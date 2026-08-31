"""Contract for replenishment policies (where the slotting algorithm acts).

A replenishment policy is consulted on EVERY replenishment event and decides
where the delivered units land. Refilling the SKU's current location is just
one more decision the policy can make. This is the single endogenous decision
of the simulation: everything else (what is picked when, when a replen happens
and how many units it brings) is replayed from the data.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np

from ..registry import Registry
from ..slotting import SlottingInstance
from .events import ReplenEvent
from .state import WarehouseState


@dataclass(frozen=True)
class SimulationContext:
    """Everything a policy may consult besides the state.

    Attributes
    ----------
    instance:
        Problem data: demand f, access cost c, affinity A, distances D.
    planned_location:
        Location index assigned to each SKU by the slotting method whose plan
        is being simulated, aligned with ``instance.sku_ids``; None when there
        is no plan (e.g. the current-layout baseline).
    lam:
        Objective weight, for policies that optimize the surrogate cost.
    rng:
        The single source of randomness of the run (reproducibility).
    """

    instance: SlottingInstance
    planned_location: np.ndarray | None
    lam: float
    rng: np.random.Generator


@runtime_checkable
class ReplenishmentPolicy(Protocol):
    name: str

    def choose_destination(
        self,
        event: ReplenEvent,
        state: WarehouseState,
        context: SimulationContext,
    ) -> int:
        """Return the location index where the units land.

        Must be a location that is free or already owned by ``event.sku_idx``;
        the simulator validates the return value and raises otherwise.
        """
        ...


#: name -> ReplenishmentPolicy subclass.
replenishment_policy_registry: Registry[type[ReplenishmentPolicy]] = Registry(
    "replenishment policy"
)
