"""Travel cost of a single picking route.

Pure numerical helpers (no pandas): they take bay indices already prepared by
the caller. The bay-level model means several picks in the same bay add nothing
to the distance. ``dock`` is the bay index of the dock / packing station.
"""

from __future__ import annotations

import numpy as np


def snake_order(bays: np.ndarray, sort_keys: np.ndarray) -> np.ndarray:
    """Return ``bays`` reordered by ``sort_keys`` ascending (stable).

    The caller encodes the traversal order into ``sort_keys`` (e.g. aisle then
    bay number), so the ordering policy lives outside this function.
    """
    return bays[np.argsort(sort_keys, kind="stable")]


def route_distance(
    bay_sequence: np.ndarray,
    bay_distance: np.ndarray,
    dock: int,
) -> float:
    """Walking distance ``dock -> bays (in the given order) -> dock``.

    Sums the bay-to-bay distance of each consecutive leg. Returns 0 for an
    empty sequence.
    """
    if len(bay_sequence) == 0:
        return 0.0
    nodes = np.empty(len(bay_sequence) + 2, dtype=int)
    nodes[0] = dock
    nodes[-1] = dock
    nodes[1:-1] = bay_sequence
    return float(bay_distance[nodes[:-1], nodes[1:]].sum())
