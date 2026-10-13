"""Routing policies: how a picker walks through the bays of one batch.

A policy turns the set of bays a batch must visit into a walking distance.
Two are available, selectable by name through ``routing_registry``:

- ``snake``: bays sorted by (aisle, bay number) and joined by shortest paths.
  Between aisles it comes back along the front, so it charges how deep the
  picker goes into each aisle. This is the policy every earlier result used.
- ``s_shape``: strict S-shape. Every aisle holding at least one pick is
  traversed end to end; aisles are visited left to right; with an odd number
  of aisles the picker ends at the back and returns along the last aisle. The
  distance depends only on WHICH aisles are visited.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
import pandas as pd

from ..config import DOCK
from ..registry import Registry
from .routes import bay_snake_keys, route_distance, snake_order


@runtime_checkable
class RoutingPolicy(Protocol):
    name: str

    def distance(self, bays: np.ndarray) -> float:
        """Walking distance dock -> the given bays -> dock (bay indices, any order)."""
        ...


#: name -> RoutingPolicy class. Every class offers ``from_tables(instance, coordinates, *, dock)``.
routing_registry: Registry[type[RoutingPolicy]] = Registry("routing policy")


@routing_registry.register("snake")
class SnakeRouting:
    """Snake order (aisle, then bay number) joined by shortest-path legs."""

    name = "snake"

    def __init__(self, bay_snake_key: np.ndarray, bay_distance: np.ndarray, dock_bay: int):
        self._key = np.asarray(bay_snake_key, dtype=float)
        self._distance = bay_distance
        self._dock = int(dock_bay)

    @classmethod
    def from_tables(cls, instance, coordinates: pd.DataFrame, *, dock: str = DOCK) -> "SnakeRouting":
        return cls(bay_snake_keys(coordinates, instance.bay_ids), instance.bay_distance, instance.bay_index(dock))

    def distance(self, bays: np.ndarray) -> float:
        bays = np.unique(np.asarray(bays, dtype=np.int64))
        return route_distance(snake_order(bays, self._key[bays]), self._distance, self._dock)


@routing_registry.register("s_shape")
class SShapeRouting:
    """Strict S-shape over parallel aisles of equal length.

    Aisles are numbered by position ``0..n_aisles-1`` from left to right. For a
    visited set ``a_1 < ... < a_m``::

        R_S = d0(a_1) + m * L + sum_k |x(a_{k+1}) - x(a_k)| + [m odd] * L + d0(a_m)

    with ``L`` the aisle length, ``x(a)`` the aisle centre and
    ``d0(a) = |x(a) - x_dock| + (y_front - y_dock)`` the walk from the dock to
    the front of aisle ``a``.
    """

    name = "s_shape"

    def __init__(
        self,
        bay_aisle: np.ndarray,
        aisle_x: np.ndarray,
        aisle_length: float,
        front_y: float,
        dock_xy: tuple[float, float],
    ):
        self.bay_aisle = np.asarray(bay_aisle, dtype=np.int64)   # aisle position per bay, -1 for the dock
        self.aisle_x = np.asarray(aisle_x, dtype=float)
        self.aisle_length = float(aisle_length)
        self.front_y = float(front_y)
        self.dock_xy = (float(dock_xy[0]), float(dock_xy[1]))
        if self.n_aisles > 24:
            raise ValueError(f"s_shape supports up to 24 aisles (bit masks), got {self.n_aisles}")

    @classmethod
    def from_tables(cls, instance, coordinates: pd.DataFrame, *, dock: str = DOCK) -> "SShapeRouting":
        """Geometry from the coordinates table, aligned with ``instance.bay_ids``."""
        coord = coordinates.set_index("bay_id")
        bays = coordinates.dropna(subset=["aisle"]).copy()
        bays["aisle"] = bays["aisle"].astype(int)

        y_range = bays.groupby("aisle")["y"].agg(["min", "max"])
        if y_range["min"].nunique() != 1 or y_range["max"].nunique() != 1:
            raise ValueError("s_shape assumes every aisle spans the same y range")

        aisle_numbers = np.sort(bays["aisle"].unique())
        position = {a: k for k, a in enumerate(aisle_numbers)}
        aisle_x = bays.groupby("aisle")["x"].mean().reindex(aisle_numbers).to_numpy(dtype=float)

        y0, y1 = float(bays["y"].min()), float(bays["y"].max())
        pitch = float(np.min(np.diff(np.sort(bays["y"].unique()))))
        aisle_number_per_bay = coord["aisle"].reindex(instance.bay_ids)
        bay_aisle = np.array([-1 if pd.isna(a) else position[int(a)] for a in aisle_number_per_bay], dtype=np.int64)
        dock_xy = tuple(coord.loc[dock, ["x", "y"]].to_numpy(dtype=float))
        return cls(bay_aisle, aisle_x, y1 - y0 + pitch, y0, dock_xy)

    @property
    def n_aisles(self) -> int:
        return len(self.aisle_x)

    def _to_front(self, aisle: int) -> float:
        return abs(self.aisle_x[aisle] - self.dock_xy[0]) + (self.front_y - self.dock_xy[1])

    def distance_of_aisles(self, aisles) -> float:
        """R_S for a set of aisle positions (any order, repetitions allowed)."""
        visited = np.unique(np.asarray(aisles, dtype=np.int64))
        m = len(visited)
        if m == 0:
            return 0.0
        lateral = float(np.abs(np.diff(self.aisle_x[visited])).sum())
        back_to_front = self.aisle_length if m % 2 == 1 else 0.0
        return self._to_front(visited[0]) + m * self.aisle_length + lateral + back_to_front + self._to_front(visited[-1])

    def distance(self, bays: np.ndarray) -> float:
        aisles = self.bay_aisle[np.asarray(bays, dtype=np.int64)]
        return self.distance_of_aisles(aisles[aisles >= 0])

    def mask_costs(self) -> np.ndarray:
        """R_S of every subset of aisles, indexed by bit mask (bit ``a`` = aisle position ``a``)."""
        n = self.n_aisles
        masks = np.arange(1 << n, dtype=np.int64)
        bits = ((masks[:, None] >> np.arange(n)) & 1).astype(bool)          # bits[mask, a]
        m = bits.sum(axis=1)
        first = np.where(m > 0, bits.argmax(axis=1), 0)
        last = np.where(m > 0, n - 1 - bits[:, ::-1].argmax(axis=1), 0)
        to_front = np.abs(self.aisle_x - self.dock_xy[0]) + (self.front_y - self.dock_xy[1])
        # aisles are sorted left to right, so the lateral walk is x(last) - x(first)
        lateral = self.aisle_x[last] - self.aisle_x[first]
        cost = to_front[first] + m * self.aisle_length + lateral + np.where(m % 2 == 1, self.aisle_length, 0.0) + to_front[last]
        cost[0] = 0.0
        return cost
