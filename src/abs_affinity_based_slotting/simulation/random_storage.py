"""Random storage: refill in place, and on a stockout move to any free slot.

Models a warehouse with no slotting plan, where the system puts things where
there is room. It is the counterfactual the plan-aware policies are measured
against, and it mirrors how the dataset itself was generated.
"""

from __future__ import annotations

from .base import SimulationContext, replenishment_policy_registry
from .events import ReplenEvent
from .state import WarehouseState


@replenishment_policy_registry.register("random")
class RandomStoragePolicy:
    """Refill in place; relocate to a random free slot on stockout."""

    name = "random"

    def __init__(self, relocation_probability: float = 0.9):
        if not 0.0 <= relocation_probability <= 1.0:
            raise ValueError(
                f"relocation_probability must be in [0, 1], "
                f"got {relocation_probability}"
            )
        self.relocation_probability = float(relocation_probability)

    def choose_destination(
        self,
        event: ReplenEvent,
        state: WarehouseState,
        context: SimulationContext,
    ) -> int:
        locations = state.locations_of(event.sku_idx)

        if locations and state.total_units(event.sku_idx) > 0:
            # Refill the location running out (ties by lowest index).
            return min(locations, key=lambda loc: (state.units_at(loc), loc))

        if locations:
            # Stocked out: relocate with probability p, else refill in place.
            free = state.free_pool()
            if len(free) > 0 and context.rng.random() < self.relocation_probability:
                return free.sample(context.rng)
            return min(locations)

        # The SKU owns no location at all: it must take a free one.
        return state.free_pool().sample(context.rng)
