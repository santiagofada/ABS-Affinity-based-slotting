"""Demand-greedy baseline: assign high-demand SKUs to low-cost locations."""

from __future__ import annotations

import numpy as np

from ..slotting import Assignment, SlottingInstance
from .base import method_registry


@method_registry.register("demand_greedy")
class DemandGreedySlotting:
    """Greedy assignment by demand frequency.

    Sorts SKUs by demand (descending) and locations by cost (ascending),
    then assigns SKU[i] → Location[i]. Ignores affinity entirely.
    Equivalent to optimizing λ·L with λ=1, no quadratic term.

    Complexity: O(n log n + m log m) for sorting.
    """

    name = "demand_greedy"

    def solve(self, instance: SlottingInstance) -> Assignment:
        """Assign SKUs greedily by demand to cheapest locations.

        Returns
        -------
        Assignment
            SKU-to-location mapping. All instance SKUs are assigned;
            m - n locations remain empty (if m > n).
        """
        # Sort SKUs by demand descending: highest demand first.
        sku_order = np.argsort(-instance.demand)  # negation reverses sort

        # Sort locations by cost ascending: cheapest first.
        location_order = np.argsort(instance.location_cost)

        # Greedy assignment: pair SKUs (by demand) with locations (by cost).
        mapping = {}
        for sku_idx, loc_idx in zip(sku_order, location_order[: len(sku_order)]):
            sku_id = instance.sku_id(sku_idx)
            location_id = instance.location_id(loc_idx)
            mapping[sku_id] = location_id

        return Assignment(mapping)
