"""Warehouse locations derived from initial stock."""

from __future__ import annotations

import pandas as pd


def build_locations(initial_stock: pd.DataFrame) -> pd.DataFrame:
    """Return one row per physical location with an ``is_empty`` flag.

    A location is empty when it holds no SKU. SKUs are 1:1 with non-empty
    locations in this dataset.
    """
    locations = initial_stock.copy()
    locations["is_empty"] = locations["sku"].isna()
    return locations


def occupied_locations(initial_stock: pd.DataFrame) -> pd.DataFrame:
    """Return only the locations that initially hold a SKU."""
    return initial_stock[initial_stock["sku"].notna()].reset_index(drop=True)
