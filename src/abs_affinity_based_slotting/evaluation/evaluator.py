"""Score an :class:`Assignment` by simulating picking routes over test batches.

The evaluator is independent of the method that produced the assignment. For
each test batch it re-routes the picks through the locations the assignment
proposes, in snake order (by aisle then bay number), and sums the walking
distance dock -> picks -> dock.

Coverage is an invariant, not a policy: every SKU picked in test must be placed
by the assignment. A missing SKU is a bug and raises, never silently skipped.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import DOCK
from ..slotting import Assignment
from ..warehouse import build_bay_distance_matrix
from .metrics import RouteMetrics, summarize_route_costs
from .routes import route_distance, snake_order


class Evaluator:
    def __init__(
        self,
        location_to_bay: dict,
        bay_distance: np.ndarray,
        bay_sort_key: np.ndarray,
        dock: int,
    ):
        self._loc_to_bay = location_to_bay  # location_id -> bay index
        self._bay_distance = bay_distance
        self._bay_sort_key = bay_sort_key
        self._dock = dock

    @classmethod
    def from_tables(
        cls,
        coordinates: pd.DataFrame,
        distances: pd.DataFrame,
        locations: pd.DataFrame,
        *,
        dock: str = DOCK,
    ) -> "Evaluator":
        """Build the evaluator's geometry from the raw layout tables.

        ``locations`` must map ``location_id`` to ``bay_id`` (e.g. initial_stock).
        """
        bay_dist = build_bay_distance_matrix(distances)
        bay_ids = bay_dist.index.to_numpy()
        bay_to_idx = {bay: idx for idx, bay in enumerate(bay_ids)}

        coord = coordinates.set_index("bay_id").reindex(bay_ids)
        aisle = coord["aisle"].astype(float).to_numpy()
        bay_number = coord["bay_number"].astype(float).to_numpy()
        # Snake order = (aisle, bay_number); the dock is only an endpoint, so its
        # key is irrelevant (NaN -> -1, never inside a pick sequence).
        sort_key = np.nan_to_num(aisle * 1000.0 + bay_number, nan=-1.0)

        loc_to_bay = {
            loc: bay_to_idx[bay]
            for loc, bay in zip(locations["location_id"], locations["bay_id"])
        }
        return cls(loc_to_bay, bay_dist.to_numpy(dtype=float), sort_key, bay_to_idx[dock])

    def evaluate(
        self,
        assignment: Assignment,
        picking_test: pd.DataFrame,
        *,
        batch_col: str = "batch_id",
        sku_col: str = "sku",
    ) -> RouteMetrics:
        missing = set(picking_test[sku_col].unique()) - set(assignment.skus)
        if missing:
            raise ValueError(
                f"{len(missing)} test SKUs are not placed by the assignment, "
                f"e.g. {next(iter(missing))!r}"
            )

        costs = [
            self._batch_cost(group[sku_col].unique(), assignment)
            for _, group in picking_test.groupby(batch_col, sort=False)
        ]
        return summarize_route_costs(costs)

    def _batch_cost(self, skus: np.ndarray, assignment: Assignment) -> float:
        bays = np.fromiter(
            (self._loc_to_bay[assignment.location_of(sku)] for sku in skus),
            dtype=int,
            count=len(skus),
        )
        ordered = snake_order(bays, self._bay_sort_key[bays])
        return route_distance(ordered, self._bay_distance, self._dock)
