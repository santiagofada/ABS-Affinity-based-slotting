"""Surrogate objective for affinity-based slotting.

This module implements the train-side objective used by constructive heuristics
and local search. It is deliberately separate from ``evaluation``: the objective
is a cheap surrogate optimized on historical demand and affinity, while the
evaluator replays held-out batches with a route model.
"""

from __future__ import annotations

from typing import Hashable

import numpy as np

from .assignment import Assignment
from .instance import SlottingInstance

SkuId = Hashable


def slotting_cost(
    assignment: Assignment,
    instance: SlottingInstance,
    *,
    lam: float,
) -> float:
    """Return the full surrogate slotting cost C.

    Objective function: C = λ·L + (1-λ)·Q

    where:
        L = Σ_i f_i · c[x_i]     (linear: demand × location cost)
        Q = Σ_i Σ_j a_ij · d[x_i, x_j]  (quadratic: affinity × distance)

    Notation:
        i, j = SKU indices
        x_i = location assigned to SKU i (assignment variable)
        f_i = demand of SKU i (picking count)
        c[x] = cost of location x (distance to dock)
        a_ij = affinity between SKU i and j (co-occurrence or Jaccard)
        d[x, y] = distance between locations x and y

    The quadratic term counts both (i,j) and (j,i) if present in the affinity
    matrix (symmetric case with no division by 2).

    Parameters
    ----------
    assignment : Assignment
        Current assignment x (SKU → location mapping).
    instance : SlottingInstance
        Problem data: f (demand array), c (location costs), a (affinity matrix),
        d (distance matrix).
    lam : float
        Weight λ ∈ [0, 1]. λ=1 minimizes L; λ=0 minimizes Q.

    Returns
    -------
    float
        C = λ·L + (1-λ)·Q
    """
    lam = _validate_lam(lam)
    location_idx = _assignment_location_indices(assignment, instance)

    linear = float(np.dot(instance.demand, instance.location_cost[location_idx]))
    quadratic = _quadratic_cost_from_location_indices(instance, location_idx)

    return lam * linear + (1.0 - lam) * quadratic


def swap_delta(
    assignment: Assignment,
    instance: SlottingInstance,
    sku_a: SkuId,
    sku_b: SkuId,
    *,
    lam: float,
) -> float:
    """Return the cost change from swapping two SKUs' locations.

    Returns: ΔC = C(x') - C(x) where x' is x with SKUs a and b swapped.

    Negative ΔC indicates improvement; positive indicates worsening.

    Cost change formula: ΔC = λ·ΔL + (1-λ)·ΔQ

    where:
        ΔL = (f_a - f_b)·(c[x'_a] - c[x_a])
           = (f_a - f_b)·(c[x_b] - c[x_a])     (after relocation)

        ΔQ = 2 · Σ_k (a_ak - a_bk)·(d[x'_a, x_k] - d[x_a, x_k])
           = 2 · Σ_k (a_ak - a_bk)·(d[x_b, x_k] - d[x_a, x_k])

    Efficiency: O(degree). Assumes affinity matrix is symmetric; iterates only
    over neighbors (nonzero entries) of SKUs a and b, not all n SKUs.

    Parameters
    ----------
    assignment : Assignment
        Current assignment x.
    instance : SlottingInstance
        Problem data.
    sku_a, sku_b : SkuId
        Two SKUs to swap.
    lam : float
        Weight λ ∈ [0, 1].

    Returns
    -------
    float
        ΔC = C(x') - C(x). Negative = improving move.
    """
    lam = _validate_lam(lam)

    if sku_a == sku_b:
        return 0.0

    sku_a_idx = instance.sku_index(sku_a)
    sku_b_idx = instance.sku_index(sku_b)

    loc_a_idx = instance.location_index(assignment.location_of(sku_a))
    loc_b_idx = instance.location_index(assignment.location_of(sku_b))

    linear_delta = (instance.demand[sku_a_idx] - instance.demand[sku_b_idx]) * (
        instance.location_cost[loc_b_idx] - instance.location_cost[loc_a_idx]
    )

    quadratic_delta = _symmetric_sparse_swap_quadratic_delta(
        assignment=assignment,
        instance=instance,
        sku_a_idx=sku_a_idx,
        sku_b_idx=sku_b_idx,
        loc_a_idx=loc_a_idx,
        loc_b_idx=loc_b_idx,
    )

    return float(lam * linear_delta + (1.0 - lam) * quadratic_delta)


def _validate_lam(lam: float) -> float:
    lam = float(lam)
    if not 0.0 <= lam <= 1.0:
        raise ValueError(f"lamda must be in [0, 1], got {lam}.")
    return lam


def _assignment_location_indices(
    assignment: Assignment,
    instance: SlottingInstance,
) -> np.ndarray:
    """Extract location indices from assignment as a dense array.

    Returns: x, where x[i] = location index of SKU i (aligned with instance.sku_ids).

    Validates:
    - Every SKU in instance has an assigned location (no missing SKUs).
    - Every assigned location exists in the instance (no invalid locations).

    Raises ValueError if validation fails.
    """
    location_idx = np.empty(instance.n_skus, dtype=np.int64)

    for i, sku_id in enumerate(instance.sku_ids):
        try:
            location_id = assignment.location_of(sku_id)
        except KeyError as exc:
            raise ValueError(f"Assignment is missing SKU {sku_id!r}.") from exc

        try:
            location_idx[i] = instance.location_index(location_id)
        except KeyError as exc:
            raise ValueError(
                f"Assignment maps SKU {sku_id!r} to unknown location "
                f"{location_id!r}."
            ) from exc

    return location_idx


