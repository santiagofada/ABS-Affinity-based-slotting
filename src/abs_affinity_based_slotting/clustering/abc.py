"""ABC clustering: group SKUs into demand classes by cumulative demand share."""

from __future__ import annotations

import numpy as np

from ..slotting import SlottingInstance
from .base import clustering_registry


@clustering_registry.register("abc")
class ABCClustering:
    """Group SKUs into demand classes (the classic Pareto A/B/C analysis).

    SKUs are ranked by demand descending; class boundaries are drawn where the
    cumulative demand share crosses each threshold. With the default
    ``(0.8, 0.95)`` this yields three classes: A (the few SKUs making up ~80%
    of demand), B (the next ~15%) and C (the long tail). Labels follow demand
    priority, so 0 = A, 1 = B, 2 = C.

    The number of classes equals ``len(thresholds) + 1``.
    """

    name = "abc"

    def __init__(self, thresholds: tuple[float, ...] = (0.8, 0.95)):
        self.thresholds = np.asarray(thresholds, dtype=float)

    def cluster(self, instance: SlottingInstance) -> np.ndarray:
        demand = instance.demand
        labels = np.empty(len(demand), dtype=int)

        total = demand.sum()
        if total <= 0:
            labels.fill(len(self.thresholds))  # everything in the last class
            return labels

        order = np.argsort(-demand, kind="stable")
        cum_share = np.cumsum(demand[order]) / total
        labels[order] = np.searchsorted(self.thresholds, cum_share, side="left")
        return labels
