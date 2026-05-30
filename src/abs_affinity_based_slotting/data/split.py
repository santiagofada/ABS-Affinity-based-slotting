"""Temporal train/test split of picking events.

The split is done at *batch* granularity: a batch is the unit of co-occurrence
and of evaluation, so it must never straddle the train/test boundary. Each batch
is assigned to a partition by the timestamp of its first pick line, and the most
recent ``test_size`` fraction of batches becomes the test set.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TemporalSplit:
    train: pd.DataFrame
    test: pd.DataFrame
    cutoff: pd.Timestamp  # first timestamp belonging to the test set


def split_picking_events(
    picking_events: pd.DataFrame,
    *,
    test_size: float = 0.2,
    batch_col: str = "batch_id",
    time_col: str = "timestamp",
) -> TemporalSplit:
    """Split ``picking_events`` into train/test keeping whole batches together.

    Parameters
    ----------
    test_size:
        Fraction of batches (most recent) assigned to the test set, in (0, 1).
    """
    if not 0.0 < test_size < 1.0:
        raise ValueError(f"test_size must be in (0, 1), got {test_size}")

    batch_start = (
        picking_events.groupby(batch_col)[time_col].min().sort_values()
    )
    n_test = math.ceil(len(batch_start) * test_size)
    test_batches = set(batch_start.index[-n_test:])

    is_test = picking_events[batch_col].isin(test_batches)
    train = picking_events.loc[~is_test].reset_index(drop=True)
    test = picking_events.loc[is_test].reset_index(drop=True)
    cutoff = batch_start.iloc[-n_test]

    return TemporalSplit(train=train, test=test, cutoff=cutoff)
