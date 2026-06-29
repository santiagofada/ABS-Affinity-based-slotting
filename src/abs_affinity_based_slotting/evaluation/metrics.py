"""Aggregate per-batch route costs into a comparable set of metrics."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class RouteMetrics:
    n_batches: int
    total_distance: float
    mean_batch_distance: float
    median_batch_distance: float
    p95_batch_distance: float
    runtime_seconds: float | None = None  # method solve time, set by the caller


def summarize_route_costs(
    batch_costs: Sequence[float] | np.ndarray,
    *,
    runtime_seconds: float | None = None,
) -> RouteMetrics:
    """Summarize a collection of per-batch route costs."""
    costs = np.asarray(batch_costs, dtype=float)
    if costs.size == 0:
        return RouteMetrics(0, 0.0, 0.0, 0.0, 0.0, runtime_seconds)
    return RouteMetrics(
        n_batches=int(costs.size),
        total_distance=float(costs.sum()),
        mean_batch_distance=float(costs.mean()),
        median_batch_distance=float(np.median(costs)),
        p95_batch_distance=float(np.percentile(costs, 95)),
        runtime_seconds=runtime_seconds,
    )
