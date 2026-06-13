"""Co-occurrence of SKUs within batches — the raw input to every affinity metric.

Two SKUs co-occur when they appear in the same batch (the picking trip is the
unit of co-demand). From the binary batch×SKU incidence matrix ``B`` the
co-occurrence is ``C = B^T B``: its off-diagonal entry ``(i, j)`` counts batches
containing both SKUs, and its diagonal is the per-SKU support.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix


@dataclass(frozen=True)
class Cooccurrence:
    skus: np.ndarray       # SKU universe; defines the row/column order
    matrix: csr_matrix     # (n, n) n_ij: batches with both i and j; zero diagonal
    support: np.ndarray    # (n,)   s_i: batches containing i
    n_batches: int         # N: total number of batches

    @property
    def n_skus(self) -> int:
        return len(self.skus)


def build_cooccurrence(
    picking_events: pd.DataFrame,
    *,
    skus: np.ndarray | pd.Index | None = None,
    batch_col: str = "batch_id",
    sku_col: str = "sku",
) -> Cooccurrence:
    """Count SKU co-occurrence over batches.

    The SKU universe is ``skus`` if given (defining the index order), else the
    sorted unique SKUs present. ``n_batches`` counts every batch, including those
    whose SKUs fall outside the universe.
    """
    pairs = picking_events[[batch_col, sku_col]].drop_duplicates()

    batches = pairs[batch_col].unique()
    batch_index = {batch: i for i, batch in enumerate(batches)}

    if skus is None:
        sku_ids = np.sort(pairs[sku_col].unique())
    else:
        sku_ids = np.asarray(skus)
        pairs = pairs[pairs[sku_col].isin(set(sku_ids))]
    sku_index = {sku: i for i, sku in enumerate(sku_ids)}

    rows = pairs[batch_col].map(batch_index).to_numpy()
    cols = pairs[sku_col].map(sku_index).to_numpy()
    incidence = csr_matrix(
        (np.ones(len(pairs), dtype=np.int32), (rows, cols)),
        shape=(len(batches), len(sku_ids)),
    )

    gram = (incidence.T @ incidence).tocsr()   # (n, n); diagonal = support
    support = gram.diagonal().astype(np.int64)
    matrix = gram.copy()
    matrix.setdiag(0)
    matrix.eliminate_zeros()

    return Cooccurrence(
        skus=sku_ids,
        matrix=matrix,
        support=support,
        n_batches=len(batches),
    )
