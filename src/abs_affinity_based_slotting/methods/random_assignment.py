"""Random baseline: every SKU in a location drawn at random."""

from __future__ import annotations

import numpy as np

from ..slotting import Assignment, SlottingInstance
from .base import method_registry


@method_registry.register("random")
class RandomSlotting:
    """Each SKU in a different location, drawn uniformly at random.

    Ignores demand, merchant and affinity: it is the plan that uses no data,
    the reference for how much a method gains by using it. ``seed`` fixes the
    draw.
    """

    name = "random"

    def __init__(self, seed: int = 0):
        self.seed = seed

    def solve(self, instance: SlottingInstance) -> Assignment:
        if instance.n_locations < instance.n_skus:
            raise ValueError("more SKUs than locations")
        locations = np.random.default_rng(self.seed).permutation(instance.n_locations)[: instance.n_skus]
        return Assignment({instance.sku_id(s): instance.location_id(l) for s, l in enumerate(locations)})
