"""Outcome of one simulation run."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..evaluation import RouteMetrics
from .state import WarehouseState


@dataclass(frozen=True)
class SimulationResult:
    """Everything one run produces.

    Attributes
    ----------
    route_metrics:
        Aggregate route distances over the simulated batches; directly
        comparable with the static evaluator's output.
    batch_log:
        One row per batch, in time order: batch_id, timestamp, distance,
        n_lines, shortfall_units, off_home_fraction. The time series is what
        shows degradation (distance drifting as the layout decays).
    replen_log:
        One row per replenishment: timestamp, sku_idx, destination, moved
        (opened a location the SKU was not in), at_home (landed on the planned
        location).
    n_relocations:
        Replens that moved the SKU somewhere new.
    shortfall_lines / shortfall_units:
        Pick lines (and units) the state could not fully serve. Nonzero values
        are legitimate dynamics under a diverging policy, never an exception.
    final_off_home_fraction:
        Fraction of SKUs not sitting exactly on their planned location at the
        end; NaN when the run had no plan.
    final_state:
        The warehouse state after the last event.
    """

    route_metrics: RouteMetrics
    batch_log: pd.DataFrame
    replen_log: pd.DataFrame
    n_relocations: int
    shortfall_lines: int
    shortfall_units: int
    final_off_home_fraction: float
    final_state: WarehouseState
