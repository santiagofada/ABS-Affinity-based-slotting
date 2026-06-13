"""Merchant clustering: group SKUs by their merchant (vendor)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..slotting import SlottingInstance
from .base import clustering_registry


@clustering_registry.register("merchant")
class MerchantClustering:
    """Group SKUs by merchant id. Each distinct merchant is one cluster.

    Requires ``instance.merchant_ids``. SKUs with a missing merchant id share
    a single cluster (label -1).
    """

    name = "merchant"

    def cluster(self, instance: SlottingInstance) -> np.ndarray:
        if instance.merchant_ids is None:
            raise ValueError("MerchantClustering requires instance.merchant_ids")
        labels, _ = pd.factorize(instance.merchant_ids)
        return labels.astype(int)
