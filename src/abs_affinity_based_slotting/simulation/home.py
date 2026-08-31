"""Replenishment policy that keeps every SKU on its planned location.

Models a WMS that knows the slotting plan and maintains it: the units go to
the SKU's assigned location whenever possible, and to the nearest free
location (by bay walking distance) when someone else occupies it. Comparing
this against ``random`` quantifies how much respecting the plan is worth.
"""

from __future__ import annotations

import numpy as np

from .base import SimulationContext, replenishment_policy_registry
from .events import ReplenEvent
from .state import WarehouseState


@replenishment_policy_registry.register("home")
class HomePolicy:
    """Deliver to the planned location, or the nearest free slot to it."""

    name = "home"

    def choose_destination(
        self,
        event: ReplenEvent,
        state: WarehouseState,
        context: SimulationContext,
    ) -> int:
        if context.planned_location is None:
            raise ValueError(
                "the home policy needs a slotting plan; run the simulation "
                "with planned=<Assignment>"
            )
        home = int(context.planned_location[event.sku_idx])

        owner = state.sku_at(home)
        if owner in (-1, event.sku_idx):
            return home

        # Home is taken by another SKU: nearest free location to home by bay
        # distance; ties broken by lowest location index (determinism).
        free = state.free_pool().as_array()
        if free.size == 0:
            own = state.locations_of(event.sku_idx)
            if own:
                return min(own)
            raise RuntimeError(
                f"no free locations and SKU {event.sku_idx} owns none"
            )
        instance = context.instance
        distances = instance.bay_distance[
            instance.location_bay[free], instance.location_bay[home]
        ]
        return int(free[np.lexsort((free, distances))[0]])