def _quadratic_cost_from_location_indices(
    instance: SlottingInstance,
    location_idx: np.ndarray,
) -> float:
    """Evaluate quadratic term: Q = Σ_i Σ_j a_ij · d[x_i, x_j].

    Input: location_idx[i] = x_i (location index of SKU i).
    Sparse computation: only nonzero a_ij entries are evaluated.
    Maps each location to a bay, then looks up bay-to-bay distances.

    Complexity: O(nnz(a)) where nnz(a) is the number of nonzero entries in affinity.
    """
    affinity = instance.affinity.tocoo()

    if affinity.nnz == 0:
        return 0.0

    sku_row_locations = location_idx[affinity.row]
    sku_col_locations = location_idx[affinity.col]

    sku_row_bays = instance.location_bay[sku_row_locations]
    sku_col_bays = instance.location_bay[sku_col_locations]

    bay_distances = instance.bay_distance[sku_row_bays, sku_col_bays]

    return float(np.dot(affinity.data, bay_distances))


def _symmetric_sparse_swap_quadratic_delta(
    *,
    assignment: Assignment,
    instance: SlottingInstance,
    sku_a_idx: int,
    sku_b_idx: int,
    loc_a_idx: int,
    loc_b_idx: int,
) -> float:
    """Compute ΔQ for swapping SKUs a and b (quadratic term of cost change).

    After swap: x'_a = x_b and x'_b = x_a.

    ΔQ = Q(x') - Q(x)
       = Σ_k [a_ak · d[x'_a, x_k] + a_ka · d[x_k, x'_a]]
         - Σ_k [a_ak · d[x_a, x_k] + a_ka · d[x_k, x_a]]
       + (swap a ↔ b symmetrically)

    With symmetric affinity (a_ij = a_ji) and summing over both directions:
    ΔQ = 2 · Σ_k (a_ak - a_bk) · [d[x_b, x_k] - d[x_a, x_k]]

    Algorithm:
    1. Find union of neighbors of a and b (nonzero columns in rows a, b).
    2. For each neighbor k (excluding a and b):
       - Compute affinity_delta = a_ak - a_bk
       - Compute distance_delta = d[x_b, x_k] - d[x_a, x_k]
       - Accumulate: ΔQ += affinity_delta × distance_delta
    3. Multiply by 2 for both orderings (a→k and k→a).

    Efficiency: O(deg(a) + deg(b)). Iterates only over neighbors, not all n SKUs.
    """
    affinity = instance.affinity.tocsr()

    # We need a_ak and a_bk for every neighbor k. The naive way is scalar indexing
    # affinity[a, k] inside the loop, but a CSR matrix stores only the nonzero
    # entries of each row as parallel (column, value) lists, so affinity[a, k] has
    # to search row a's column list on every single access. With ~250k swaps per
    # pass and ~10 neighbors each, that search runs millions of times and is what
    # makes local search hang -- despite the function being O(degree) on paper.
    #
    # Fix: read each row's (column, value) pairs ONCE into a plain dict, so each
    # later lookup row_a[k] is a true O(1) hash access instead of a row scan.
    row_a = _row_as_dict(affinity, sku_a_idx)
    row_b = _row_as_dict(affinity, sku_b_idx)

    # Neighbors that matter are those with nonzero affinity to a or b (the rest
    # contribute a_ak - a_bk = 0). a and b themselves are excluded.
    neighbor_indices = (row_a.keys() | row_b.keys()) - {sku_a_idx, sku_b_idx}

    if not neighbor_indices:
        return 0.0

    quadratic_delta = 0.0

    for neighbor_idx in neighbor_indices:
        # Where does neighbor k currently sit? We need its location to measure how
        # the a<->b swap changes the distance between k and each of them.
        neighbor_sku_id = instance.sku_id(neighbor_idx)
        neighbor_location_idx = instance.location_index(
            assignment.location_of(neighbor_sku_id)
        )

        # After the swap, a sits where b was. distance_change is how much closer (or
        # farther) k ends up from that slot: d[x_b, x_k] - d[x_a, x_k].
        distance_change = (
            instance.distance_between_location_indices(loc_b_idx, neighbor_location_idx)
            - instance.distance_between_location_indices(loc_a_idx, neighbor_location_idx)
        )

        # a_ak - a_bk; a neighbor absent from a row means its affinity there is 0.
        affinity_change = row_a.get(neighbor_idx, 0.0) - row_b.get(neighbor_idx, 0.0)
        quadratic_delta += affinity_change * distance_change

    # Factor 2: the affinity matrix is symmetric, so each pair (a, k) is also
    # counted as (k, a). We summed one direction and double it.
    return float(2.0 * quadratic_delta)


def _row_as_dict(matrix, row: int) -> dict[int, float]:
    """Return {column index: value} for one CSR row's nonzero entries.

    Reading the row's slice of ``indices`` and ``data`` once and zipping them into
    a dict turns repeated affinity lookups from O(row length) row scans into O(1)
    hash accesses.
    """
    start, end = matrix.indptr[row], matrix.indptr[row + 1]
    return dict(zip(matrix.indices[start:end], matrix.data[start:end]))
