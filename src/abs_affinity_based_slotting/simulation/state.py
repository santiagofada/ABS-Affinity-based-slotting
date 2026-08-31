"""Physical state of the warehouse at a point in time.

A :class:`WarehouseState` tracks, per location, which SKU lives there and how
many units it holds. It is the mutable counterpart of :class:`Assignment`: the
assignment is the plan a method proposes, the state is what actually evolves as
picks consume stock and replenishments deliver it. Everything lives in the index
space of a :class:`SlottingInstance`, so the simulation core stays numpy-only.

Three rules that are easy to get wrong:

- A location at 0 units stays owned while it is the SKU's only one; if the SKU
  owns another, the empty one is released (that is how a relocation frees the
  old slot once its leftovers are picked).
- A SKU may occupy several locations at once, which happens in the data during
  a relocation and can also be a policy's choice.
- A location holds at most one SKU. Per-location capacity is not modeled.
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np
import pandas as pd

FREE = -1


class FreeLocationPool:
    """Set of free location indices with O(1) add/remove/sample.

    Backed by an array-with-positions scheme (remove swaps with the last item),
    which also provides an O(1) array view for vectorized argmin scans.
    """

    def __init__(self, free_indices: Iterable[int]):
        self._items: list[int] = []
        self._pos: dict[int, int] = {}
        for idx in free_indices:
            idx = int(idx)
            if idx in self._pos:
                raise ValueError(f"duplicate free location index {idx}")
            self._pos[idx] = len(self._items)
            self._items.append(idx)

    def add(self, loc_idx: int) -> None:
        loc_idx = int(loc_idx)
        if loc_idx in self._pos:
            raise ValueError(f"location {loc_idx} is already in the free pool")
        self._pos[loc_idx] = len(self._items)
        self._items.append(loc_idx)

    def remove(self, loc_idx: int) -> None:
        loc_idx = int(loc_idx)
        pos = self._pos.pop(loc_idx)  # KeyError if absent: caller bug
        last = self._items.pop()
        if last != loc_idx:
            self._items[pos] = last
            self._pos[last] = pos

    def sample(self, rng: np.random.Generator) -> int:
        if not self._items:
            raise RuntimeError("free location pool is empty")
        return self._items[int(rng.integers(len(self._items)))]

    def as_array(self) -> np.ndarray:
        """Current free indices as an int64 array (copy, safe to reorder)."""
        return np.asarray(self._items, dtype=np.int64)

    def __contains__(self, loc_idx: int) -> bool:
        return int(loc_idx) in self._pos

    def __len__(self) -> int:
        return len(self._items)


class WarehouseState:
    """Mutable stock state: SKU and units per location, in instance index space."""

    def __init__(self, n_skus: int, n_locations: int):
        self._location_sku = np.full(n_locations, FREE, dtype=np.int64)
        self._location_units = np.zeros(n_locations, dtype=np.int64)
        self._sku_locations: list[set[int]] = [set() for _ in range(n_skus)]
        self._free = FreeLocationPool(range(n_locations))

    @property
    def n_skus(self) -> int:
        return len(self._sku_locations)

    @property
    def n_locations(self) -> int:
        return len(self._location_sku)

    # -- queries ------------------------------------------------------------

    def locations_of(self, sku_idx: int) -> frozenset[int]:
        return frozenset(self._sku_locations[sku_idx])

    def sku_at(self, loc_idx: int) -> int:
        """SKU index at a location, or FREE (-1) if the location is free."""
        return int(self._location_sku[loc_idx])

    def units_at(self, loc_idx: int) -> int:
        return int(self._location_units[loc_idx])

    def total_units(self, sku_idx: int) -> int:
        return int(
            sum(self._location_units[loc] for loc in self._sku_locations[sku_idx])
        )

    def is_free(self, loc_idx: int) -> bool:
        return self._location_sku[loc_idx] == FREE

    def free_pool(self) -> FreeLocationPool:
        return self._free

    def primary_location(self, sku_idx: int) -> int:
        """The SKU's location with most units (ties: lowest index); -1 if none."""
        locations = self._sku_locations[sku_idx]
        if not locations:
            return FREE
        return min(locations, key=lambda loc: (-self._location_units[loc], loc))

    # -- mutations ----------------------------------------------------------

    def remove_units(self, sku_idx: int, loc_idx: int, qty: int) -> int:
        """Take up to ``qty`` units of the SKU from a location it owns.

        Returns the units actually taken (clamped at the available stock, never
        negative). The location stays owned by the SKU even at 0 units.
        """
        if qty < 0:
            raise ValueError(f"qty must be >= 0, got {qty}")
        if self._location_sku[loc_idx] != sku_idx:
            raise ValueError(
                f"location {loc_idx} does not hold SKU {sku_idx} "
                f"(holds {int(self._location_sku[loc_idx])})"
            )
        taken = min(qty, int(self._location_units[loc_idx]))
        self._location_units[loc_idx] -= taken
        return taken

    def add_units(self, sku_idx: int, loc_idx: int, qty: int) -> None:
        """Deliver ``qty`` units of the SKU to a location.

        A free location becomes owned by the SKU (even with qty 0, matching the
        initial stock, where a SKU can own a slot at partial or zero level). A
        location owned by another SKU is a hard error: one SKU per location.
        """
        if qty < 0:
            raise ValueError(f"qty must be >= 0, got {qty}")
        owner = int(self._location_sku[loc_idx])
        if owner == FREE:
            self._free.remove(loc_idx)
            self._location_sku[loc_idx] = sku_idx
            self._sku_locations[sku_idx].add(int(loc_idx))
        elif owner != sku_idx:
            raise ValueError(
                f"location {loc_idx} already holds SKU {owner}; "
                f"cannot deliver SKU {sku_idx} there"
            )
        self._location_units[loc_idx] += qty

    def release_empty_locations(
        self, sku_idx: int, keep: int | None = None
    ) -> list[int]:
        """Free the SKU's locations left at 0 units, keeping at least one.

        This is how a relocation opens up the old slot once its leftovers are
        picked. ``keep`` protects a location from being released (the
        destination of a replenishment). The SKU always retains one location,
        so a single home at zero level survives. Returns what was released.
        """
        locations = self._sku_locations[sku_idx]
        candidates = sorted(
            loc
            for loc in locations
            if loc != keep and self._location_units[loc] == 0
        )
        keep_last = len(candidates) == len(locations)
        if keep_last:
            candidates = candidates[1:]

        for loc in candidates:
            locations.discard(loc)
            self._location_sku[loc] = FREE
            self._free.add(loc)
        return candidates

    # -- utilities ----------------------------------------------------------

    def copy(self) -> "WarehouseState":
        clone = WarehouseState.__new__(WarehouseState)
        clone._location_sku = self._location_sku.copy()
        clone._location_units = self._location_units.copy()
        clone._sku_locations = [set(locs) for locs in self._sku_locations]
        clone._free = FreeLocationPool(self._free.as_array())
        return clone

    def check_invariants(self) -> None:
        """Full O(n) consistency check; raises on the first violation."""
        for loc in range(self.n_locations):
            sku = int(self._location_sku[loc])
            if sku == FREE:
                if self._location_units[loc] != 0:
                    raise AssertionError(f"free location {loc} has units")
                if loc not in self._free:
                    raise AssertionError(f"free location {loc} not in pool")
            else:
                if loc in self._free:
                    raise AssertionError(f"occupied location {loc} in free pool")
                if loc not in self._sku_locations[sku]:
                    raise AssertionError(
                        f"location {loc} holds SKU {sku} but is not indexed"
                    )
        indexed = sum(len(locs) for locs in self._sku_locations)
        occupied = int((self._location_sku != FREE).sum())
        if indexed != occupied:
            raise AssertionError(
                f"{indexed} indexed sku-locations vs {occupied} occupied"
            )
        if (self._location_units < 0).any():
            raise AssertionError("negative units")

    def to_frame(self, instance) -> pd.DataFrame:
        """Export as a DataFrame with external ids (pandas boundary)."""
        sku_ids = [
            instance.sku_id(s) if s != FREE else None for s in self._location_sku
        ]
        return pd.DataFrame(
            {
                "location_id": instance.location_ids,
                "sku": sku_ids,
                "units": self._location_units,
            }
        )

    def __repr__(self) -> str:
        occupied = int((self._location_sku != FREE).sum())
        return (
            f"WarehouseState(n_locations={self.n_locations}, occupied={occupied}, "
            f"free={len(self._free)}, total_units={int(self._location_units.sum())})"
        )
