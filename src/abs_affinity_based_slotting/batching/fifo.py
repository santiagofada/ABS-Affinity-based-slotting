"""FIFO batching: consecutive orders, ``batch_size`` at a time (what the data does)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .base import batching_registry, orders_by_arrival, relabel


@batching_registry.register("fifo")
class FifoBatching:
    name = "fifo"

    def __init__(self, batch_size: int = 25):
        if batch_size < 1:
            raise ValueError(f"batch_size must be positive, got {batch_size}")
        self.batch_size = int(batch_size)

    def make_batches(self, picking: pd.DataFrame) -> pd.DataFrame:
        orders = orders_by_arrival(picking)
        number = np.arange(len(orders)) // self.batch_size
        ids = pd.Series([f"FIFO-{k:06d}" for k in number], index=orders)
        return relabel(picking, ids)
