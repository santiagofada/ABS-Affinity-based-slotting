"""Exact linear assignment solution for λ=1 regime (demand only, no affinity).

Solves the linear sum assignment problem (Hungarian algorithm) to find the
optimal assignment of SKUs to locations when minimizing L = Σ_i f_i * c[x_i].

Complexity: O(n³) via Hungarian algorithm. Only practical for n ≲ 5000.
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import linear_sum_assignment

from ..slotting import Assignment, SlottingInstance
from .base import method_registry


@method_registry.register("linear_assignment")
class LinearAssignmentSlotting:
    """Exact solver for the linear assignment problem (λ=1).

    Finds the optimal assignment of SKUs to locations minimizing:

        L = Σ_i f_i * c[x_i]

    (ignoring affinity; equivalent to λ=1 in the QAP formulation).

    Uses the Hungarian algorithm from scipy.optimize.linear_sum_assignment.
    Optimal solution, but O(n³) complexity; only scales to n ≲ 5000.

    Useful for:
    - Benchmarking: measuring how far greedy is from optimal.
    - Validation: verifying the formulation and builder.
    - Small-scale experiments or tesis validation.
    """

    name = "linear_assignment"

    def solve(self, instance: SlottingInstance) -> Assignment:
        """Find the optimal assignment minimizing linear term.

        Returns
        -------
        Assignment
            SKU-to-location mapping. All instance SKUs are assigned;
            m - n locations remain empty (if m > n).

        Raises
        ------
        ValueError
            If the instance has more SKUs than locations (infeasible).
        """
        n_skus = instance.n_skus
        n_locations = instance.n_locations

        if n_skus > n_locations:
            raise ValueError(
                f"More SKUs ({n_skus}) than locations ({n_locations}): infeasible."
            )

        # Build cost matrix: cost[i, ℓ] = f_i * c[ℓ]
        # Shape: (n_skus, n_locations)
        cost_matrix = np.outer(instance.demand, instance.location_cost)

        # Solve linear sum assignment (Hungarian algorithm).
        # Returns (sku_indices, location_indices) where sku_indices[i] is paired
        # with location_indices[i].
        sku_indices, location_indices = linear_sum_assignment(cost_matrix)

        # Build Assignment: sku_id → location_id
        assignment = Assignment()
        for sku_idx, loc_idx in zip(sku_indices, location_indices):
            sku_id = instance.sku_id(sku_idx)
            location_id = instance.location_id(loc_idx)
            assignment[sku_id] = location_id

        return assignment
