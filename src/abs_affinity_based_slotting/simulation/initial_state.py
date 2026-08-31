"""Building the simulation's starting states.

Three entry points:

- :func:`state_from_initial_stock` — the day-0 snapshot, straight from the
  ``initial_stock`` table (units included).
- :func:`state_after_history` — the state after the recorded events, derived
  arithmetically from the data (units in minus units out per location, plus
  ownership rules). Used to move day 0 to the REAL state at the train/test
  cutoff, the honest starting point of the ``current`` baseline.
- :func:`reslot_state` — apply a method's Assignment as a full re-slot: every
  SKU moves to its planned location carrying the units it had. The cost of that
  massive move is out of scope but reportable (compare locations before/after).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..slotting import Assignment, SlottingInstance
from .events import PickBatch, ReplenEvent
from .state import FREE, WarehouseState


def state_from_initial_stock(
    instance: SlottingInstance,
    initial_stock: pd.DataFrame,
) -> WarehouseState:
    """Day-0 state: every non-empty row occupies its location with its units."""
    state = WarehouseState(instance.n_skus, instance.n_locations)
    loc_to_idx = instance.location_indexes

    unknown = ~initial_stock["location_id"].isin(loc_to_idx)
    if unknown.any():
        raise ValueError(
            f"{int(unknown.sum())} initial_stock locations missing from the "
            f"instance, e.g. {initial_stock.loc[unknown, 'location_id'].iloc[0]!r}"
        )

    occupied = initial_stock[initial_stock["sku"].notna()]
    for row in occupied.itertuples(index=False):
        state.add_units(
            instance.sku_index(row.sku),
            loc_to_idx[row.location_id],
            int(row.units),
        )
    return state


def pick_units(
    state: WarehouseState, sku_idx: int, qty: int
) -> tuple[list[int], int]:
    """Consume ``qty`` units of a SKU, visiting as few locations as possible.

    Go to the location with the least stock that covers the line on its own; if
    none does, gather from several walking from least to most stock. What the
    stock cannot cover is reported as a shortfall instead of raising. Returns
    (visited location indices, missing units).
    """
    stocked = sorted(
        (units, loc)
        for loc in state.locations_of(sku_idx)
        if (units := state.units_at(loc)) > 0
    )
    if not stocked:
        return [], qty

    sufficient = [loc for units, loc in stocked if units >= qty]
    if sufficient:
        state.remove_units(sku_idx, sufficient[0], qty)
        state.release_empty_locations(sku_idx)
        return [sufficient[0]], 0

    visited = []
    remaining = qty
    for units, loc in stocked:
        taken = state.remove_units(sku_idx, loc, min(units, remaining))
        if taken > 0:
            visited.append(loc)
            remaining -= taken
        if remaining == 0:
            break
    state.release_empty_locations(sku_idx)
    return visited, remaining


@dataclass(frozen=True)
class HistorySummary:
    n_batches: int
    n_replens: int
    n_relocations: int        # replens whose recorded source differs from target
    n_multi_location_skus: int  # SKUs left holding more than one location
    n_homeless_skus: int      # SKUs left with no location (0 stock, home taken)


def state_after_history(
    initial_state: WarehouseState,
    events: list[PickBatch | ReplenEvent],
    instance: SlottingInstance,
) -> tuple[WarehouseState, HistorySummary]:
    """State after the recorded events, derived arithmetically from the data.

    Everything is recorded, so the final state is computed rather than walked
    event by event: units per location are initial plus deliveries minus picks,
    each stocked location belongs to the last SKU delivered there, and each
    SKU's home is the target of its last replenishment.

    Deriving instead of walking sidesteps a quirk of the data: relocations are
    stamped at their trigger pick minus the handling time, so picks at the new
    location can appear BEFORE the relocation that delivers there. Arithmetic
    is immune to that reordering.

    A location ending negative means corrupt data and raises. A SKU left with
    no stock whose home was taken over ends up with no location; the
    simulation places it on its next replenishment.
    """
    batches = [e for e in events if isinstance(e, PickBatch)]
    replens = sorted(
        (e for e in events if isinstance(e, ReplenEvent)),
        key=lambda e: e.timestamp,
    )

    units = np.fromiter(
        (initial_state.units_at(loc) for loc in range(instance.n_locations)),
        dtype=np.int64,
        count=instance.n_locations,
    )
    owner = np.fromiter(
        (initial_state.sku_at(loc) for loc in range(instance.n_locations)),
        dtype=np.int64,
        count=instance.n_locations,
    )
    home = {
        sku: initial_state.primary_location(sku)
        for sku in range(instance.n_skus)
        if initial_state.locations_of(sku)
    }

    n_relocations = 0
    for event in replens:
        units[event.dataset_target_idx] += event.quantity
        owner[event.dataset_target_idx] = event.sku_idx
        home[event.sku_idx] = event.dataset_target_idx
        if event.dataset_target_idx != event.source_location_idx:
            n_relocations += 1

    for batch in batches:
        np.subtract.at(units, batch.location_indices, batch.quantities)

    negative = np.flatnonzero(units < 0)
    if negative.size:
        raise RuntimeError(
            f"{negative.size} locations end with negative stock, e.g. "
            f"location {int(negative[0])} at {int(units[negative[0]])}: "
            "corrupt event data"
        )

    state = WarehouseState(instance.n_skus, instance.n_locations)
    for loc in np.flatnonzero(units > 0):
        state.add_units(int(owner[loc]), int(loc), int(units[loc]))

    n_homeless = 0
    for sku, loc in home.items():
        if state.sku_at(loc) == FREE:
            state.add_units(sku, int(loc), 0)
        elif not state.locations_of(sku):
            n_homeless += 1

    n_multi = sum(
        1 for sku in range(instance.n_skus) if len(state.locations_of(sku)) > 1
    )
    return state, HistorySummary(
        n_batches=len(batches),
        n_replens=len(replens),
        n_relocations=n_relocations,
        n_multi_location_skus=n_multi,
        n_homeless_skus=n_homeless,
    )


def reslot_state(
    state_at_cutoff: WarehouseState,
    assignment: Assignment,
    instance: SlottingInstance,
) -> WarehouseState:
    """Full re-slot: every SKU moves to its planned location with its units.

    SKUs at 0 units still occupy their planned location (an owner at zero
    level, as in the initial stock). Unplanned locations end up free. Raises if
    the assignment does not cover the instance's SKU universe.
    """
    state = WarehouseState(instance.n_skus, instance.n_locations)
    for sku_idx, sku_id in enumerate(instance.sku_ids):
        try:
            loc_id = assignment.location_of(sku_id)
        except KeyError as exc:
            raise ValueError(f"assignment is missing SKU {sku_id!r}") from exc
        state.add_units(
            sku_idx,
            instance.location_index(loc_id),
            state_at_cutoff.total_units(sku_idx),
        )
    return state

