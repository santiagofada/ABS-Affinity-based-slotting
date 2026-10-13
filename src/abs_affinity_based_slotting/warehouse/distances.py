"""Bay-to-bay distances.

Two things live here. The helpers that turn the raw ``distances`` table (each
unordered bay pair once) into a symmetric lookup and into the distance of each
bay to the dock: that is the physical geometry, used to measure routes and to
simulate. And the pluggable *distance models*, the ``d_lk`` the quadratic term
of the objective charges between two products, registered by name:

- ``walking``: the physical walking distance between the two bays.
- ``aisle``: what S-shape routing charges: nothing if both bays are in the same
  aisle, otherwise a full aisle traverse plus the lateral move between aisles.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd

from ..config import DOCK
from ..registry import Registry


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


@runtime_checkable
class DistanceModel(Protocol):
    name: str

    def build(self, coordinates: pd.DataFrame, distances: pd.DataFrame) -> pd.DataFrame:
        """Return a symmetric bay-by-bay matrix (indexed by bay id, dock included)."""
        ...


#: name -> DistanceModel subclass.
distance_registry: Registry[type[DistanceModel]] = Registry("distance model")


@distance_registry.register("walking")
class WalkingDistance:
    """Physical walking distance between bays, straight from the distances table."""

    name = "walking"

    def build(self, coordinates, distances) -> pd.DataFrame:
        return build_bay_distance_matrix(distances)


@distance_registry.register("aisle")
class AisleDistance:
    """Cost that S-shape routing charges between two bays.

    Under S-shape the picker traverses every aisle that has at least one pick,
    end to end, and moves laterally along the cross aisle between consecutive
    aisles. So two products in the same aisle cost nothing extra to each other,
    and two products in different aisles cost an extra aisle traverse plus the
    lateral distance between the two aisles:

        d(a, b) = 0                                   if aisle(a) == aisle(b)
        d(a, b) = aisle_length + |x_aisle(a) - x_aisle(b)|   otherwise

    ``aisle_length`` is the span of the aisle in y plus one bay pitch, taken
    from the coordinates (the same for every aisle in these layouts). The dock
    row and column keep the physical distance to the dock, so the matrix stays
    usable as a full bay-by-bay lookup.
    """

    name = "aisle"

    def build(self, coordinates, distances, *, dock: str = DOCK) -> pd.DataFrame:
        bays = coordinates.dropna(subset=["aisle"]).copy()
        bays["aisle"] = bays["aisle"].astype(int)

        y_levels = np.sort(bays["y"].unique())
        pitch = float(np.min(np.diff(y_levels)))
        aisle_length = float(bays["y"].max() - bays["y"].min() + pitch)
        aisle_x = bays.groupby("aisle")["x"].mean()

        aisle_of = bays.set_index("bay_id")["aisle"]
        ids = bays["bay_id"].to_numpy()
        a = aisle_of.loc[ids].to_numpy()
        x = aisle_x.loc[a].to_numpy(dtype=float)

        different = a[:, None] != a[None, :]
        matrix = np.where(different, aisle_length + np.abs(x[:, None] - x[None, :]), 0.0)
        result = pd.DataFrame(matrix, index=ids, columns=ids)

        dock_dist = distance_to_dock(distances, dock=dock)
        result.loc[dock, :] = dock_dist.reindex(ids).to_numpy()
        result[dock] = dock_dist.reindex(result.index).to_numpy()
        result.loc[dock, dock] = 0.0
        result.index.name = "bay_id"
        result.columns.name = "bay_id"
        return result
