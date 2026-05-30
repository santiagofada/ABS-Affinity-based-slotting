"""Access cost of each location, measured as distance to the dock."""

from __future__ import annotations

import pandas as pd

from ..config import DOCK, inches_to_meters
from .distances import distance_to_dock


def build_location_costs(
    initial_stock: pd.DataFrame,
    distances: pd.DataFrame,
    *,
    dock: str = DOCK,
) -> pd.DataFrame:
    """Attach the dock distance of its bay to every location.

    The location-to-dock distance is approximated by the bay-to-dock distance
    (intra-bay travel between shelves/bins is not modeled).
    """
    dock_dist = distance_to_dock(distances, dock=dock)

    costs = initial_stock[["location_id", "location_name", "bay_id"]].copy()
    costs["distance_to_dock_in"] = costs["bay_id"].map(dock_dist)
    costs["distance_to_dock_m"] = inches_to_meters(costs["distance_to_dock_in"])

    missing = costs["distance_to_dock_in"].isna().sum()
    if missing:
        raise ValueError(f"{missing} locations have no bay distance to the dock")

    return costs
