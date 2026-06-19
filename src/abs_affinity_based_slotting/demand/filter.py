"""Affinity filters: sparse transformations applied to matrix A after construction.

An AffinityFilter takes a CSR affinity matrix and returns a sparser version,
keeping only the most informative entries. Filtering before solving reduces
the search space and removes noisy weak affinities.

Three strategies:
- TopKFilter: keep the k strongest neighbors per SKU (row-wise top-k)
- ThresholdFilter: keep entries with a_ij >= threshold
- MutualTopKFilter: keep (i,j) only if j is in top-k of i AND i is in top-k of j
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
from scipy.sparse import csr_matrix

from ..registry import Registry


@runtime_checkable
class AffinityFilter(Protocol):
    name: str

    def filter(self, affinity: csr_matrix) -> csr_matrix:
        """Return a sparser version of affinity. Shape is preserved."""
        ...


#: name -> AffinityFilter subclass.
filter_registry: Registry[type[AffinityFilter]] = Registry("filter")


def _row_wise_top_k(affinity: csr_matrix, k: int) -> csr_matrix:
    """Keep only the k largest entries of each row, zeroing the rest.

    Directional helper: the result is NOT symmetric in general (j may be in row
    i's top-k while i is not in row j's). Callers symmetrize afterwards.
    """
    affinity = affinity.tocsr()
    new_data = affinity.data.copy()

    for i in range(affinity.shape[0]):
        start, end = affinity.indptr[i], affinity.indptr[i + 1]
        row_data = new_data[start:end]
        n_neighbors = len(row_data)

        if n_neighbors <= k:
            continue

        # Drop everything below the k-th largest value. argpartition finds that
        # cutoff in O(n) average instead of fully sorting the row.
        threshold_pos = n_neighbors - k
        cutoff_idx = np.argpartition(row_data, threshold_pos)[threshold_pos]
        cutoff_val = row_data[cutoff_idx]
        row_data[row_data < cutoff_val] = 0.0

    result = csr_matrix(
        (new_data, affinity.indices.copy(), affinity.indptr.copy()),
        shape=affinity.shape,
    )
    result.eliminate_zeros()
    return result


@filter_registry.register("top_k")
class TopKFilter:
    """Keep the k strongest neighbors per SKU, then symmetrize by union.

    For each row i, the k entries with highest a_ij are kept. The result is then
    symmetrized by UNION: edge (i, j) survives if j is in i's top-k OR i is in
    j's top-k. The kept value is the original (symmetric) affinity.

    Symmetry is required: the QAP affinity matrix must satisfy a_ij = a_ji, and
    swap_delta relies on it. A raw row-wise top-k is directional and would break
    that invariant, so symmetrization is part of the filter, not optional.

    For the stricter intersection variant (edge survives only if mutual), see
    MutualTopKFilter.

    Parameters
    ----------
    k : int
        Number of neighbors to keep per SKU before symmetrization.
    """

    name = "top_k"

    def __init__(self, k: int):
        if k < 1:
            raise ValueError(f"k must be >= 1, got {k}.")
        self.k = int(k)

    def filter(self, affinity: csr_matrix) -> csr_matrix:
        """Return symmetric top-k filtered affinity matrix.

        Union symmetrization: element-wise maximum of the directional top-k and
        its transpose. Since the input is symmetric, max keeps the original value
        on any edge surviving in either direction. Complexity: O(nnz).
        """
        one_sided = _row_wise_top_k(affinity, self.k)
        result = one_sided.maximum(one_sided.T)
        result.eliminate_zeros()
        return result


@filter_registry.register("threshold")
class ThresholdFilter:
    """Keep only entries with a_ij >= threshold.

    Removes weak affinities below a minimum score. Preserves symmetry if the
    input is symmetric (both (i,j) and (j,i) are either kept or removed
    independently based on their value; for symmetric matrices they are equal).

    Parameters
    ----------
    threshold : float
        Minimum affinity value to keep.
    """

    name = "threshold"

    def __init__(self, threshold: float):
        if threshold < 0:
            raise ValueError(f"threshold must be >= 0, got {threshold}.")
        self.threshold = float(threshold)

    def filter(self, affinity: csr_matrix) -> csr_matrix:
        """Return threshold-filtered affinity matrix.

        Zero out all entries with a_ij < threshold, then eliminate zeros.
        Complexity: O(nnz).
        """
        affinity = affinity.tocsr()
        result = affinity.copy()
        result.data[result.data < self.threshold] = 0.0
        result.eliminate_zeros()
        return result


@filter_registry.register("mutual_top_k")
class MutualTopKFilter:
    """Keep (i,j) only if j is in top-k of i AND i is in top-k of j.

    Symmetric sparsification: an edge survives only when both SKUs consider
    each other important neighbors. Produces a symmetric matrix.

    Stricter than TopKFilter (fewer edges) but more noise-resistant: weak
    one-directional affinities are discarded.

    Parameters
    ----------
    k : int
        Number of neighbors considered per SKU in each direction.
    """

    name = "mutual_top_k"

    def __init__(self, k: int):
        if k < 1:
            raise ValueError(f"k must be >= 1, got {k}.")
        self.k = int(k)

    def filter(self, affinity: csr_matrix) -> csr_matrix:
        """Return mutual top-k filtered affinity matrix.

        Intersection symmetrization: take the directional row-wise top-k, then
        keep only edges present in BOTH it and its transpose (element-wise
        minimum). An edge survives only if i→j and j→i both made top-k.
        Complexity: O(nnz) for filtering + O(nnz) for intersection.
        """
        one_sided = _row_wise_top_k(affinity, self.k)

        # minimum(M, M.T) is nonzero only where both directions are nonzero; with
        # symmetric input values it preserves the original affinity.
        result = one_sided.minimum(one_sided.T)
        result.eliminate_zeros()
        return result
