"""A slotting solution: a partial bijection between SKUs and locations.

Mutability: ``Assignment`` is **mutable in place**. ``swap`` is O(1) and changes
the object directly, because local-search heuristics perform huge numbers of
swaps and the standard pattern is "try a swap, measure, undo if it doesn't
help". Use :meth:`copy` to snapshot a solution (e.g. to remember the best one).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Hashable

import pandas as pd

Sku = Hashable
Location = Hashable


class Assignment:
    """Maps each SKU to exactly one location; each location holds <= one SKU.

    Backed by two dicts (``sku -> location`` and ``location -> sku``) so that
    lookups in both directions and swaps are O(1).
    """

    def __init__(self, mapping: Mapping[Sku, Location]):
        sku_to_loc = dict(mapping)
        loc_to_sku: dict[Location, Sku] = {}
        for sku, loc in sku_to_loc.items():
            if loc in loc_to_sku:
                raise ValueError(
                    f"location {loc!r} assigned to both "
                    f"{loc_to_sku[loc]!r} and {sku!r}"
                )
            loc_to_sku[loc] = sku
        self._sku_to_loc = sku_to_loc
        self._loc_to_sku = loc_to_sku

    @classmethod
    def from_frame(
        cls,
        df: pd.DataFrame,
        *,
        sku_col: str = "sku",
        location_col: str = "location_id",
    ) -> "Assignment":
        """Build an Assignment from a DataFrame with SKU and location columns."""
        if df[sku_col].duplicated().any():
            raise ValueError(f"duplicate SKUs in column {sku_col!r}")
        return cls(dict(zip(df[sku_col], df[location_col])))

    # --- lookups ---

    def location_of(self, sku: Sku) -> Location:
        return self._sku_to_loc[sku]

    def sku_at(self, location: Location) -> Sku | None:
        return self._loc_to_sku.get(location)

    def __contains__(self, sku: Sku) -> bool:
        return sku in self._sku_to_loc

    def __len__(self) -> int:
        return len(self._sku_to_loc)

    @property
    def skus(self):
        return self._sku_to_loc.keys()

    @property
    def locations(self):
        return self._loc_to_sku.keys()

    # --- mutation (in place) ---

    def swap(self, sku_a: Sku, sku_b: Sku) -> None:
        """Swap the locations of two assigned SKUs, in place (O(1))."""
        loc_a = self._sku_to_loc[sku_a]
        loc_b = self._sku_to_loc[sku_b]
        self._sku_to_loc[sku_a], self._sku_to_loc[sku_b] = loc_b, loc_a
        self._loc_to_sku[loc_a], self._loc_to_sku[loc_b] = sku_b, sku_a

    def copy(self) -> "Assignment":
        """Return an independent snapshot of this assignment."""
        return Assignment(self._sku_to_loc)

    # --- export ---

    def to_frame(
        self,
        *,
        sku_col: str = "sku",
        location_col: str = "location_id",
    ) -> pd.DataFrame:
        """Return a fresh canonical DataFrame (one row per SKU)."""
        return pd.DataFrame(
            {
                sku_col: list(self._sku_to_loc),
                location_col: list(self._sku_to_loc.values()),
            }
        )

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, Assignment)
            and self._sku_to_loc == other._sku_to_loc
        )

    def __repr__(self) -> str:
        return f"Assignment({len(self)} SKUs)"
