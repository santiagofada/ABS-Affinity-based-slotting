"""Affinity clustering: group SKUs by connectivity in the affinity graph."""

from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components

from ..slotting import SlottingInstance
from .base import clustering_registry


@clustering_registry.register("affinity")
class AffinityClustering:
    """Group SKUs into connected components of the affinity graph.

    The SKU-SKU affinity matrix is read as an undirected graph: two SKUs are
    linked when their affinity is nonzero, and SKUs reachable through a chain
    of links share a cluster.

    With ``k`` set, only the top-k strongest affinity edges per SKU are kept
    before computing components. This controls how coarse the grouping is and
    removes weak/noisy links (e.g. single co-occurrences); SKUs left with no
    edges become singleton clusters. Note that on a dense graph the components
    can collapse into one giant cluster, so ``k`` is the main knob to tune.
    """

    name = "affinity"

    def __init__(self, k: int | None = None):
        self.k = k

    def cluster(self, instance: SlottingInstance) -> np.ndarray:
        graph = instance.affinity
        if self.k is not None:
            graph = _topk_per_row(graph, self.k)
        graph = graph.maximum(graph.T)  # treat as undirected
        _, labels = connected_components(graph, directed=False)
        return labels.astype(int)


def _topk_per_row(matrix: csr_matrix, k: int) -> csr_matrix:
    """Return a copy of ``matrix`` keeping only the top-k entries per row."""
    matrix = matrix.tocsr().astype(float, copy=True)
    for i in range(matrix.shape[0]):
        start, end = int(matrix.indptr[i]), int(matrix.indptr[i + 1])
        if end - start <= k:
            continue
        row = matrix.data[start:end]
        threshold = np.partition(row, -k)[-k]
        row[row < threshold] = 0.0
    matrix.eliminate_zeros()
    return matrix
