from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class AffinityInputConfig:
    order_col: str = "order_id"
    product_col: str = "product_id"
    drop_duplicate_lines: bool = True
    zero_diagonal: bool = True


class BaseAffinityMatrix(ABC):
    def __init__(
        self,
        order_lines: pd.DataFrame,
        config: AffinityInputConfig | None = None,
    ) -> None:
        self.order_lines = order_lines.copy()
        self.config = config or AffinityInputConfig()
        self.product_ids: np.ndarray | None = None
        self.product_index: dict[int, int] | None = None
        self._validate_input()

    def _validate_input(self) -> None:
        required = {self.config.order_col, self.config.product_col}
        missing = required - set(self.order_lines.columns)
        if missing:
            raise ValueError(f"Faltan columnas requeridas: {sorted(missing)}")

    def build_order_product_matrix(self) -> np.ndarray:
        df = self.order_lines[[self.config.order_col, self.config.product_col]].copy()

        if self.config.drop_duplicate_lines:
            df = df.drop_duplicates()

        orders = np.sort(df[self.config.order_col].unique())
        products = np.sort(df[self.config.product_col].unique())

        order_index = {order_id: idx for idx, order_id in enumerate(orders)}
        product_index = {product_id: idx for idx, product_id in enumerate(products)}

        X = np.zeros((len(orders), len(products)), dtype=np.int8)

        for row in df.itertuples(index=False):
            i = order_index[getattr(row, self.config.order_col)]
            j = product_index[getattr(row, self.config.product_col)]
            X[i, j] = 1

        self.product_ids = products
        self.product_index = product_index
        return X

    def _finalize(self, A: np.ndarray) -> np.ndarray:
        A = A.astype(float)
        if self.config.zero_diagonal:
            np.fill_diagonal(A, 0.0)
        return A

    @abstractmethod
    def compute(self) -> np.ndarray:
        raise NotImplementedError


class CooccurrenceAffinity(BaseAffinityMatrix):
    def compute(self) -> np.ndarray:
        X = self.build_order_product_matrix()
        A = X.T @ X
        return self._finalize(A)


class JaccardAffinity(BaseAffinityMatrix):
    def compute(self) -> np.ndarray:
        X = self.build_order_product_matrix()
        intersection = X.T @ X
        freq = X.sum(axis=0)
        union = freq[:, None] + freq[None, :] - intersection

        with np.errstate(divide="ignore", invalid="ignore"):
            A = np.where(union > 0, intersection / union, 0.0)

        return self._finalize(A)


class CosineAffinity(BaseAffinityMatrix):
    def compute(self) -> np.ndarray:
        X = self.build_order_product_matrix().astype(float)
        dot = X.T @ X
        norm = np.sqrt(np.diag(dot))
        denom = norm[:, None] * norm[None, :]

        with np.errstate(divide="ignore", invalid="ignore"):
            A = np.where(denom > 0, dot / denom, 0.0)

        return self._finalize(A)


def build_affinity_matrix(
    method: str,
    order_lines: pd.DataFrame,
    config: AffinityInputConfig | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    methods = {
        "cooccurrence": CooccurrenceAffinity,
        "jaccard": JaccardAffinity,
        "cosine": CosineAffinity,
    }

    if method not in methods:
        raise ValueError(f"Método desconocido: {method}")

    builder = methods[method](order_lines, config)
    A = builder.compute()

    if builder.product_ids is None:
        raise RuntimeError("No se pudieron recuperar los product_ids al construir la afinidad.")

    return A, builder.product_ids