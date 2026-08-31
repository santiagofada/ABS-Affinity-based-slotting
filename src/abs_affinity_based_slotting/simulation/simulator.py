"""The simulation loop: walk events over a state, letting a policy place replens.

Each run copies the initial state and walks the stream in time order.
Replenishments ask the policy where the units go (the answer must be a free
location or one the SKU already owns). Batches are processed atomically, after
applying every replenishment falling inside their time span, and their route is
measured over the locations actually visited using the same snake ordering and
distance model as the static evaluator.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from ..evaluation import route_distance, snake_order, summarize_route_costs
from ..slotting import Assignment, SlottingInstance
from ..slotting.objective import _assignment_location_indices
from .base import ReplenishmentPolicy, SimulationContext
from .events import PickBatch, ReplenEvent
from .initial_state import pick_units
from .results import SimulationResult
from .state import WarehouseState


class Simulator:
    """Runs event streams over warehouse states.

    Holds only geometry (instance + snake key + dock); each ``run`` is
    independent and does not mutate its inputs.
    """

    def __init__(
        self,
        instance: SlottingInstance,
        bay_snake_key: np.ndarray,
        dock_bay: int,
    ):
        if bay_snake_key.shape != (instance.n_bays,):
            raise ValueError(
                f"bay_snake_key must have shape ({instance.n_bays},), "
                f"got {bay_snake_key.shape}"
            )
        self._instance = instance
        self._bay_snake_key = np.asarray(bay_snake_key, dtype=float)
        self._dock_bay = int(dock_bay)

    @classmethod
    def from_tables(
        cls,
        instance: SlottingInstance,
        coordinates: pd.DataFrame,
        *,
        dock: str = "DOCK",
    ) -> "Simulator":
        from ..evaluation import bay_snake_keys

        return cls(
            instance,
            bay_snake_keys(coordinates, instance.bay_ids),
            instance.bay_index(dock),
        )

    def run(
        self,
        initial_state: WarehouseState,
        events: list[PickBatch | ReplenEvent],
        policy: ReplenishmentPolicy,
        *,
        planned: Assignment | None = None,
        lam: float = 0.5,
        seed: int = 0,
    ) -> SimulationResult:
        """Simulate ``events`` from ``initial_state`` under ``policy``.

        Parameters
        ----------
        planned:
            The slotting plan being simulated; required by plan-aware policies
            and by the off-home metric. Must cover the SKU universe.
        """
        instance = self._instance
        state = initial_state.copy()

        if planned is not None:
            planned_location = _assignment_location_indices(planned, instance)
        else:
            planned_location = None

        context = SimulationContext(
            instance=instance,
            planned_location=planned_location,
            lam=float(lam),
            rng=np.random.default_rng(seed),
        )

        # A SKU is "at home" when it sits on its planned location and nowhere
        # else. Counted once, then updated per SKU as events touch it.
        if planned_location is not None:
            at_home = np.fromiter(
                (
                    state.locations_of(s) == frozenset({int(planned_location[s])})
                    for s in range(instance.n_skus)
                ),
                dtype=bool,
                count=instance.n_skus,
            )
            off_home_count = int(instance.n_skus - at_home.sum())
        else:
            at_home = None
            off_home_count = -1

        n_relocations = 0
        shortfall_lines = 0
        shortfall_units = 0
        batch_rows: list[tuple] = []
        replen_rows: list[tuple] = []

        def off_home_fraction() -> float:
            if off_home_count < 0:
                return math.nan
            return off_home_count / instance.n_skus

        def refresh_at_home(sku_idx: int) -> None:
            nonlocal off_home_count
            if at_home is None:
                return
            now_home = state.locations_of(sku_idx) == frozenset(
                {int(planned_location[sku_idx])}
            )
            off_home_count += int(at_home[sku_idx]) - int(now_home)
            at_home[sku_idx] = now_home

        def apply_replen(event: ReplenEvent) -> None:
            nonlocal n_relocations, off_home_count
            dest = int(policy.choose_destination(event, state, context))
            owner = state.sku_at(dest)
            if owner not in (-1, event.sku_idx):
                raise RuntimeError(
                    f"policy {policy.name!r} chose location {dest}, which holds "
                    f"SKU {owner}, for SKU {event.sku_idx}"
                )
            moved = dest not in state.locations_of(event.sku_idx)
            state.add_units(event.sku_idx, dest, event.quantity)
            state.release_empty_locations(event.sku_idx, keep=dest)
            if moved:
                n_relocations += 1
            refresh_at_home(event.sku_idx)
            replen_rows.append(
                (
                    event.timestamp,
                    event.sku_idx,
                    dest,
                    moved,
                    (
                        dest == int(planned_location[event.sku_idx])
                        if planned_location is not None
                        else None
                    ),
                )
            )

        batches = [e for e in events if isinstance(e, PickBatch)]
        replens = [e for e in events if isinstance(e, ReplenEvent)]

        replen_ptr = 0
        for batch in batches:
            visited: set[int] = set()
            batch_shortfall = 0

            # Interleaved at exact timestamps: a replen fires right before the
            # line that triggered it, when the SKU is actually drained.
            for line_ts, sku_idx, qty in zip(
                batch.line_timestamps, batch.sku_indices, batch.quantities
            ):
                while (
                    replen_ptr < len(replens)
                    and replens[replen_ptr].timestamp <= line_ts
                ):
                    apply_replen(replens[replen_ptr])
                    replen_ptr += 1

                stops, missing = pick_units(state, int(sku_idx), int(qty))
                visited.update(stops)
                refresh_at_home(int(sku_idx))
                if missing > 0:
                    shortfall_lines += 1
                    shortfall_units += missing
                    batch_shortfall += missing

            bays = np.unique(
                instance.location_bay[np.fromiter(visited, dtype=np.int64)]
            ) if visited else np.empty(0, dtype=np.int64)
            ordered = snake_order(bays, self._bay_snake_key[bays])
            distance = route_distance(ordered, instance.bay_distance, self._dock_bay)

            batch_rows.append(
                (
                    batch.batch_id,
                    batch.timestamp,
                    distance,
                    batch.n_lines,
                    batch_shortfall,
                    off_home_fraction(),
                )
            )

        while replen_ptr < len(replens):
            apply_replen(replens[replen_ptr])
            replen_ptr += 1

        batch_log = pd.DataFrame(
            batch_rows,
            columns=[
                "batch_id",
                "timestamp",
                "distance",
                "n_lines",
                "shortfall_units",
                "off_home_fraction",
            ],
        )
        replen_log = pd.DataFrame(
            replen_rows,
            columns=["timestamp", "sku_idx", "destination", "moved", "at_home"],
        )

        return SimulationResult(
            route_metrics=summarize_route_costs(batch_log["distance"].to_numpy()),
            batch_log=batch_log,
            replen_log=replen_log,
            n_relocations=n_relocations,
            shortfall_lines=shortfall_lines,
            shortfall_units=shortfall_units,
            final_off_home_fraction=off_home_fraction(),
            final_state=state,
        )
