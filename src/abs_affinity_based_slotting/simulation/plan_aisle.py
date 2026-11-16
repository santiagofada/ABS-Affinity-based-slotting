"""Put-away that brings the plan in one relocation at a time.

Starting from the warehouse as it is, the plan can only enter through the
relocations. A SKU "fits" when one of its locations is where the plan wants
it: in its planned aisle (``target="aisle"``, the default) or on its planned
location (``target="location"``). When a replenishment arrives:

- with ``trigger="stockout"`` (the default, the dataset's own mechanism), a
  SKU that still has units is refilled in place, and only a SKU that ran out
  can move;
- with ``trigger="always"``, any replenishment of a SKU that does not fit
  moves it, even with units left (they stay behind until picked, and the old
  location is freed once empty).

A SKU that fits stays (its fitting location is refilled). One that has to move
goes, with ``target="aisle"``, to a free location of its planned aisle, the
closest to its planned location, or, if that aisle is full, to a free location
of the nearest aisle (by aisle position), again the closest to its planned
location. With ``target="location"`` it goes to its planned location if free,
else to the free location closest to it by walking distance (any aisle).

Under strict S-shape routing a batch's route depends only on the aisles it
visits, which is why the default aims at the planned aisle and not at the
exact planned location.
"""

from __future__ import annotations

import numpy as np

from .base import SimulationContext, replenishment_policy_registry
from .events import ReplenEvent
from .state import WarehouseState

TRIGGERS = ("stockout", "always")
TARGETS = ("aisle", "location")


@replenishment_policy_registry.register("plan_aisle")
class PlanAislePolicy:
    """Refill in place or move to where the plan wants the SKU."""

    name = "plan_aisle"

    def __init__(self, location_aisle: np.ndarray, *, trigger: str = "stockout", target: str = "aisle"):
        """
        Parameters
        ----------
        location_aisle:
            Aisle position (0-based, 0 = closest to the dock) of every
            location, e.g. ``routing.bay_aisle[instance.location_bay]``.
        trigger:
            ``stockout`` or ``always`` (see the module docstring).
        target:
            ``aisle`` or ``location``.
        """
        if trigger not in TRIGGERS or target not in TARGETS:
            raise ValueError(f"trigger must be one of {TRIGGERS} and target one of {TARGETS}")
        self.location_aisle = np.asarray(location_aisle, dtype=np.int64)
        self.trigger = trigger
        self.target = target

    def fits(self, loc: int, planned: int) -> bool:
        """Whether a location is where the plan wants a SKU planned at ``planned``."""
        if self.target == "aisle":
            return self.location_aisle[loc] == self.location_aisle[planned]
        return loc == planned

    def choose_destination(
        self,
        event: ReplenEvent,
        state: WarehouseState,
        context: SimulationContext,
    ) -> int:
        if context.planned_location is None:
            raise ValueError(
                "the plan_aisle policy needs a slotting plan; run the "
                "simulation with planned=<Assignment>"
            )
        sku = event.sku_idx
        own = state.locations_of(sku)
        planned = int(context.planned_location[sku])
        if self.trigger == "stockout":
            if own and state.total_units(sku) > 0:
                # Still has units: refill the location running out (ties by index).
                return min(own, key=lambda loc: (state.units_at(loc), loc))
            fitting = [loc for loc in own if self.fits(loc, planned)]
            if fitting:
                return min(fitting)
        else:
            fitting = [loc for loc in own if self.fits(loc, planned)]
            if fitting:
                return min(fitting, key=lambda loc: (state.units_at(loc), loc))

        free = state.free_pool().as_array()
        if free.size == 0:
            if own:
                return min(own)
            raise RuntimeError(f"no free locations and SKU {sku} owns none")
        instance = context.instance
        distance = instance.bay_distance[instance.location_bay[free], instance.location_bay[planned]]
        if self.target == "location":
            if state.is_free(planned):
                return planned
            return int(free[np.lexsort((free, distance))[0]])
        aisle_gap = np.abs(self.location_aisle[free] - self.location_aisle[planned])
        return int(free[np.lexsort((free, distance, aisle_gap))[0]])
