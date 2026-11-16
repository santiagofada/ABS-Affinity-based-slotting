"""Simulation that re-batches each pool with the warehouse as it is at that moment.

This is how the project simulates a slotting plan: the warehouse starts as it
really is, and the plan only enters through relocations decided by the
replenishment policy (see :mod:`.plan_aisle`). Because the aisle of a SKU
changes during the run, the batching has to read the current state, as a WMS
would.

The test orders are cut into pools of ``window * batch_size`` consecutive
orders (arrival order). For each pool:

1. read the aisle of every SKU (the aisle of its location with the most units);
2. re-batch the pool with :class:`AisleCoverBatching` using those aisles;
3. simulate its batches plus the replenishments up to the pool's last line.

With ``window = 1`` the pools are the FIFO batches, which do not depend on the
state, so several of them are simulated per step (``fifo_chunk``) only to keep
the run fast.

Every step also logs how far the plan has come in: the mean number of aisles
per order of the step's orders (with the SKUs where they are at that moment)
and, given a plan, the share of the training demand whose SKU has a location
in its planned aisle.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..batching import AisleCoverBatching, orders_by_arrival
from ..slotting import Assignment, SlottingInstance
from ..slotting.objective import _assignment_location_indices
from .base import ReplenishmentPolicy
from .events import build_event_stream
from .simulator import Simulator
from .state import WarehouseState


@dataclass(frozen=True)
class RollingResult:
    """Outcome of :func:`simulate_rolling`.

    Attributes
    ----------
    picking:
        The test lines with the ``batch_id`` actually used.
    batch_log:
        One row per batch (the columns of ``SimulationResult.batch_log``) plus
        the step it belongs to.
    step_log:
        One row per step: ``step``, ``timestamp`` (first line), ``orders``,
        ``aisles_per_order`` and ``demand_in_plan_aisle`` (NaN without a plan).
    n_relocations:
        Replenishments that moved a SKU somewhere new.
    shortfall_lines:
        Pick lines the state could not fully serve.
    batching:
        Route totals the batching computed (``fifo``, ``construction``,
        ``local_search``), summed over the pools.
    final_state:
        The warehouse state after the last step.
    """

    picking: pd.DataFrame
    batch_log: pd.DataFrame
    step_log: pd.DataFrame
    n_relocations: int
    shortfall_lines: int
    batching: dict
    final_state: WarehouseState


def location_aisles(simulator: Simulator, instance: SlottingInstance) -> np.ndarray:
    """Aisle position (0-based) of every location; needs S-shape routing."""
    bay_aisle = getattr(simulator.routing, "bay_aisle", None)
    if bay_aisle is None:
        raise ValueError("location_aisles needs a simulator with s_shape routing")
    return np.asarray(bay_aisle, dtype=np.int64)[instance.location_bay]


def simulate_rolling(
    simulator: Simulator,
    instance: SlottingInstance,
    initial_state: WarehouseState,
    picking: pd.DataFrame,
    replenishments: pd.DataFrame,
    policy: ReplenishmentPolicy,
    *,
    aisle_set_cost: np.ndarray,
    window: int,
    batch_size: int = 25,
    max_passes: int = 20,
    planned: Assignment | None = None,
    lam: float = 0.5,
    seed: int = 0,
    location_aisle: np.ndarray | None = None,
    fifo_chunk: int = 20,
) -> RollingResult:
    """Simulate ``picking`` and ``replenishments`` re-batching pool by pool.

    ``planned`` is passed to the policy (``plan_aisle`` and ``home`` need it)
    and drives the ``demand_in_plan_aisle`` log.
    Each step's run gets the seed ``seed + step``, so a random policy does not
    repeat its draws. ``location_aisle`` defaults to the aisles of the
    simulator's S-shape routing; pass it when the simulator walks another
    route. ``initial_state`` is not modified.
    """
    if window < 1:
        raise ValueError("window must be positive")
    loc_aisle = location_aisles(simulator, instance) if location_aisle is None else np.asarray(location_aisle)
    planned_location = None if planned is None else _assignment_location_indices(planned, instance)
    plan_aisle = None if planned is None else loc_aisle[planned_location]
    sku_index = instance.sku_indexes

    orders = orders_by_arrival(picking)
    step_orders = (window if window > 1 else fifo_chunk) * batch_size
    step_of_order = pd.Series(np.arange(len(orders)) // step_orders, index=orders)
    step_of_line = picking["order_id"].map(step_of_order).to_numpy()
    replen = replenishments.sort_values("timestamp", kind="stable")
    replen_ts = replen["timestamp"].to_numpy()
    replen_events = build_event_stream(picking.iloc[0:0], replen, instance)   # built once, in time order
    no_replen = replen.iloc[0:0]

    state = initial_state.copy()
    replen_start = 0
    pickings, logs, steps = [], [], []
    totals = {"fifo": 0.0, "construction": 0.0, "local_search": 0.0}
    n_relocations = shortfall_lines = 0
    n_steps = int(step_of_order.max()) + 1 if len(orders) else 0
    for step in range(n_steps):
        lines = picking[step_of_line == step]
        step_time = lines["timestamp"].min()

        loc_sku, loc_units = state.location_arrays()                           # 1
        held = loc_sku >= 0
        current = (pd.DataFrame({"sku": loc_sku[held], "units": loc_units[held], "aisle": loc_aisle[held]})
                   .sort_values(["sku", "units"], ascending=[True, False]).drop_duplicates("sku")
                   .set_index("sku")["aisle"])
        sku_aisle = pd.Series(current.reindex(lines["sku"].map(sku_index).unique()).to_numpy(),
                              index=lines["sku"].unique())
        if sku_aisle.isna().any():
            raise RuntimeError(f"{int(sku_aisle.isna().sum())} SKUs of step {step} hold no location")

        batching = AisleCoverBatching(sku_aisle.astype(np.int64), aisle_set_cost, batch_size=batch_size,  # 2
                                      window=window, max_passes=max_passes)
        batched = batching.make_batches(lines)
        batched = batched.assign(batch_id=f"S{step:05d}-" + batched["batch_id"].astype(str))
        for key in totals:
            totals[key] += batching.stats_[key]

        masks = batching.order_masks(lines, orders_by_arrival(lines))
        in_plan = np.nan
        if plan_aisle is not None:
            placed = np.zeros(instance.n_skus, dtype=bool)
            placed[loc_sku[held][loc_aisle[held] == plan_aisle[loc_sku[held]]]] = True
            in_plan = float(instance.demand[placed].sum() / instance.demand.sum())
        steps.append({"step": step, "timestamp": step_time, "orders": len(masks),
                      "aisles_per_order": float(np.mean([bin(int(m)).count("1") for m in masks])),
                      "demand_in_plan_aisle": in_plan})

        # 3. Replenishments up to this step's last line (all the rest after the last step).
        if step == n_steps - 1:
            replen_end = len(replen)
        else:
            replen_end = int(np.searchsorted(replen_ts, lines["timestamp"].max().to_datetime64(), side="right"))
        # Simulator.run splits batches from replenishments, so the two lists can be concatenated.
        events = build_event_stream(batched, no_replen, instance) + replen_events[replen_start:replen_end]
        replen_start = replen_end

        res = simulator.run(state, events, policy, planned=planned_location, lam=lam, seed=seed + step,
                            copy_state=False)
        state = res.final_state
        n_relocations += res.n_relocations
        shortfall_lines += res.shortfall_lines
        pickings.append(batched)
        logs.append(res.batch_log.assign(step=step))

    return RollingResult(
        picking=pd.concat(pickings),
        batch_log=pd.concat(logs, ignore_index=True),
        step_log=pd.DataFrame(steps),
        n_relocations=n_relocations,
        shortfall_lines=shortfall_lines,
        batching=totals,
        final_state=state,
    )
