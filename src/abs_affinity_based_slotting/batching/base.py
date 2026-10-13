"""Contract for batching policies: which orders are picked together in one trip.

A batching policy takes the picking lines of a period and returns the same lines
with a new ``batch_id``. Lines, SKUs, quantities and timestamps are untouched,
so the result feeds :func:`..simulation.build_event_stream` like the original.
Orders arrive in the order of their first pick line; that order is the only
notion of time a policy may use.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd

from ..registry import Registry


@runtime_checkable
class BatchingPolicy(Protocol):
    name: str

    def make_batches(self, picking: pd.DataFrame) -> pd.DataFrame:
        """Return ``picking`` with the ``batch_id`` column reassigned."""
        ...


#: name -> BatchingPolicy class.
batching_registry: Registry[type[BatchingPolicy]] = Registry("batching policy")


def orders_by_arrival(
    picking: pd.DataFrame,
    *,
    order_col: str = "order_id",
    time_col: str = "timestamp",
) -> pd.Index:
    """Order ids sorted by the timestamp of their first line (ties by id)."""
    first = picking.groupby(order_col)[time_col].min().reset_index()
    return pd.Index(first.sort_values([time_col, order_col], kind="stable")[order_col])


def relabel(
    picking: pd.DataFrame,
    batch_of_order: pd.Series,
    *,
    order_col: str = "order_id",
    batch_col: str = "batch_id",
) -> pd.DataFrame:
    """Copy of ``picking`` whose batch column comes from ``batch_of_order``."""
    batch = picking[order_col].map(batch_of_order)
    if batch.isna().any():
        raise ValueError(f"{int(batch.isna().sum())} lines belong to orders without a batch")
    return picking.assign(**{batch_col: batch.to_numpy()})
