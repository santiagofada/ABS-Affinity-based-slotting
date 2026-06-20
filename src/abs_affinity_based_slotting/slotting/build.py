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
    initial_stock: pd.DataFrame | None = None,
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
    initial_stock:
        Initial stock table (for merchant assignment). If provided, merchant comes
        from here (covers all SKUs); otherwise from sku_demand (may have NaN for
        SKUs not in train).
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

    if initial_stock is not None:
        merchant_by_sku = initial_stock.drop_duplicates(subset=["sku"]).set_index("sku")["merchant_account_id"]
        merchant_ids = merchant_by_sku.reindex(sku_ids).to_numpy()
    else:
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


def build_instance_canonical(
    picking_train: pd.DataFrame,
    initial_stock: pd.DataFrame,
    distances: pd.DataFrame,
    *,
    affinity_metric: str = "jaccard",
) -> SlottingInstance:
    """Build the canonical problem instance for the entire SKU universe.

    Produces a SlottingInstance covering all 27k occupied SKUs:
    - Universe: all SKUs in initial_stock
    - Demand f: from picking_train (cold-start SKUs get f=0)
    - Merchant: from initial_stock (complete coverage)
    - Affinity A: co-occurrence from picking_train, aligned to the universe
    - Warehouse (c, D): from initial_stock and distances

    This is the single entry point for building the canonical problem.
    """
    from ..warehouse import (
        occupied_locations,
        build_location_costs,
        build_bay_distance_matrix,
    )
    from ..demand import build_cooccurrence, affinity_registry, build_sku_demand

    universe = occupied_locations(initial_stock)["sku"].to_numpy()

    co = build_cooccurrence(picking_train, skus=universe)
    A = affinity_registry.get(affinity_metric)().build(
        co.matrix, co.support, co.n_batches
    )
    sku_demand = build_sku_demand(picking_train)
    location_costs = build_location_costs(initial_stock, distances)
    bay_distance = build_bay_distance_matrix(distances)

    return build_instance(
        sku_demand,
        location_costs,
        bay_distance,
        initial_stock=initial_stock,
        skus=universe,
        affinity=A,
    )


def restrict_instance(
    instance: SlottingInstance,
    sku_indices: np.ndarray,
    location_indices: np.ndarray,
) -> SlottingInstance:
    """Return a sub-instance over a subset of SKUs and locations.

    Used by the bi-level method to turn each cluster's zone into a standalone
    instance, so any SlottingMethod can solve it unchanged. The bay layout
    (``bay_ids``, ``bay_distance``) is kept whole; only SKUs and locations are
    subset, and the affinity is the corresponding symmetric submatrix.

    Parameters
    ----------
    instance : SlottingInstance
    sku_indices : np.ndarray
        Indices of the SKUs to keep.
    location_indices : np.ndarray
        Indices of the locations to keep (must be at least as many as SKUs).
    """
    sku_indices = np.asarray(sku_indices)
    location_indices = np.asarray(location_indices)

    sub_affinity = instance.affinity[sku_indices][:, sku_indices]
    merchant = (
        None if instance.merchant_ids is None else instance.merchant_ids[sku_indices]
    )

    return SlottingInstance(
        sku_ids=instance.sku_ids[sku_indices],
        location_ids=instance.location_ids[location_indices],
        bay_ids=instance.bay_ids,
        demand=instance.demand[sku_indices],
        location_cost=instance.location_cost[location_indices],
        location_bay=instance.location_bay[location_indices],
        bay_distance=instance.bay_distance,
        affinity=sub_affinity,
        merchant_ids=merchant,
    )
