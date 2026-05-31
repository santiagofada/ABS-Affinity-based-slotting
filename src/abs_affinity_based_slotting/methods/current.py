"""Baseline: the warehouse's current slotting (a static snapshot).

This is not a computed strategy: the placement is *read* from ``initial_stock``
(the SKU that each location holds at the start of the history). It is the main
benchmark every other method is compared against.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..slotting import Assignment, SlottingInstance
from ..warehouse import occupied_locations
from .base import method_registry


def current_assignment(
    initial_stock: pd.DataFrame,
    *,
    skus: np.ndarray | pd.Index | None = None,
) -> Assignment:
    """Build the current SKU -> location assignment from ``initial_stock``.

    Only occupied locations contribute. If ``skus`` is given, the assignment is
    restricted to that SKU universe.
    """
    occupied = occupied_locations(initial_stock)
    if skus is not None:
        occupied = occupied[occupied["sku"].isin(skus)]
    return Assignment.from_frame(occupied, sku_col="sku", location_col="location_id")


@method_registry.register("current")
class CurrentSlotting:
    """The current slotting as a :class:`SlottingMethod`.

    Carries the snapshot (``initial_stock``); ``solve`` just reads it, restricted
    to the instance's SKU universe.
    """

    name = "current"

    def __init__(self, initial_stock: pd.DataFrame):
        self._initial_stock = initial_stock

    def solve(self, instance: SlottingInstance) -> Assignment:
        return current_assignment(self._initial_stock, skus=instance.sku_ids)
