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
) -> pd.DataFrame:
    """Aggregate picking events into one row per SKU.

    ``pick_lines`` (the number of pick actions) is the primary demand metric:
    each line is one operational pick regardless of the units taken.
    """
    grouped = picking_events.groupby(sku_col, observed=True)
    demand = grouped.agg(
        merchant_account_id=(merchant_col, "first"),
        pick_lines=(sku_col, "size"),
        total_units=(qty_col, "sum"),
        unique_batches=(batch_col, "nunique"),
        first_pick_date=(time_col, "min"),
        last_pick_date=(time_col, "max"),
    )
    return (
        demand.sort_values("pick_lines", ascending=False)
        .reset_index()
    )
