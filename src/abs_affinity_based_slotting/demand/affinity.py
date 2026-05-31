"""Contract for affinity builders (the pluggable ways to build the matrix A).

An affinity builder turns raw co-occurrence into a SKU-SKU affinity score.
Keeping the input metric-agnostic (co-occurrence counts + per-SKU support +
number of batches) lets every metric — raw count, Jaccard, cosine, lift, ... —
be a separate registered implementation deriving from the same data.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
from scipy.sparse import csr_matrix

from ..registry import Registry


@runtime_checkable
class AffinityBuilder(Protocol):
    name: str

    def build(
        self,
        cooccurrence: csr_matrix,  # (n_skus, n_skus) #batches with both SKUs
        support: np.ndarray,       # (n_skus,) #batches containing each SKU
        n_batches: int,
    ) -> csr_matrix:
        """Return the SKU-SKU affinity matrix (CSR), aligned with ``support``."""
        ...


#: name -> AffinityBuilder subclass. Implementations live alongside (deferred).
affinity_registry: Registry[type[AffinityBuilder]] = Registry("affinity")
