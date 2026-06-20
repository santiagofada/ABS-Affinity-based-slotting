from .base import SlottingMethod, method_registry
from .current import CurrentSlotting, current_assignment
from .demand_greedy import DemandGreedySlotting
from .exact import ExactSlotting
from .linear_assignment import LinearAssignmentSlotting
from .local_search import AffinityPairSearch, LocalSearchSlotting
from .two_stage import (
    ClusterAggregation,
    TwoStageSlotting,
    aggregate_clusters,
    assign_locations_to_clusters,
)

__all__ = [
    "SlottingMethod",
    "method_registry",
    "CurrentSlotting",
    "current_assignment",
    "DemandGreedySlotting",
    "ExactSlotting",
    "LinearAssignmentSlotting",
    "LocalSearchSlotting",
    "AffinityPairSearch",
    "TwoStageSlotting",
    "ClusterAggregation",
    "aggregate_clusters",
    "assign_locations_to_clusters",
]
