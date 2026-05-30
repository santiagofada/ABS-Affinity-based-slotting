"""The problem to solve: immutable data for one slotting instance.

A :class:`SlottingInstance` bundles everything a method needs to produce and
score an assignment, and nothing else. It is read-only; methods consume it and
return an :class:`Assignment`, they never mutate it.

Units: distances are kept in their native unit (inches); convert to meters only
when reporting.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass(frozen=True, eq=False, repr=False)
class SlottingInstance:
    demand: pd.Series          # index = sku; defines the SKU universe
    location_cost: pd.Series   # index = location_id; access cost (to dock)
    location_bay: pd.Series    # index = location_id; value = bay_id
    bay_distance: pd.DataFrame  # symmetric bay-by-bay distances
    affinity: Any | None = None        # SKU-SKU affinity, built later
    merchant: pd.Series | None = None  # index = sku; owning merchant

    def __post_init__(self) -> None:
        if not self.demand.index.is_unique:
            raise ValueError("demand has duplicate SKUs in its index")
        if not self.location_cost.index.is_unique:
            raise ValueError("location_cost has duplicate locations in its index")
        if not self.location_cost.index.equals(self.location_bay.index):
            raise ValueError("location_cost and location_bay must share the same index")
        if self.n_locations < self.n_skus:
            raise ValueError(
                f"infeasible: {self.n_skus} SKUs but only {self.n_locations} locations"
            )
        unknown = set(self.location_bay.unique()) - set(self.bay_distance.index)
        if unknown:
            raise ValueError(f"{len(unknown)} bays missing from bay_distance, e.g. {next(iter(unknown))!r}")

    # --- universes ---

    @property
    def skus(self) -> pd.Index:
        return self.demand.index

    @property
    def locations(self) -> pd.Index:
        return self.location_cost.index

    @property
    def n_skus(self) -> int:
        return len(self.demand)

    @property
    def n_locations(self) -> int:
        return len(self.location_cost)

    # --- geometry ---

    def distance(self, loc_a, loc_b) -> float:
        """Walking distance between two locations, via their bays."""
        bay_a = self.location_bay.at[loc_a]
        bay_b = self.location_bay.at[loc_b]
        return float(self.bay_distance.at[bay_a, bay_b])

    # --- construction ---

    @classmethod
    def from_tables(
        cls,
        sku_demand: pd.DataFrame,
        location_costs: pd.DataFrame,
        bay_distance: pd.DataFrame,
        *,
        skus: np.ndarray | pd.Index | None = None,
        demand_metric: str = "pick_lines",
        cost_col: str = "distance_to_dock_in",
    ) -> "SlottingInstance":
        """Assemble an instance from the processed tables.

        The SKU universe is ``skus`` if given, else every SKU in ``sku_demand``.
        SKUs in the universe without recorded demand get demand 0.
        """
        demand_by_sku = sku_demand.set_index("sku")
        universe = pd.Index(skus) if skus is not None else demand_by_sku.index

        demand = demand_by_sku[demand_metric].reindex(universe, fill_value=0)
        merchant = demand_by_sku["merchant_account_id"].reindex(universe)

        costs = location_costs.set_index("location_id")
        return cls(
            demand=demand,
            location_cost=costs[cost_col],
            location_bay=costs["bay_id"],
            bay_distance=bay_distance,
            merchant=merchant,
        )

    def __repr__(self) -> str:
        return (
            f"SlottingInstance(skus={self.n_skus}, locations={self.n_locations}, "
            f"affinity={'set' if self.affinity is not None else 'none'})"
        )
