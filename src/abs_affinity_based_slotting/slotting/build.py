"""Build a :class:`SlottingInstance` from the processed pandas tables.

This is the boundary between the pandas data layer and the numerical
optimization core: the only place that knows the processed table layout. The
resulting instance is purely numerical (NumPy / SciPy).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

from .instance import SlottingInstance


def build_instance(
    sku_demand: pd.DataFrame,
    location_costs: pd.DataFrame,
    bay_distance: pd.DataFrame,
    *,
    skus: np.ndarray | pd.Index | None = None,
    demand_metric: str = "pick_lines",
    cost_col: str = "distance_to_dock_in",
    affinity: csr_matrix | None = None,
) -> SlottingInstance:
    """Assemble a slotting instance.

    Parameters
    ----------
    sku_demand:
        Per-SKU demand table (columns ``sku``, ``merchant_account_id`` and the
        chosen ``demand_metric``).
    location_costs:
        Per-location table (columns ``location_id``, ``bay_id`` and ``cost_col``).
    bay_distance:
        Symmetric bay-by-bay distance matrix, indexed and columned by bay id.
    skus:
        SKU universe to place. Defaults to every SKU in ``sku_demand``. SKUs in
        the universe without recorded demand get demand 0.
    affinity:
        SKU-SKU affinity as a CSR matrix aligned with ``skus``. Defaults to an
        empty matrix (no affinity built yet).
    """
    demand_by_sku = sku_demand.set_index("sku")
    sku_ids = (
        demand_by_sku.index.to_numpy() if skus is None else np.asarray(skus)
    )
    demand = (
        demand_by_sku[demand_metric].reindex(sku_ids, fill_value=0).to_numpy(dtype=float)
    )
    merchant_ids = demand_by_sku["merchant_account_id"].reindex(sku_ids).to_numpy()

    # Bay order is defined by the distance matrix; locations map into it.
    bay_ids = bay_distance.index.to_numpy()
    bay_matrix = bay_distance.loc[bay_ids, bay_ids].to_numpy(dtype=float)
    bay_to_idx = {bay: idx for idx, bay in enumerate(bay_ids)}

    location_ids = location_costs["location_id"].to_numpy()
    location_cost = location_costs[cost_col].to_numpy(dtype=float)
    loc_bays = location_costs["bay_id"]
    unknown = set(loc_bays.unique()) - bay_to_idx.keys()
    if unknown:
        raise ValueError(
            f"{len(unknown)} location bays missing from bay_distance, "
            f"e.g. {next(iter(unknown))!r}"
        )
    location_bay = loc_bays.map(bay_to_idx).to_numpy(dtype=int)

    if affinity is None:
        affinity = csr_matrix((len(sku_ids), len(sku_ids)))

    return SlottingInstance(
        sku_ids=sku_ids,
        location_ids=location_ids,
        bay_ids=bay_ids,
        demand=demand,
        location_cost=location_cost,
        location_bay=location_bay,
        bay_distance=bay_matrix,
        affinity=affinity,
        merchant_ids=merchant_ids,
    )
