"""Warehouse locations derived from initial stock."""

from __future__ import annotations

import pandas as pd


def occupied_locations(initial_stock: pd.DataFrame) -> pd.DataFrame:
    """Return only the locations that initially hold a SKU."""
    return initial_stock[initial_stock["sku"].notna()].reset_index(drop=True)
