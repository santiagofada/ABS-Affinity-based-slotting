"""Contract for clustering strategies — the pluggable ways to group SKUs.

A clustering strategy partitions the instance's SKUs into groups, returning one
integer label per SKU (aligned with ``instance.sku_ids``). It does NOT place
SKUs into locations: producing an Assignment is the job of a slotting method.

This separation is what enables a bi-level decomposition. The grouping is the
outer level (which SKUs belong together); a method then solves the placement of
those groups (inner level). The grouping granularity tunes the decomposition:
a single group holding every SKU leaves all the work to the inner solver, while
one group per SKU (labels = 0..n-1, the identity partition) is the opposite
extreme.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from ..registry import Registry
from ..slotting import SlottingInstance


@runtime_checkable
class ClusteringStrategy(Protocol):
    name: str

    def cluster(self, instance: SlottingInstance) -> np.ndarray:
        """Return an integer cluster label per SKU, aligned with sku_ids."""
        ...


clustering_registry: Registry[type[ClusteringStrategy]] = Registry("clustering")
