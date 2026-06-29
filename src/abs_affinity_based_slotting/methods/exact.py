"""Exact slotting solver.

Solves the full slotting objective C = λ·L + (1-λ)·Q to proven optimality (within
an optional gap), using the binary program from the formulation:

    min  λ Σ_i Σ_k f_i c_k x_ik  +  (1-λ) Σ_i Σ_j Σ_k Σ_l a_ij d_kl x_ik x_jl
    s.t. Σ_k x_ik = 1   for every product i
         Σ_i x_ik ≤ 1   for every location k
         x_ik ∈ {0, 1}

This does NOT scale to the full instance (the QAP is NP-hard). Its role is to
solve the SMALL subproblems of the bi-level decomposition (per-cluster placement)
and to provide the optimal reference on small instances against which heuristics
are measured. The optimization backend is configured in ``config``.
"""

from __future__ import annotations

import numpy as np

from ..config import make_solver_env
from ..slotting import Assignment, SlottingInstance
from .base import method_registry


@method_registry.register("exact_qap")
class ExactQAPSlotting:
    """Exact solver for the full λ·L + (1-λ)·Q objective.

    Intended for small instances and for the subproblems of the bi-level
    decomposition. On large instances it will not finish; pass a time limit to
    get the best solution found within the budget.

    Parameters
    ----------
    lam : float
        Weight λ ∈ [0, 1] for C = λ·L + (1-λ)·Q.
    time_limit : float | None
        Seconds before returning the best solution found. None = no limit.
    mip_gap : float | None
        Relative optimality gap to accept (e.g. 0.02 = 2%). None = solve to
        proven optimality.
    output : bool
        Whether the solver prints its log.
    """

    name = "exact_qap"

    def __init__(
        self,
        *,
        lam: float = 0.5,
        time_limit: float | None = None,
        mip_gap: float | None = None,
        output: bool = False,
    ):
        self.lam = float(lam)
        self.time_limit = time_limit
        self.mip_gap = mip_gap
        self.output = output
        if not 0.0 <= self.lam <= 1.0:
            raise ValueError(f"lam must be in [0, 1], got {self.lam}.")

    def solve(self, instance: SlottingInstance) -> Assignment:
        import gurobipy as gp
        from gurobipy import GRB

        n = instance.n_skus
        m = instance.n_locations
        lam = self.lam

        # Dense location-to-location distance via bays (only sound for small m).
        loc_bay = instance.location_bay
        location_distance = instance.bay_distance[np.ix_(loc_bay, loc_bay)]

        env = make_solver_env()
        model = gp.Model("slotting", env=env)
        model.Params.OutputFlag = 1 if self.output else 0
        if self.time_limit is not None:
            model.Params.TimeLimit = self.time_limit
        if self.mip_gap is not None:
            model.Params.MIPGap = self.mip_gap

        # x[i, k] = 1 if product i is placed at location k.
        x = model.addVars(n, m, vtype=GRB.BINARY, name="x")

        # Each product goes to exactly one location.
        model.addConstrs((x.sum(i, "*") == 1 for i in range(n)), name="assign")
        # Each location holds at most one product (m >= n leaves some empty).
        model.addConstrs((x.sum("*", k) <= 1 for k in range(m)), name="capacity")

        # Linear term: λ Σ_i Σ_k f_i c_k x_ik.
        linear = gp.quicksum(
            instance.demand[i] * instance.location_cost[k] * x[i, k]
            for i in range(n)
            for k in range(m)
        )

        # Quadratic term: (1-λ) Σ a_ij d_kl x_ik x_jl, only over nonzero a_ij.
        affinity = instance.affinity.tocoo()
        quadratic = gp.quicksum(
            a_ij * location_distance[k, l] * x[i, k] * x[j, l]
            for i, j, a_ij in zip(affinity.row, affinity.col, affinity.data)
            for k in range(m)
            for l in range(m)
        )

        model.setObjective(lam * linear + (1.0 - lam) * quadratic, GRB.MINIMIZE)
        model.optimize()

        if model.SolCount == 0:
            raise RuntimeError(
                f"Solver found no feasible solution (status {model.Status})."
            )

        # Extract assignment from the solution.
        mapping: dict = {}
        solution = model.getAttr("X", x)
        for i in range(n):
            for k in range(m):
                if solution[i, k] > 0.5:
                    mapping[instance.sku_id(i)] = instance.location_id(k)
                    break

        return Assignment(mapping)
