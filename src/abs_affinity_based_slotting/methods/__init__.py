from .base import SlottingMethod, method_registry
from .current import CurrentSlotting, current_assignment
from .demand_greedy import DemandGreedySlotting
from .exact import ExactQAPSlotting
from .linear_assignment import LinearAssignmentSlotting
from .local_search import SwapSearchSlotting
from .two_stage import (
    ClusterAggregation,
    BiLevelSlotting,
    aggregate_clusters,
    assign_locations_to_clusters,
)

__all__ = [
    "SlottingMethod",
    "method_registry",
    "CurrentSlotting",
    "current_assignment",
    "DemandGreedySlotting",
    "ExactQAPSlotting",
    "LinearAssignmentSlotting",
    "SwapSearchSlotting",
    "BiLevelSlotting",
    "ClusterAggregation",
    "aggregate_clusters",
    "assign_locations_to_clusters",
]
