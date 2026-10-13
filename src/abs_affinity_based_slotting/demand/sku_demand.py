"""Per-SKU demand features derived from picking history."""

from __future__ import annotations

import pandas as pd


def build_sku_demand(
    picking_events: pd.DataFrame,
    *,
    sku_col: str = "sku",
    batch_col: str = "batch_id",
    time_col: str = "timestamp",
    qty_col: str = "quantity",
    merchant_col: str = "merchant_account_id",
    order_col: str = "order_id",
) -> pd.DataFrame:
    """Aggregate picking events into one row per SKU.

    ``pick_lines`` (the number of pick actions) is the primary demand metric:
    each line is one operational pick regardless of the units taken. The
    alternatives are ``unique_orders`` (orders containing the SKU; only when
    the table has ``order_col``), ``unique_batches`` (trips that visit it) and
    ``total_units``.
    """
    grouped = picking_events.groupby(sku_col, observed=True)
    columns = dict(
        merchant_account_id=(merchant_col, "first"),
        pick_lines=(sku_col, "size"),
        total_units=(qty_col, "sum"),
        unique_batches=(batch_col, "nunique"),
        first_pick_date=(time_col, "min"),
        last_pick_date=(time_col, "max"),
    )
    if order_col in picking_events.columns:
        columns["unique_orders"] = (order_col, "nunique")
    demand = grouped.agg(**columns)
    return (
        demand.sort_values("pick_lines", ascending=False)
        .reset_index()
    )
