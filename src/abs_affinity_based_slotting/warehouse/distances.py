"""Bay-to-bay walking distances.

The raw ``distances`` table stores each unordered bay pair once. These helpers
turn it into a symmetric lookup and extract the distance of each bay to the dock.
"""

from __future__ import annotations

import pandas as pd

from ..config import DOCK


def build_bay_distance_matrix(distances: pd.DataFrame) -> pd.DataFrame:
    """Return a symmetric bay-by-bay distance matrix (inches), zero diagonal.
    """
    long = distances.rename(
        columns={"bay_a": "src", "bay_b": "dst", "distance_in": "d"}
    )
    mirror = long.rename(columns={"src": "dst", "dst": "src"})
    full = pd.concat([long, mirror], ignore_index=True)

    matrix = full.pivot(index="src", columns="dst", values="d")
    bays = matrix.index.union(matrix.columns)
    matrix = matrix.reindex(index=bays, columns=bays)
    for bay in bays:
        matrix.loc[bay, bay] = 0.0
    matrix.index.name = "bay_id"
    matrix.columns.name = "bay_id"
    return matrix


def distance_to_dock(distances: pd.DataFrame, dock: str = DOCK) -> pd.Series:
    """Return a Series mapping each ``bay_id`` to its distance from the dock."""
    pairs = distances[(distances["bay_a"] == dock) | (distances["bay_b"] == dock)]
    bay = pairs["bay_a"].where(pairs["bay_b"] == dock, pairs["bay_b"])
    result = pd.Series(pairs["distance_in"].to_numpy(), index=bay.to_numpy())
    result.loc[dock] = 0.0
    result.index.name = "bay_id"
    result.name = "distance_to_dock_in"
    return result
