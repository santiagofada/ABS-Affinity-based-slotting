"""Contract for clustering strategies (the pluggable ways to group SKUs).

A clustering strategy groups the instance's SKUs (e.g. by affinity, by merchant)
into clusters that two-stage slotting methods place into nearby zones. Variants
are registered implementations; the two-stage method consumes any of them.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np

from .registry import Registry
from .slotting import SlottingInstance


@runtime_checkable
class ClusteringStrategy(Protocol):
    name: str

    def cluster(self, instance: SlottingInstance) -> np.ndarray:
        """Return a cluster label per SKU, aligned with ``instance.sku_ids``."""
        ...


#: name -> ClusteringStrategy subclass. Implementations are deferred.
clustering_registry: Registry[type[ClusteringStrategy]] = Registry("clustering")
