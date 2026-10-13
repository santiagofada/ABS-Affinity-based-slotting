"""Local search: improve a seed assignment with affinity-guided moves.

The goal of a move is to bring a SKU next to the SKUs it is picked with. For a
SKU i and each of its affinity neighbors k, the candidate destinations are the
locations in the bay where k currently sits (distance zero to k at the bay
level). A free location there is taken by a plain move; an occupied one by
swapping i with its occupant j, even if a_ij = 0. The cost change of each
candidate is evaluated incrementally and the first improving one is applied.

The earlier version only proposed swapping i with k itself, which puts i in
k's bay but throws k out of it. That neighborhood is kept as
``neighborhood="neighbor"`` so its effect can be measured.
"""

from __future__ import annotations

import numpy as np

from ..slotting import Assignment, SlottingInstance, move_cost_delta, swap_cost_delta
from .base import method_registry
from .demand_greedy import DemandGreedySlotting


def _affinity_neighbors(affinity_csr, sku_idx: int) -> np.ndarray:
    """Return indices of SKUs with nonzero affinity to sku_idx."""
    start, end = affinity_csr.indptr[sku_idx], affinity_csr.indptr[sku_idx + 1]
    return affinity_csr.indices[start:end]


@method_registry.register("swap_search")
class SwapSearchSlotting:
    """Affinity-guided local search over swaps and moves to free locations.

    Algorithm:
    1. Seed: ``seed_method`` (DemandGreedy by default).
    2. Per pass, for each SKU i and each affinity neighbor k of i, look at the
       locations of k's bay. Free location: move i there if the cost drops.
       Occupied by j: swap i and j if the cost drops. First improvement wins.
    3. Stop after a pass without any improvement, or after ``max_passes``.

    Complexity per pass: O(n * deg * locations_per_bay * deg) with the
    ``bay`` neighborhood, O(n * deg * deg) with ``neighbor``.

    Parameters
    ----------
    seed_method :
        Initial assignment generator. Defaults to DemandGreedySlotting.
    lam : float
        Weight of the linear term in C = lam * L + (1 - lam) * Q.
    max_passes : int
        Maximum passes over all SKUs.
    neighborhood : {"bay", "neighbor"}
        ``bay``: all locations of each neighbor's bay (moves and swaps).
        ``neighbor``: only swapping i with the neighbor itself (old behavior).
    """

    name = "swap_search"

    def __init__(
        self,
        seed_method=None,
        *,
        lam: float = 0.5,
        max_passes: int = 50,
        neighborhood: str = "bay",
    ):
        self.seed_method = seed_method or DemandGreedySlotting()
        self.lam = float(lam)
        self.max_passes = int(max_passes)
        if not 0.0 <= self.lam <= 1.0:
            raise ValueError(f"lam must be in [0, 1], got {self.lam}.")
        if neighborhood not in ("bay", "neighbor"):
            raise ValueError(f"neighborhood must be 'bay' or 'neighbor', got {neighborhood!r}")
        self.neighborhood = neighborhood
        self.passes_run = 0
        self.n_swaps = 0
        self.n_moves = 0

    def solve(self, instance: SlottingInstance) -> Assignment:
        assignment = self.seed_method.solve(instance)
        affinity = instance.affinity.tocsr()
        self.passes_run = self.n_swaps = self.n_moves = 0

        # Location indices grouped by bay, so "the bay where k sits" is a lookup.
        bay_locations: dict[int, list[int]] = {}
        for loc_idx, bay_idx in enumerate(instance.location_bay):
            bay_locations.setdefault(int(bay_idx), []).append(loc_idx)

        for _ in range(self.max_passes):
            improved = False
            self.passes_run += 1

            for sku_i_idx in range(instance.n_skus):
                neighbors = _affinity_neighbors(affinity, sku_i_idx)
                if len(neighbors) == 0:
                    continue
                sku_i = instance.sku_id(sku_i_idx)

                for sku_k_idx in neighbors:
                    if self.neighborhood == "neighbor":
                        candidates = [instance.location_index(assignment.location_of(instance.sku_id(sku_k_idx)))]
                    else:
                        loc_k = instance.location_index(assignment.location_of(instance.sku_id(sku_k_idx)))
                        candidates = bay_locations[int(instance.location_bay[loc_k])]

                    for loc_idx in candidates:
                        loc_id = instance.location_id(loc_idx)
                        occupant = assignment.sku_at(loc_id)
                        if occupant is None:
                            delta = move_cost_delta(assignment, instance, sku_i, loc_id, lam=self.lam)
                            if delta < 0.0:
                                assignment.move(sku_i, loc_id)
                                self.n_moves += 1
                                improved = True
                                break
                        elif occupant != sku_i:
                            delta = swap_cost_delta(assignment, instance, sku_i, occupant, lam=self.lam)
                            if delta < 0.0:
                                assignment.swap(sku_i, occupant)
                                self.n_swaps += 1
                                improved = True
                                break

            if not improved:
                break

        return assignment
