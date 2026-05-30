from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from src.affinity import AffinityInputConfig, build_affinity_matrix
from src.build_wh import (
    build_location_costs,
    build_location_distance_matrix,
    build_location_grid,
    build_product_frequency,
)


@dataclass(frozen=True, slots=True)
class ToyInstance:
    product_ids: np.ndarray
    location_ids: np.ndarray
    affinity_matrix: np.ndarray
    product_frequency: np.ndarray
    location_costs: np.ndarray
    location_distances: np.ndarray
    n_rows: int
    n_cols: int


def load_synthetic_data(
    data_dir: str | Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    data_dir = Path(data_dir)

    products_df = pd.read_csv(data_dir / "products.csv")
    orders_df = pd.read_csv(data_dir / "orders.csv")
    order_lines_df = pd.read_csv(data_dir / "order_lines.csv")

    return products_df, orders_df, order_lines_df


def validate_order_lines(order_lines: pd.DataFrame) -> None:
    required = {"order_id", "product_id"}
    missing = required - set(order_lines.columns)

    if missing:
        raise ValueError(f"Faltan columnas requeridas en order_lines: {sorted(missing)}")


def build_frequency_vector(
    order_lines: pd.DataFrame,
    product_ids: np.ndarray,
) -> np.ndarray:
    freq = build_product_frequency(order_lines)
    freq = freq.reindex(product_ids, fill_value=0.0)
    return freq.to_numpy(dtype=float)


def build_toy_instance(
    order_lines: pd.DataFrame,
    n_rows: int,
    n_cols: int,
    affinity_method: str = "cooccurrence",
) -> ToyInstance:
    if n_rows <= 0 or n_cols <= 0:
        raise ValueError("n_rows y n_cols deben ser positivos")

    validate_order_lines(order_lines)

    affinity_config = AffinityInputConfig(
        order_col="order_id",
        product_col="product_id",
        drop_duplicate_lines=True,
        zero_diagonal=True,
    )

    A, product_ids = build_affinity_matrix(
        method=affinity_method,
        order_lines=order_lines,
        config=affinity_config,
    )

    f = build_frequency_vector(order_lines, product_ids)

    grid = build_location_grid(n_rows, n_cols)
    location_ids = grid["location_id"].to_numpy(dtype=int)

    D = build_location_distance_matrix(n_rows, n_cols)
    c = build_location_costs(n_rows, n_cols)

    return ToyInstance(
        product_ids=product_ids,
        location_ids=location_ids,
        affinity_matrix=A,
        product_frequency=f,
        location_costs=c,
        location_distances=D,
        n_rows=n_rows,
        n_cols=n_cols,
    )


def summarize_products(instance: ToyInstance) -> pd.DataFrame:
    return (
        pd.DataFrame(
            {
                "product_id": instance.product_ids,
                "frequency": instance.product_frequency,
            }
        )
        .sort_values("frequency", ascending=False)
        .reset_index(drop=True)
    )


def summarize_locations(instance: ToyInstance) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "location_id": instance.location_ids,
            "location_cost": instance.location_costs,
        }
    )