"""Bi-level (two-stage) slotting.

The problem is decomposed into two optimization problems:

- Problem 1 (assign locations to clusters): given a clustering, assign to each
  cluster the set of locations it will occupy. Posed as an optimization over the
  aggregated cluster demand (a linear assignment / transportation problem).
- Problem 2 (place within each cluster): for each cluster independently, solve
  the QAP that places its SKUs in its assigned locations.

Both are solved with a real solver; the swap search is only used to refine a
solution. This module also provides the aggregation that turns a per-SKU
clustering into cluster-level data (demand, size, inter-cluster affinity).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.sparse import csr_matrix

from ..config import make_solver_env
from ..slotting import Assignment, SlottingInstance, restrict_instance
from .base import method_registry


@dataclass(frozen=True)
class ClusterAggregation:
    """Cluster-level reduction of an instance under a given labeling.

    All cluster-indexed arrays use contiguous cluster codes 0..n_clusters-1.
    The original labels (which may be arbitrary integers, including -1) are kept
    in ``labels`` so that code c corresponds to ``labels[c]``.

    Attributes
    ----------
    cluster_of_sku : np.ndarray, shape (n_skus,)
        Contiguous cluster code for each SKU, aligned with ``instance.sku_ids``.
    labels : np.ndarray, shape (n_clusters,)
        Original label of each cluster code.
    n_clusters : int
        Number of distinct clusters.
    demand : np.ndarray, shape (n_clusters,)
        Aggregated demand per cluster: sum of f_i over the SKUs it contains.
    size : np.ndarray, shape (n_clusters,)
        Number of SKUs per cluster (how many locations its zone must hold).
    affinity : np.ndarray, shape (n_clusters, n_clusters)
        Inter-cluster affinity: sum of a_ij over SKUs i, j in the two clusters,
        with the diagonal (intra-cluster affinity) zeroed. Symmetric.
    members : list[np.ndarray]
        members[c] holds the SKU indices belonging to cluster c.
    """

    cluster_of_sku: np.ndarray
    labels: np.ndarray
    n_clusters: int
    demand: np.ndarray
    size: np.ndarray
    affinity: np.ndarray
    members: list[np.ndarray]


def aggregate_clusters(
    instance: SlottingInstance,
    labels: np.ndarray,
) -> ClusterAggregation:
    """Reduce an instance to cluster level under a per-SKU labeling.

    Builds the one-hot indicator matrix G (n_skus x n_clusters), where
    G[i, c] = 1 iff SKU i belongs to cluster c. The aggregations are then simple
    matrix products:

        demand_per_cluster   = G^T f          (sum of demand within each cluster)
        cluster_affinity     = G^T A G        (affinity summed over cluster pairs)

    The diagonal of G^T A G is the intra-cluster affinity; it is zeroed because
    the upper-level QAP only needs the affinity BETWEEN clusters (intra-cluster
    affinity is resolved by keeping each cluster's zone compact).

    Parameters
    ----------
    instance : SlottingInstance
        The full problem instance.
    labels : np.ndarray, shape (n_skus,)
        Cluster label per SKU (as returned by a ClusteringStrategy). Arbitrary
        integers; mapped internally to contiguous codes.

    Returns
    -------
    ClusterAggregation
    """
    labels = np.asarray(labels)
    if labels.shape != (instance.n_skus,):
        raise ValueError(
            f"labels must have shape ({instance.n_skus},), got {labels.shape}."
        )

    # Map arbitrary labels to contiguous codes 0..K-1. distinct[code] = label.
    distinct, codes = np.unique(labels, return_inverse=True)
    n_clusters = len(distinct)
    n_skus = instance.n_skus

    # One-hot indicator G (n_skus x n_clusters): G[i, codes[i]] = 1.
    indicator = csr_matrix(
        (np.ones(n_skus), (np.arange(n_skus), codes)),
        shape=(n_skus, n_clusters),
    )

    demand = indicator.T @ instance.demand
    size = np.asarray(indicator.sum(axis=0)).ravel().astype(int)

    # Inter-cluster affinity: G^T A G, then drop the intra-cluster diagonal.
    cluster_affinity = (indicator.T @ instance.affinity @ indicator).toarray()
    np.fill_diagonal(cluster_affinity, 0.0)

    members = [np.flatnonzero(codes == c) for c in range(n_clusters)]

    return ClusterAggregation(
        cluster_of_sku=codes,
        labels=distinct,
        n_clusters=n_clusters,
        demand=demand,
        size=size,
        affinity=cluster_affinity,
        members=members,
    )


def assign_locations_to_clusters(
    instance: SlottingInstance,
    aggregation: ClusterAggregation,
    *,
    location_cost: np.ndarray | None = None,
    output: bool = False,
) -> list[np.ndarray]:
    """Problem 1: assign to each cluster the set of locations it will occupy.

    Posed as an optimization (a transportation problem): give the best
    locations to the clusters that need them most, measured by aggregated
    demand. Let ``y[l, c] = 1`` if location l is assigned to cluster c, then

        min  Σ_l Σ_c  demand[c] · cost[l] · y[l, c]
        s.t. Σ_c y[l, c] ≤ 1            each location to at most one cluster
             Σ_l y[l, c] = size[c]      each cluster gets its number of locations
             y[l, c] ∈ {0, 1}

    The constraint matrix is totally unimodular, so the LP relaxation already has
    an integral optimum: we solve it as a continuous program. Inter-cluster
    affinity is not modeled here yet (it would add a quadratic term); that is a
    planned extension.

    Parameters
    ----------
    instance : SlottingInstance
    aggregation : ClusterAggregation
        Cluster-level demand and sizes (from ``aggregate_clusters``).
    location_cost : np.ndarray | None
        Per-location cost the assignment ranks locations by (aligned with
        ``instance.location_ids``). Default: distance to dock
        (``instance.location_cost``), which yields cost bands. Passing the
        position along the pick path (snake order) instead yields spatially
        compact, contiguous zones.
    output : bool
        Whether the solver prints its log.

    Returns
    -------
    list[np.ndarray]
        zone_locations[c] holds the location indices assigned to cluster c.
    """
    import gurobipy as gp
    from gurobipy import GRB

    n_locations = instance.n_locations
    n_clusters = aggregation.n_clusters

    value = (
        instance.location_cost if location_cost is None else np.asarray(location_cost)
    )

    # cost_of_giving[l, c] = demand[c] * value[l]: penalizes giving a costly (far,
    # or late in the pick path) location to a high-demand cluster.
    cost_of_giving = np.outer(value, aggregation.demand)

    env = make_solver_env()
    model = gp.Model("location_assignment", env=env)
    model.Params.OutputFlag = 1 if output else 0

    # Continuous in [0, 1]; integral by total unimodularity.
    y = model.addMVar((n_locations, n_clusters), lb=0.0, ub=1.0, name="y")
    model.addConstr(y.sum(axis=1) <= 1, name="one_cluster_per_location")
    model.addConstr(y.sum(axis=0) == aggregation.size, name="cluster_size")
    model.setObjective((cost_of_giving * y).sum(), GRB.MINIMIZE)
    model.optimize()

    if model.SolCount == 0:
        raise RuntimeError(
            f"Solver found no feasible location assignment (status {model.Status})."
        )

    assigned = y.X > 0.5
    return [np.flatnonzero(assigned[:, c]) for c in range(n_clusters)]


@method_registry.register("bilevel")
class BiLevelSlotting:
    """Bi-level slotting, fully composable.

    Solves the two optimization problems, each with a plug-in piece:

    - Problem 1: assign locations to clusters (``assign_locations_to_clusters``).
    - Problem 2: for each cluster, solve its zone as a standalone sub-instance
      with ``zone_solver`` — any SlottingMethod (exact, linear_assignment,
      swap_search, ...). Clusters are independent.

    Every block is a choice: the affinity A and geometry are fixed when the
    instance is built; the grouping and the per-zone solver are passed here.

    Parameters
    ----------
    clustering : ClusteringStrategy
        Strategy that groups SKUs (any from clustering_registry).
    zone_solver : SlottingMethod
        Method used to solve each cluster's zone (any from method_registry).
    location_cost : np.ndarray | None
        Per-location cost passed to Problem 1 (aligned with
        ``instance.location_ids``). Default: distance to dock (cost bands).
        Pass the pick-path position (snake order) for compact zones.
    """

    name = "bilevel"

    def __init__(self, clustering, zone_solver, *, location_cost=None):
        self.clustering = clustering
        self.zone_solver = zone_solver
        self.location_cost = location_cost

    def solve(self, instance: SlottingInstance) -> Assignment:
        labels = self.clustering.cluster(instance)
        aggregation = aggregate_clusters(instance, labels)

        # Problem 1: best locations per cluster.
        zones = assign_locations_to_clusters(
            instance, aggregation, location_cost=self.location_cost
        )

        # Problem 2: solve each cluster's zone as an independent sub-instance.
        mapping: dict = {}
        for cluster in range(aggregation.n_clusters):
            sku_indices = aggregation.members[cluster]
            location_indices = zones[cluster]
            if len(sku_indices) == 0:
                continue

            sub_instance = restrict_instance(instance, sku_indices, location_indices)
            sub_assignment = self.zone_solver.solve(sub_instance)

            for sku_id in sub_instance.sku_ids:
                mapping[sku_id] = sub_assignment.location_of(sku_id)

        return Assignment(mapping)
