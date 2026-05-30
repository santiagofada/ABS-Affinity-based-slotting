"""Representation of a slotting assignment.

An ``Assignment`` maps SKUs to warehouse locations:

    SKU -> location

The mapping is injective: a SKU is assigned to one location, and a location can
hold at most one SKU.

The class keeps two dictionaries internally, one for each lookup direction.
This makes both ``location_of(sku)`` and ``sku_at(location)`` constant-time
operations. The object is intentionally mutable because local-search methods
need to try many swaps efficiently.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Hashable

import pandas as pd

Sku = Hashable
Location = Hashable


class Assignment:
    """SKU-location assignment used by slotting methods.

    Parameters
    ----------
    mapping:
        Mapping from SKU identifiers to location identifiers.

    Notes
    -----
    This class represents assigned SKUs only. Empty locations are not stored.
    """

    def __init__(self, mapping: Mapping[Sku, Location]):
        self._sku_to_loc = dict(mapping)
        self._loc_to_sku = self._build_reverse_mapping(self._sku_to_loc)

    @staticmethod
    def _build_reverse_mapping(
        sku_to_loc: Mapping[Sku, Location],
    ) -> dict[Location, Sku]:
        loc_to_sku: dict[Location, Sku] = {}

        for sku, loc in sku_to_loc.items():
            if loc in loc_to_sku:
                previous_sku = loc_to_sku[loc]
                raise ValueError(
                    f"Location {loc!r} is assigned to multiple SKUs: "
                    f"{previous_sku!r} and {sku!r}."
                )

            loc_to_sku[loc] = sku

        return loc_to_sku

    @classmethod
    def from_frame(
        cls,
        df: pd.DataFrame,
        *,
        sku_col: str = "sku",
        location_col: str = "location_id",
        drop_missing: bool = True,
    ) -> "Assignment":
        """Build an assignment from a DataFrame.

        Parameters
        ----------
        df:
            DataFrame containing one row per assigned SKU.
        sku_col:
            Column containing SKU identifiers.
        location_col:
            Column containing location identifiers.
        drop_missing:
            If True, rows with missing SKU or location are ignored.

        Returns
        -------
        Assignment
            Assignment built from the selected columns.
        """
        missing_cols = {sku_col, location_col} - set(df.columns)
        if missing_cols:
            raise ValueError(f"Missing columns: {sorted(missing_cols)}")

        assignment_df = df[[sku_col, location_col]].copy()

        if drop_missing:
            assignment_df = assignment_df.dropna(subset=[sku_col, location_col])

        if assignment_df[sku_col].duplicated().any():
            duplicated = assignment_df.loc[
                assignment_df[sku_col].duplicated(),
                sku_col,
            ].unique()
            raise ValueError(f"Duplicate SKUs found: {list(duplicated[:5])}")

        return cls(
            dict(
                zip(
                    assignment_df[sku_col],
                    assignment_df[location_col],
                )
            )
        )

    def location_of(self, sku: Sku) -> Location:
        """Return the location assigned to a SKU."""
        return self._sku_to_loc[sku]

    def sku_at(self, location: Location) -> Sku | None:
        """Return the SKU assigned to a location, or None if it is empty."""
        return self._loc_to_sku.get(location)

    def contains_location(self, location: Location) -> bool:
        """Return whether a location is occupied in this assignment."""
        return location in self._loc_to_sku

    def swap(self, sku_a: Sku, sku_b: Sku) -> None:
        """Swap the locations of two assigned SKUs in place."""
        if sku_a == sku_b:
            return

        loc_a = self._sku_to_loc[sku_a]
        loc_b = self._sku_to_loc[sku_b]

        self._sku_to_loc[sku_a] = loc_b
        self._sku_to_loc[sku_b] = loc_a

        self._loc_to_sku[loc_a] = sku_b
        self._loc_to_sku[loc_b] = sku_a

    def copy(self) -> "Assignment":
        """Return an independent copy of the assignment."""
        return Assignment(self._sku_to_loc)

    def to_dict(self) -> dict[Sku, Location]:
        """Return a copy of the SKU-to-location mapping."""
        return dict(self._sku_to_loc)

    def to_frame(
        self,
        *,
        sku_col: str = "sku",
        location_col: str = "location_id",
    ) -> pd.DataFrame:
        """Export the assignment as a DataFrame."""
        return pd.DataFrame(
            {
                sku_col: list(self._sku_to_loc.keys()),
                location_col: list(self._sku_to_loc.values()),
            }
        )

    @property
    def skus(self) -> Iterable[Sku]:
        """Assigned SKUs."""
        return self._sku_to_loc.keys()

    @property
    def locations(self) -> Iterable[Location]:
        """Occupied locations."""
        return self._loc_to_sku.keys()

    def __contains__(self, sku: Sku) -> bool:
        return sku in self._sku_to_loc

    def __len__(self) -> int:
        return len(self._sku_to_loc)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Assignment):
            return False

        return self._sku_to_loc == other._sku_to_loc

    def __repr__(self) -> str:
        return f"Assignment(n_skus={len(self)})"