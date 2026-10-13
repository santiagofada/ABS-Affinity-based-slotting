"""Re-batching that covers each batch with as few (and as cheap) aisles as possible.

Orders are pooled ``window`` FIFO batches at a time (``window * batch_size``
consecutive orders), so no order waits longer than ``window`` batch slots. Each
pool is split into the same number of batches FIFO would make, of
``batch_size`` orders each, minimising the total strict S route

    sum_k R_S( union of the aisles of the orders in batch k ).

Under strict S the route depends only on the visited aisles, so every order is
summarised by the bit mask of the aisles its SKUs sit in (given a slotting
plan), and ``R_S`` of any union is read from a table over masks.

Two steps per pool:

1. Construction (seed and grow): open a batch with the remaining order whose
   own route is the most expensive, then repeatedly add the remaining order
   that increases the batch route the least, until the batch is full.
2. Improvement: swap two orders of different batches whenever it lowers the
   pool's total route, best swap per order, until a full pass finds none or
   ``max_passes`` is reached.
"""

from __future__ import annotations

import math
from collections.abc import Mapping

import numpy as np
import pandas as pd

from .base import batching_registry, orders_by_arrival, relabel


@batching_registry.register("aisle_cover")
class AisleCoverBatching:
    name = "aisle_cover"

    def __init__(
        self,
        sku_aisle: Mapping,
        aisle_set_cost: np.ndarray,
        *,
        batch_size: int = 25,
        window: int = 1,
        max_passes: int = 20,
    ):
        """
        Parameters
        ----------
        sku_aisle:
            Aisle position (0-based) of every SKU under the slotting plan.
        aisle_set_cost:
            Route cost of every set of aisles, indexed by bit mask
            (``SShapeRouting.mask_costs()``).
        window:
            FIFO batches pooled together; 1 reproduces FIFO.
        """
        if batch_size < 1 or window < 1 or max_passes < 0:
            raise ValueError("batch_size and window must be positive, max_passes non-negative")
        self.sku_aisle = pd.Series(sku_aisle, dtype="int64")
        self.cost = np.asarray(aisle_set_cost, dtype=float)
        self.n_aisles = int(round(math.log2(len(self.cost))))
        if len(self.cost) != 1 << self.n_aisles:
            raise ValueError("aisle_set_cost must have length 2**n_aisles")
        if self.sku_aisle.min() < 0 or self.sku_aisle.max() >= self.n_aisles:
            raise ValueError("sku_aisle values must be aisle positions 0..n_aisles-1")
        self.batch_size = int(batch_size)
        self.window = int(window)
        self.max_passes = int(max_passes)
        #: Totals of the last ``make_batches`` call (sum of R_S over batches).
        self.stats_: dict = {}

    # ------------------------------------------------------------------ masks
    def order_masks(self, picking: pd.DataFrame, orders: pd.Index) -> np.ndarray:
        """Bit mask of the aisles each order touches, aligned with ``orders``."""
        pairs = picking[["order_id", "sku"]].drop_duplicates()
        aisle = pairs["sku"].map(self.sku_aisle)
        if aisle.isna().any():
            raise ValueError(f"{int(aisle.isna().sum())} order lines have SKUs without an aisle")
        bit = np.left_shift(1, aisle.to_numpy(dtype=np.int64))
        masks = pd.Series(bit).groupby(pairs["order_id"].to_numpy()).agg(np.bitwise_or.reduce)
        return masks.reindex(orders).to_numpy(dtype=np.int64)

    # ------------------------------------------------------------------- pool
    def _fifo_cost(self, masks: np.ndarray) -> float:
        total = 0.0
        for start in range(0, len(masks), self.batch_size):
            total += self.cost[np.bitwise_or.reduce(masks[start:start + self.batch_size])]
        return total

    def _construct(self, masks: np.ndarray) -> np.ndarray:
        n, q = len(masks), self.batch_size
        batch = np.full(n, -1, dtype=np.int64)
        own_cost = self.cost[masks]
        for k in range(math.ceil(n / q)):
            free = np.flatnonzero(batch < 0)
            seed = free[np.argmax(own_cost[free])]
            batch[seed], union, size = k, masks[seed], 1
            while size < q:
                free = np.flatnonzero(batch < 0)
                if free.size == 0:
                    break
                increase = self.cost[union | masks[free]] - self.cost[union]
                pick = free[np.argmin(increase)]
                batch[pick], union, size = k, union | masks[pick], size + 1
        return batch

    def _improve(self, masks: np.ndarray, batch: np.ndarray) -> tuple[np.ndarray, int]:
        n, n_batches = len(masks), int(batch.max()) + 1
        if n_batches < 2:
            return batch, 0
        pow2 = np.left_shift(1, np.arange(self.n_aisles, dtype=np.int64))
        bits = ((masks[:, None] & pow2) > 0).astype(np.int64)            # bits[o, a]
        count = np.zeros((n_batches, self.n_aisles), dtype=np.int64)      # orders of batch k in aisle a
        np.add.at(count, batch, bits)
        union = ((count > 0) * pow2).sum(axis=1)                          # aisles of each batch
        without = (((count[batch] - bits) > 0) * pow2).sum(axis=1)        # aisles of o's batch without o
        batch = batch.copy()
        n_swaps = 0
        for _ in range(self.max_passes):
            swaps_this_pass = 0
            for o in range(n):
                k1 = batch[o]
                # swap o with every order j: batch k1 loses o and gains j; j's batch loses j and gains o
                delta = (self.cost[without[o] | masks] + self.cost[without | masks[o]]
                         - self.cost[union[k1]] - self.cost[union[batch]])
                delta[batch == k1] = np.inf
                j = int(np.argmin(delta))
                if delta[j] >= -1e-9:
                    continue
                k2 = batch[j]
                count[k1] += bits[j] - bits[o]
                count[k2] += bits[o] - bits[j]
                batch[o], batch[j] = k2, k1
                for k in (k1, k2):
                    union[k] = ((count[k] > 0) * pow2).sum()
                touched = np.flatnonzero((batch == k1) | (batch == k2))
                without[touched] = (((count[batch[touched]] - bits[touched]) > 0) * pow2).sum(axis=1)
                swaps_this_pass += 1
            n_swaps += swaps_this_pass
            if swaps_this_pass == 0:
                break
        return batch, n_swaps

    def _pool_cost(self, masks: np.ndarray, batch: np.ndarray) -> float:
        unions = pd.Series(masks).groupby(batch).agg(np.bitwise_or.reduce).to_numpy(dtype=np.int64)
        return float(self.cost[unions].sum())

    # ----------------------------------------------------------------- public
    def make_batches(self, picking: pd.DataFrame) -> pd.DataFrame:
        orders = orders_by_arrival(picking)
        masks = self.order_masks(picking, orders)
        pool_size = self.window * self.batch_size

        labels = np.empty(len(orders), dtype=object)
        totals = {"fifo": 0.0, "construction": 0.0, "local_search": 0.0, "swaps": 0, "pools": 0}
        for p, start in enumerate(range(0, len(orders), pool_size)):
            pool = slice(start, start + pool_size)
            m = masks[pool]
            built = self._construct(m)
            improved, swaps = self._improve(m, built)
            labels[pool] = [f"AC-{p:05d}-{k:03d}" for k in improved]
            totals["fifo"] += self._fifo_cost(m)
            totals["construction"] += self._pool_cost(m, built)
            totals["local_search"] += self._pool_cost(m, improved)
            totals["swaps"] += swaps
            totals["pools"] += 1
        self.stats_ = totals
        return relabel(picking, pd.Series(labels, index=orders))
