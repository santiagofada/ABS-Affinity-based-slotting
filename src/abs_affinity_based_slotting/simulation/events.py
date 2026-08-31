"""Pandas boundary: raw event tables -> numeric event stream.

Two event kinds feed the simulation. A :class:`PickBatch` is one picking trip,
the unit of evaluation, processed atomically. A :class:`ReplenEvent` is one
replenishment whose timestamp, SKU and quantity are replayed from the data;
only its destination is decided at simulation time.

Ids are resolved against the instance here, and an unresolved one raises: that
is the dynamic version of the static evaluator's coverage invariant.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..slotting import SlottingInstance


@dataclass(frozen=True)
class PickBatch:
    timestamp: pd.Timestamp        # first line of the batch
    end_timestamp: pd.Timestamp    # last line of the batch
    batch_id: str
    sku_indices: np.ndarray        # one entry per pick line, in line order
    quantities: np.ndarray         # int64, aligned with sku_indices
    line_timestamps: np.ndarray    # datetime64, aligned; exact interleaving
                                   # with replens for the literal replay
    location_indices: np.ndarray   # int64, aligned; the RECORDED pick location
                                   # (used by the literal replay; the simulator
                                   # re-derives locations from its own state)

    @property
    def n_lines(self) -> int:
        return len(self.sku_indices)


@dataclass(frozen=True)
class ReplenEvent:
    timestamp: pd.Timestamp
    sku_idx: int
    quantity: int
    source_location_idx: int   # the SKU's location before the replen (data)
    dataset_target_idx: int    # where the generator delivered it (historical replay)


def build_event_stream(
    picking: pd.DataFrame,
    replenishments: pd.DataFrame,
    instance: SlottingInstance,
) -> list[PickBatch | ReplenEvent]:
    """Merge picking batches and replenishments into one time-ordered stream.

    Batches are keyed by the timestamp of their first line. On a timestamp tie
    the replenishment goes first (the generator inserts each replen just before
    the pick that triggered it).
    """
    sku_to_idx = instance.sku_indexes
    loc_to_idx = instance.location_indexes

    events: list[PickBatch | ReplenEvent] = []

    picking = picking.sort_values("timestamp", kind="stable")
    sku_idx_col = picking["sku"].map(sku_to_idx)
    if sku_idx_col.isna().any():
        missing = picking.loc[sku_idx_col.isna(), "sku"].unique()
        raise ValueError(
            f"{len(missing)} picking SKUs missing from the instance, "
            f"e.g. {missing[0]!r}"
        )
    loc_idx_col = picking["location_id"].map(loc_to_idx)
    if loc_idx_col.isna().any():
        missing = picking.loc[loc_idx_col.isna(), "location_id"].unique()
        raise ValueError(
            f"{len(missing)} picking locations missing from the instance, "
            f"e.g. {missing[0]!r}"
        )
    picking = picking.assign(
        _sku_idx=sku_idx_col.astype(np.int64),
        _loc_idx=loc_idx_col.astype(np.int64),
    )

    for batch_id, group in picking.groupby("batch_id", sort=False):
        events.append(
            PickBatch(
                timestamp=group["timestamp"].iloc[0],
                end_timestamp=group["timestamp"].iloc[-1],
                batch_id=batch_id,
                sku_indices=group["_sku_idx"].to_numpy(dtype=np.int64),
                quantities=group["quantity"].to_numpy(dtype=np.int64),
                line_timestamps=group["timestamp"].to_numpy(),
                location_indices=group["_loc_idx"].to_numpy(dtype=np.int64),
            )
        )

    replenishments = replenishments.sort_values("timestamp", kind="stable")
    for column in ("sku", "source_location_id", "target_location_id"):
        mapping = sku_to_idx if column == "sku" else loc_to_idx
        unresolved = ~replenishments[column].isin(mapping)
        if unresolved.any():
            example = replenishments.loc[unresolved, column].iloc[0]
            raise ValueError(
                f"{int(unresolved.sum())} replenishment values of {column!r} "
                f"missing from the instance, e.g. {example!r}"
            )

    for row in replenishments.itertuples(index=False):
        events.append(
            ReplenEvent(
                timestamp=row.timestamp,
                sku_idx=sku_to_idx[row.sku],
                quantity=int(row.quantity),
                source_location_idx=loc_to_idx[row.source_location_id],
                dataset_target_idx=loc_to_idx[row.target_location_id],
            )
        )

    # Stable sort by timestamp; replens (kind 0) before batches (kind 1) on ties.
    events.sort(key=lambda e: (e.timestamp, isinstance(e, PickBatch)))
    return events


def split_replenishments(
    replenishments: pd.DataFrame,
    picking_train: pd.DataFrame,
    initial_stock: pd.DataFrame,
    cutoff: pd.Timestamp,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split replenishments at the train/test cutoff, repairing the boundary.

    Cutting by timestamp alone leaves some train picks without the units that
    served them, because relocations are stamped later than the physical move.
    Any location whose train stock would end negative pulls its earliest test
    replenishment back into train, repeating until every location balances.
    """
    before = replenishments["timestamp"] < cutoff
    train = replenishments[before]
    test = replenishments[~before]

    picked = picking_train.groupby("location_id")["quantity"].sum().astype("int64")
    initial = initial_stock.set_index("location_id")["units"].astype("int64")
    balance_index = picked.index.union(initial.index)
    opening = initial.reindex(balance_index, fill_value=0) - picked.reindex(
        balance_index, fill_value=0
    )

    while True:
        delivered = (
            train.groupby("target_location_id")["quantity"].sum().astype("int64")
        )
        net = opening + delivered.reindex(balance_index, fill_value=0)
        short = net[net < 0].index
        if len(short) == 0:
            return train, test
        rescue = test[test["target_location_id"].isin(short)]
        if rescue.empty:
            raise RuntimeError(
                f"{len(short)} locations cannot balance at the cutoff even "
                f"after pulling every later replen, e.g. {short[0]!r}"
            )
        first = rescue.groupby("target_location_id", sort=False).head(1)
        train = pd.concat([train, first]).sort_values("timestamp", kind="stable")
        test = test.drop(index=first.index)
