"""Slotting problem instance.

A ``SlottingInstance`` contains the fixed data needed to build, score, and
compare slotting assignments.

It does not represent a solution. A solution is represented by ``Assignment``.
The instance is immutable: methods and heuristics should read from it and
return assignments without modifying the instance itself.
"""
"""Slotting problem instance.

A SlottingInstance stores the fixed numerical data needed to evaluate and
solve one warehouse slotting problem.

External identifiers such as SKU ids, location ids and bay ids are kept for
interpretability. Internally, the instance uses integer positions and NumPy /
SciPy objects, which are more convenient for objective functions and heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable

import numpy as np
from scipy.sparse import csr_matrix, issparse

SkuId = Hashable
LocationId = Hashable
BayId = Hashable


@dataclass(frozen=True, eq=False, repr=False)
class SlottingInstance:
    """Numerical representation of one slotting instance.

    Parameters
    ----------
    sku_ids:
        SKU identifiers. Position i in this array corresponds to SKU i.
    location_ids:
        Location identifiers. Position l in this array corresponds to location l.
    bay_ids:
        Bay identifiers. Position b in this array corresponds to bay b.
    demand:
        Demand weight per SKU. Shape: (n_skus,).
    location_cost:
        Access cost per location, usually distance to the dock. Shape:
        (n_locations,).
    location_bay:
        Bay index for each location. Shape: (n_locations,).
    bay_distance:
        Walking distance between bays. Shape: (n_bays, n_bays).
    affinity:
        SKU-SKU affinity matrix. Shape: (n_skus, n_skus). Stored as CSR sparse
        matrix.
    merchant_ids:
        Optional merchant identifier per SKU. Shape: (n_skus,).

    Notes
    -----
    This class does not represent a solution. A solution is represented by an
    Assignment.

    Distances are kept in the unit used by the source data, currently inches.
    Convert to meters only when reporting results.
    """

    sku_ids: np.ndarray
    location_ids: np.ndarray
    bay_ids: np.ndarray

    demand: np.ndarray
    location_cost: np.ndarray
    location_bay: np.ndarray
    bay_distance: np.ndarray
    affinity: csr_matrix

    merchant_ids: np.ndarray | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "sku_ids", np.asarray(self.sku_ids, dtype=object))
        object.__setattr__(
            self,
            "location_ids",
            np.asarray(self.location_ids, dtype=object),
        )
        object.__setattr__(self, "bay_ids", np.asarray(self.bay_ids, dtype=object))

        object.__setattr__(self, "demand", np.asarray(self.demand, dtype=float))
        object.__setattr__(
            self,
            "location_cost",
            np.asarray(self.location_cost, dtype=float),
        )
        object.__setattr__(
            self,
            "location_bay",
            np.asarray(self.location_bay, dtype=int),
        )
        object.__setattr__(
            self,
            "bay_distance",
            np.asarray(self.bay_distance, dtype=float),
        )

        if not issparse(self.affinity):
            affinity = csr_matrix(self.affinity)
        else:
            affinity = self.affinity.tocsr()

        object.__setattr__(self, "affinity", affinity)

        if self.merchant_ids is not None:
            merchant_ids = np.asarray(self.merchant_ids, dtype=object)
            object.__setattr__(self, "merchant_ids", merchant_ids)

        self._validate()
        self._build_indexes()

    def _validate(self) -> None:
        self._validate_ids()
        self._validate_shapes()
        self._validate_values()

    def _validate_ids(self) -> None:
        if len(set(self.sku_ids)) != len(self.sku_ids):
            raise ValueError("sku_ids contains duplicated values.")

        if len(set(self.location_ids)) != len(self.location_ids):
            raise ValueError("location_ids contains duplicated values.")

        if len(set(self.bay_ids)) != len(self.bay_ids):
            raise ValueError("bay_ids contains duplicated values.")

    def _validate_shapes(self) -> None:
        if self.demand.shape != (self.n_skus,):
            raise ValueError(
                f"demand must have shape ({self.n_skus},), "
                f"got {self.demand.shape}."
            )

        if self.location_cost.shape != (self.n_locations,):
            raise ValueError(
                f"location_cost must have shape ({self.n_locations},), "
                f"got {self.location_cost.shape}."
            )

        if self.location_bay.shape != (self.n_locations,):
            raise ValueError(
                f"location_bay must have shape ({self.n_locations},), "
                f"got {self.location_bay.shape}."
            )

        if self.bay_distance.shape != (self.n_bays, self.n_bays):
            raise ValueError(
                f"bay_distance must have shape ({self.n_bays}, {self.n_bays}), "
                f"got {self.bay_distance.shape}."
            )

        if self.affinity.shape != (self.n_skus, self.n_skus):
            raise ValueError(
                f"affinity must have shape ({self.n_skus}, {self.n_skus}), "
                f"got {self.affinity.shape}."
            )

        if self.merchant_ids is not None and self.merchant_ids.shape != (self.n_skus,):
            raise ValueError(
                f"merchant_ids must have shape ({self.n_skus},), "
                f"got {self.merchant_ids.shape}."
            )

        if self.n_locations < self.n_skus:
            raise ValueError(
                f"Infeasible instance: {self.n_skus} SKUs but only "
                f"{self.n_locations} locations."
            )

    def _validate_values(self) -> None:
        if np.isnan(self.demand).any():
            raise ValueError("demand contains NaN values.")

        if np.isnan(self.location_cost).any():
            raise ValueError("location_cost contains NaN values.")

        if np.isnan(self.bay_distance).any():
            raise ValueError("bay_distance contains NaN values.")

        if (self.demand < 0).any():
            raise ValueError("demand must be non-negative.")

        if (self.location_cost < 0).any():
            raise ValueError("location_cost must be non-negative.")

        if (self.bay_distance < 0).any():
            raise ValueError("bay_distance must be non-negative.")

        if self.location_bay.min(initial=0) < 0:
            raise ValueError("location_bay contains negative bay indexes.")

        if self.location_bay.max(initial=0) >= self.n_bays:
            raise ValueError("location_bay contains indexes outside bay_ids.")

    def _build_indexes(self) -> None:
        sku_to_idx = {sku: idx for idx, sku in enumerate(self.sku_ids)}
        location_to_idx = {loc: idx for idx, loc in enumerate(self.location_ids)}
        bay_to_idx = {bay: idx for idx, bay in enumerate(self.bay_ids)}

        object.__setattr__(self, "_sku_to_idx", sku_to_idx)
        object.__setattr__(self, "_location_to_idx", location_to_idx)
        object.__setattr__(self, "_bay_to_idx", bay_to_idx)

    @property
    def n_skus(self) -> int:
        return len(self.sku_ids)

    @property
    def n_locations(self) -> int:
        return len(self.location_ids)

    @property
    def n_bays(self) -> int:
        return len(self.bay_ids)

    def sku_index(self, sku_id: SkuId) -> int:
        """Return internal integer index for a SKU id."""
        return self._sku_to_idx[sku_id]

    def location_index(self, location_id: LocationId) -> int:
        """Return internal integer index for a location id."""
        return self._location_to_idx[location_id]

    def bay_index(self, bay_id: BayId) -> int:
        """Return internal integer index for a bay id."""
        return self._bay_to_idx[bay_id]

    def location_id(self, location_idx: int) -> LocationId:
        """Return external location id from internal location index."""
        return self.location_ids[location_idx]

    def sku_id(self, sku_idx: int) -> SkuId:
        """Return external SKU id from internal SKU index."""
        return self.sku_ids[sku_idx]

    def bay_id(self, bay_idx: int) -> BayId:
        """Return external bay id from internal bay index."""
        return self.bay_ids[bay_idx]

    def bay_of_location_index(self, location_idx: int) -> int:
        """Return bay index of a location index."""
        return int(self.location_bay[location_idx])

    def cost_of_location_index(self, location_idx: int) -> float:
        """Return access cost of a location index."""
        return float(self.location_cost[location_idx])

    def distance_between_location_indices(
        self,
        location_a: int,
        location_b: int,
    ) -> float:
        """Return walking distance between two location indices."""
        bay_a = self.location_bay[location_a]
        bay_b = self.location_bay[location_b]

        return float(self.bay_distance[bay_a, bay_b])

    def affinity_between_sku_indices(
        self,
        sku_a: int,
        sku_b: int,
    ) -> float:
        """Return affinity score between two SKU indices."""
        return float(self.affinity[sku_a, sku_b])

    def __repr__(self) -> str:
        return (
            "SlottingInstance("
            f"n_skus={self.n_skus}, "
            f"n_locations={self.n_locations}, "
            f"n_bays={self.n_bays}, "
            f"affinity_edges={self.affinity.nnz}"
            ")"
        )