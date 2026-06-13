"""Contract for affinity builders (the pluggable ways to build the matrix A).

An affinity builder turns raw co-occurrence into a SKU-SKU affinity score.
Keeping the input metric-agnostic (co-occurrence counts + per-SKU support +
number of batches) lets every metric — raw count, Jaccard, cosine, lift, ... —
be a separate registered implementation deriving from the same data.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np
from scipy.sparse import csr_matrix

from ..registry import Registry


@runtime_checkable
class AffinityBuilder(Protocol):
    name: str

    def build(
        self,
        cooccurrence: csr_matrix,  # (n_skus, n_skus) #batches with both SKUs
        support: np.ndarray,       # (n_skus,) #batches containing each SKU
        n_batches: int,
    ) -> csr_matrix:
        """Return the SKU-SKU affinity matrix (CSR), aligned with ``support``."""
        ...


#: name -> AffinityBuilder subclass.
affinity_registry: Registry[type[AffinityBuilder]] = Registry("affinity")


@affinity_registry.register("cooccurrence")
class CooccurrenceAffinity:
    """Raw co-occurrence count, ``a_ij = n_ij``. Unnormalized baseline metric."""

    name = "cooccurrence"

    def build(self, cooccurrence, support, n_batches) -> csr_matrix:
        return cooccurrence.astype(float).tocsr()


@affinity_registry.register("jaccard")
class JaccardAffinity:
    """Jaccard affinity between SKUs.

    Computes the similarity between two SKUs as the fraction of batches/orders
    containing both SKUs over the number of batches/orders containing at least one
    of them:

        a_ij = n_ij / (s_i + s_j - n_ij)

    where n_ij is the number of co-occurrences, and s_i and s_j are the individual
    supports of SKUs i and j, the formula is equivalent to:

        = |B_i ∩ B_j| / |B_i U B_j|

    where B_i and B_j are the sets of batches/orders containing SKUs i and j-

    This normalization penalizes pairs whose items are frequent independently,
    making the score high only when the two SKUs tend to appear together relative
    to their total combined presence. The computation is performed only on nonzero
    co-occurrence entries, preserving sparsity.
    """

    name = "jaccard"

    def build(self, cooccurrence, support, n_batches) -> csr_matrix:
        coo = cooccurrence.tocoo()
        n_ij = coo.data.astype(float)
        union = support[coo.row] + support[coo.col] - n_ij
        with np.errstate(divide="ignore", invalid="ignore"):
            scores = np.where(union > 0, n_ij / union, 0.0)
        return csr_matrix((scores, (coo.row, coo.col)), shape=cooccurrence.shape)


# ---------------------------------------------------------------------------
# Metricas candidatas a implementar
# ---------------------------------------------------------------------------
#
# Cosine:
#   a_ij = n_ij / sqrt(s_i * s_j)
#   Interpreta cada SKU como un vector binario en el espacio de batches.
#   Normaliza por la raiz del producto de soportes; menos sensible que Jaccard
#   a SKUs muy frecuentes.
#
# Lift (confianza relativa):
#   a_ij = (n_ij / N) / ((s_i / N) * (s_j / N))  =  n_ij * N / (s_i * s_j)
#   Mide cuantas veces mas co-ocurren de lo esperado bajo independencia.
#   Puede dispararse si s_i o s_j es muy bajo (pares raros con co-ocurrencia
#   perfecta obtienen lift altisimo). Requiere umbral minimo de soporte.
#
# Confianza dirigida (P(j|i)):
#   a_ij = n_ij / s_i  (asimetrica)
#   Probabilidad de ver j dado que aparece i. Util para demand-side slotting
#   pero rompe la simetria que requiere el QAP (A debe ser simetrica).
#   Se puede simetrizar como min o promedio de las dos direcciones.
#
# PMI (Pointwise Mutual Information):
#   a_ij = log( (n_ij / N) / ((s_i / N) * (s_j / N)) )  =  log(lift)
#   Escala logaritmica del lift; mas estable para soportes bajos.
#   En su variante normalizada (NPMI) cae en [-1, 1].
# ---------------------------------------------------------------------------
