"""Replenishment policy that re-optimizes the slotting objective on every replen.

This is where the slotting algorithm acts online: instead of maintaining a
fixed plan, each replenishment chooses the location that minimizes the SKU's
marginal contribution to the surrogate objective, given where everything sits
RIGHT NOW:

    cost(l) = lam * f_s * c[l]
            + (1 - lam) * 2 * sum_j a_sj * dist(l, location of j)

where j runs over the SKU's affinity neighbors (the nonzero row of A) and the
factor 2 mirrors the symmetric double count of the objective. A neighbor spread
over several locations contributes the mean distance to them. Candidates are
every free location plus the SKU's current ones (staying put is a decision).
"""

from __future__ import annotations

import numpy as np

from .base import SimulationContext, replenishment_policy_registry
from .events import ReplenEvent
from .state import WarehouseState


@replenishment_policy_registry.register("objective_greedy")
class ObjectiveGreedyPolicy:
    """Send the units to the marginal-cost-minimizing location."""

    name = "objective_greedy"

    def choose_destination(
        self,
        event: ReplenEvent,
        state: WarehouseState,
        context: SimulationContext,
    ) -> int:
        instance = context.instance
        sku = event.sku_idx
        lam = context.lam

        own = np.fromiter(state.locations_of(sku), dtype=np.int64)
        free = state.free_pool().as_array()
        candidates = np.concatenate([free, own]) if own.size else free
        if candidates.size == 0:
            raise RuntimeError(
                f"no candidate locations for SKU {sku}: free pool empty and "
                "the SKU owns none"
            )

        cost = lam * instance.demand[sku] * instance.location_cost[candidates]

        if lam < 1.0:
            affinity = instance.affinity
            start, end = affinity.indptr[sku], affinity.indptr[sku + 1]
            neighbors = affinity.indices[start:end]
            weights = affinity.data[start:end]

            # One (location, weight) list for all neighbors: a neighbor spread
            # over several locations splits its weight evenly, so its
            # contribution is the mean distance. One matrix product then scores
            # every candidate at once.
            neighbor_locations: list[int] = []
            neighbor_weights: list[float] = []
            for neighbor, weight in zip(neighbors, weights):
                locations = state.locations_of(int(neighbor))
                if not locations:
                    continue
                share = weight / len(locations)
                neighbor_locations.extend(locations)
                neighbor_weights.extend([share] * len(locations))

            if neighbor_locations:
                neighbor_bays = instance.location_bay[
                    np.asarray(neighbor_locations, dtype=np.int64)
                ]
                candidate_bays = instance.location_bay[candidates]
                quadratic = (
                    instance.bay_distance[np.ix_(candidate_bays, neighbor_bays)]
                    @ np.asarray(neighbor_weights)
                )
                cost = cost + (1.0 - lam) * 2.0 * quadratic

        # argmin with ties broken by lowest location index (determinism).
        return int(candidates[np.lexsort((candidates, cost))[0]])
