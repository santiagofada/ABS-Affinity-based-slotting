"""What one experiment run is: an instance, a slotting plan and how it is evaluated.

A :class:`Task` is the unit of work. Building the plan is the expensive part
(``swap_search`` takes minutes), so a task builds one plan and evaluates it
under several :class:`EvalSpec` (batching window, routing, replenishment),
which are cheap. Every field is a plain value so tasks hash, pickle and
serialise without surprises.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class InstanceSpec:
    """How the problem instance is built (see ``build_full_instance``)."""

    dataset: str                         # folder under data/v2
    demand_metric: str = "pick_lines"    # pick_lines | unique_orders | unique_batches | total_units
    affinity_metric: str = "jaccard"     # jaccard | cosine | cooccurrence
    cooccurrence_col: str = "order_id"   # order_id | batch_id
    affinity_filter: str = "top_k:10"    # none | top_k:K | mutual_top_k:K | threshold:X
    normalize: bool = True
    pair_distance: str = "aisle"         # walking | aisle


@dataclass(frozen=True)
class SlottingSpec:
    """Which method builds the plan, with its parameters (None = not used)."""

    method: str                          # vigente | demand_greedy | linear_assignment | aisle_fill |
                                         # merchant_aisle_fill | bilevel | swap_search
    lam: float | None = None             # swap_search
    neighborhood: str | None = None      # swap_search: bay | neighbor
    seed: str | None = None              # swap_search: plan it starts from
    clustering: str | None = None        # bilevel: merchant | demand_class
    zone_cost: str | None = None         # bilevel: dock (cost bands) | aisle_order (zones aisle by aisle)


@dataclass(frozen=True)
class EvalSpec:
    """How a plan is measured in the simulation."""

    window: int = 1                      # FIFO batches pooled by the re-batching; 1 = FIFO
    batching_passes: int = 20            # swap passes of the re-batching; 0 = construction only
    routing: str = "s_shape"             # s_shape | snake
    replenishment: str = "home"          # home | random | objective_greedy
    replenishment_lam: float = 0.5       # objective_greedy only


@dataclass(frozen=True)
class Task:
    block: str                           # which part of the experiment design it belongs to
    instance: InstanceSpec
    slotting: SlottingSpec
    evals: tuple[EvalSpec, ...] = field(default_factory=tuple)

    @property
    def key(self) -> str:
        """Stable identifier: same task, same key, across runs and machines."""
        text = json.dumps(asdict(self), sort_keys=True, default=str)
        return hashlib.sha1(text.encode()).hexdigest()[:16]

    @property
    def needs_solver(self) -> bool:
        """Uses the optimization solver (licence sessions are limited, run these one at a time)."""
        return self.slotting.method == "bilevel"
