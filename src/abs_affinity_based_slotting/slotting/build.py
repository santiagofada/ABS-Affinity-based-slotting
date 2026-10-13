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
    normalize: bool = False,
    pair_distance: pd.DataFrame | None = None,
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
    normalize:
        If True, divide the demand vector by its sum and the affinity matrix by
        its sum, so both become shares. The linear term of the objective is
        then the mean dock distance of a pick and the quadratic term the mean
        distance between an affine pair, both in inches, and ``lam`` weighs two
        comparable quantities. Without it the two terms differ by orders of
        magnitude (picks x inches vs. an affinity score x inches). Applied to
        the affinity as given, so filter before building the instance.
    pair_distance:
        Optional bay-by-bay matrix (same index/columns as ``bay_distance``)
        that the quadratic term charges between two products. Built by a model
        from ``distance_registry`` (``walking`` reproduces ``bay_distance``,
        ``aisle`` charges per aisle entered as S-shape routing does). None
        keeps the physical walking distance.
    """
    demand_by_sku = sku_demand.set_index("sku")
    sku_ids = (
        demand_by_sku.index.to_numpy() if skus is None else np.asarray(skus)
    )
    demand = (
        demand_by_sku[demand_metric].reindex(sku_ids, fill_value=0).to_numpy(dtype=float)
    )
    if normalize and demand.sum() > 0:
        demand = demand / demand.sum()

    if initial_stock is not None:
        merchant_by_sku = initial_stock.drop_duplicates(subset=["sku"]).set_index("sku")["merchant_account_id"]
        merchant_ids = merchant_by_sku.reindex(sku_ids).to_numpy()
    else:
        merchant_ids = demand_by_sku["merchant_account_id"].reindex(sku_ids).to_numpy()

    # Bay order is defined by the distance matrix; locations map into it.
    bay_ids = bay_distance.index.to_numpy()
    bay_matrix = bay_distance.loc[bay_ids, bay_ids].to_numpy(dtype=float)
    bay_to_idx = {bay: idx for idx, bay in enumerate(bay_ids)}
    pair_matrix = (
        None if pair_distance is None
        else pair_distance.loc[bay_ids, bay_ids].to_numpy(dtype=float)
    )

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
    elif normalize and affinity.sum() > 0:
        affinity = (affinity / affinity.sum()).tocsr()

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
        pair_distance=pair_matrix,
    )


def build_full_instance(
    picking_train: pd.DataFrame,
    initial_stock: pd.DataFrame,
    distances: pd.DataFrame,
    *,
    affinity_metric: str = "jaccard",
    cooccurrence_col: str = "batch_id",
    affinity_filter=None,
    normalize: bool = False,
    pair_distance_model: str = "walking",
    coordinates: pd.DataFrame | None = None,
    demand_metric: str = "pick_lines",
) -> SlottingInstance:
    """Build the canonical problem instance for the entire SKU universe.

    - Universe: all SKUs in initial_stock
    - Demand f: from picking_train (cold-start SKUs get f=0)
    - Merchant: from initial_stock (complete coverage)
    - Affinity A: co-occurrence from picking_train, aligned to the universe
    - Warehouse (c, D): from initial_stock and distances

    Parameters
    ----------
    affinity_metric:
        Name in ``affinity_registry`` (``jaccard``, ``cosine``, ``cooccurrence``).
    cooccurrence_col:
        Column of ``picking_train`` that defines when two SKUs co-occur. The
        batch (a picking trip) is the only unit available in the v1 dataset;
        with v2 the customer order (``"order_id"``) is observable too.
    affinity_filter:
        An ``AffinityFilter`` (e.g. ``TopKFilter(k=10)``) applied to A before
        building the instance. None keeps every nonzero pair, which is dense
        for large warehouses.
    normalize:
        Passed to :func:`build_instance`: turn demand and affinity into shares
        so the two objective terms are comparable.
    pair_distance_model:
        Name in ``distance_registry`` of the distance the quadratic term
        charges: ``walking`` (physical path between bays, the default) or
        ``aisle`` (per aisle entered, as S-shape routing costs). Models other
        than ``walking`` need ``coordinates``.
    coordinates:
        The ``coordinates`` table, required by distance models that use the
        layout (aisle, x, y).
    demand_metric:
        Column of :func:`build_sku_demand` used as the demand f:
        ``pick_lines`` (default), ``unique_orders``, ``unique_batches`` or
        ``total_units``.

    This is the single entry point for building the canonical problem.
    """
    from ..warehouse import (
        occupied_locations,
        build_location_costs,
        build_bay_distance_matrix,
        distance_registry,
    )
    from ..demand import build_cooccurrence, affinity_registry, build_sku_demand

    universe = occupied_locations(initial_stock)["sku"].to_numpy()

    co = build_cooccurrence(picking_train, skus=universe, batch_col=cooccurrence_col)
    A = affinity_registry.get(affinity_metric)().build(
        co.matrix, co.support, co.n_batches
    )
    if affinity_filter is not None:
        A = affinity_filter.filter(A)
    sku_demand = build_sku_demand(picking_train)
    location_costs = build_location_costs(initial_stock, distances)
    bay_distance = build_bay_distance_matrix(distances)

    pair_distance = None
    if pair_distance_model != "walking":
        if coordinates is None:
            raise ValueError(
                f"pair_distance_model={pair_distance_model!r} needs the coordinates table"
            )
        pair_distance = distance_registry.get(pair_distance_model)().build(coordinates, distances)

    return build_instance(
        sku_demand,
        location_costs,
        bay_distance,
        initial_stock=initial_stock,
        skus=universe,
        demand_metric=demand_metric,
        affinity=A,
        normalize=normalize,
        pair_distance=pair_distance,
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
        pair_distance=instance.pair_distance,
    )
