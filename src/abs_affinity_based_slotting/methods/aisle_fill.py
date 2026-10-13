"""Fill the warehouse aisle by aisle instead of by distance to the dock.

Under strict S-shape routing a picker that enters an aisle walks all of it, so
what matters is which aisles a batch enters, not how deep. Both rules here sort
locations by (aisle, distance to the dock), aisles ordered by how cheap they are
to reach, and fill them in that order:

- ``aisle_fill``: SKUs by demand, descending. Concentrates the popular SKUs in
  the first aisles.
- ``merchant_aisle_fill``: merchants by total demand, descending, and inside
  each merchant its SKUs by demand. Every merchant ends up in one aisle (or two
  contiguous ones), so a single-merchant order touches one aisle.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..slotting import Assignment, SlottingInstance
from .base import method_registry


def aisle_fill_location_order(instance: SlottingInstance, coordinates: pd.DataFrame) -> np.ndarray:
    """Location indices sorted by (aisle rank, location cost).

    An aisle's rank is its cheapest location (its front, the closest to the dock).
    """
    aisle_of_bay = coordinates.set_index("bay_id")["aisle"].reindex(instance.bay_ids).to_numpy(dtype=float)
    location_aisle = aisle_of_bay[instance.location_bay]
    if np.isnan(location_aisle).any():
        raise ValueError("some storage locations have no aisle in the coordinates table")
    front_cost = pd.Series(instance.location_cost).groupby(location_aisle).min()
    aisle_rank = front_cost.rank(method="first").reindex(location_aisle).to_numpy()
    return np.lexsort((np.arange(instance.n_locations), instance.location_cost, aisle_rank))


def _assign_in_order(instance: SlottingInstance, sku_order: np.ndarray, location_order: np.ndarray) -> Assignment:
    if len(location_order) < len(sku_order):
        raise ValueError("more SKUs than locations")
    return Assignment({instance.sku_id(s): instance.location_id(l) for s, l in zip(sku_order, location_order)})


@method_registry.register("aisle_fill")
class AisleFillSlotting:
    """Most demanded SKUs into the first aisles, filling one aisle before the next."""

    name = "aisle_fill"

    def __init__(self, coordinates: pd.DataFrame):
        self._coordinates = coordinates

    def solve(self, instance: SlottingInstance) -> Assignment:
        sku_order = np.argsort(-instance.demand, kind="stable")
        return _assign_in_order(instance, sku_order, aisle_fill_location_order(instance, self._coordinates))


@method_registry.register("merchant_aisle_fill")
class MerchantAisleFillSlotting:
    """Same location order, SKUs grouped by merchant (merchants by total demand)."""

    name = "merchant_aisle_fill"

    def __init__(self, coordinates: pd.DataFrame):
        self._coordinates = coordinates

    def solve(self, instance: SlottingInstance) -> Assignment:
        if instance.merchant_ids is None:
            raise ValueError("merchant_aisle_fill requires instance.merchant_ids")
        merchant = pd.Series(instance.merchant_ids)
        merchant_demand = pd.Series(instance.demand).groupby(merchant).sum()
        merchant_rank = merchant.map(merchant_demand.rank(ascending=False, method="first")).to_numpy()
        sku_order = np.lexsort((np.arange(instance.n_skus), -instance.demand, merchant_rank))
        return _assign_in_order(instance, sku_order, aisle_fill_location_order(instance, self._coordinates))
