from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass(frozen=True, slots=True)
class SyntheticOrderConfig:
    n_products: int = 100
    n_orders: int = 5000
    n_affinity_groups: int = 5
    avg_items_per_order: float = 4.0
    std_items_per_order: float = 1.5
    within_group_strength: float = 0.85
    cross_group_noise: float = 0.15
    multi_group_product_prob: float = 0.10
    popular_product_fraction: float = 0.10
    popular_product_boost: float = 2.0
    seed: int = 42
    output_dir: str = "../data/synthetic_dataset"


def _assign_groups(
    config: SyntheticOrderConfig,
    rng: np.random.Generator,
) -> pd.DataFrame:
    product_ids = np.arange(config.n_products)

    base_groups = rng.integers(0, config.n_affinity_groups, size=config.n_products)
    memberships = {i: [int(base_groups[i])] for i in product_ids}

    for i in product_ids:
        if rng.random() < config.multi_group_product_prob:
            g = int(rng.integers(0, config.n_affinity_groups))
            if g not in memberships[i]:
                memberships[i].append(g)

    n_popular = max(1, int(config.popular_product_fraction * config.n_products))
    popular_products = set(rng.choice(product_ids, size=n_popular, replace=False))

    products_df = pd.DataFrame(
        {
            "product_id": product_ids,
            "product_name": [f"P{i:03d}" for i in product_ids],
            "group_ids": ["|".join(map(str, memberships[i])) for i in product_ids],
            "is_popular": [int(i in popular_products) for i in product_ids],
        }
    )

    return products_df


def _build_sampling_weights(
    products_df: pd.DataFrame,
    config: SyntheticOrderConfig,
) -> tuple[dict[int, np.ndarray], np.ndarray]:
    n_products = len(products_df)

    membership_map = {
        row.product_id: [int(x) for x in row.group_ids.split("|")]
        for row in products_df.itertuples(index=False)
    }

    popularity = np.ones(n_products, dtype=float)
    for row in products_df.itertuples(index=False):
        if row.is_popular:
            popularity[row.product_id] *= config.popular_product_boost

    group_weights: dict[int, np.ndarray] = {}
    for g in range(config.n_affinity_groups):
        weights = np.full(n_products, config.cross_group_noise, dtype=float)

        for product_id in range(n_products):
            if g in membership_map[product_id]:
                weights[product_id] += config.within_group_strength

        weights *= popularity
        weights /= weights.sum()
        group_weights[g] = weights

    global_weights = popularity / popularity.sum()

    return group_weights, global_weights


def _sample_order_size(
    rng: np.random.Generator,
    config: SyntheticOrderConfig,
) -> int:
    size = int(round(rng.normal(config.avg_items_per_order, config.std_items_per_order)))
    return max(1, min(size, config.n_products))


def _generate_orders_and_lines(
    products_df: pd.DataFrame,
    config: SyntheticOrderConfig,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    group_weights, global_weights = _build_sampling_weights(products_df, config)
    product_ids = products_df["product_id"].to_numpy()

    orders_rows: list[dict] = []
    order_lines_rows: list[dict] = []

    for order_id in range(config.n_orders):
        basket_size = _sample_order_size(rng, config)
        main_group = int(rng.integers(0, config.n_affinity_groups))

        chosen_products: set[int] = set()

        for _ in range(basket_size):
            use_main_group = rng.random() < 0.85
            weights = group_weights[main_group] if use_main_group else global_weights

            available_mask = np.array([pid not in chosen_products for pid in product_ids], dtype=bool)
            if not available_mask.any():
                break

            candidate_ids = product_ids[available_mask]
            candidate_weights = weights[available_mask]
            candidate_weights = candidate_weights / candidate_weights.sum()

            chosen_product = int(rng.choice(candidate_ids, p=candidate_weights))
            chosen_products.add(chosen_product)

        chosen_products_list = sorted(chosen_products)

        orders_rows.append(
            {
                "order_id": order_id,
                "main_group": main_group,
                "n_items": len(chosen_products_list),
            }
        )

        for line_no, product_id in enumerate(chosen_products_list, start=1):
            quantity = int(rng.integers(1, 4))
            order_lines_rows.append(
                {
                    "order_id": order_id,
                    "line_no": line_no,
                    "product_id": product_id,
                    "quantity": quantity,
                }
            )

    orders_df = pd.DataFrame(orders_rows)
    order_lines_df = pd.DataFrame(order_lines_rows)

    return orders_df, order_lines_df


def main() -> None:
    config = SyntheticOrderConfig()
    rng = np.random.default_rng(config.seed)

    output_dir = Path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    products_df = _assign_groups(config, rng)
    orders_df, order_lines_df = _generate_orders_and_lines(products_df, config, rng)

    products_df.to_csv(output_dir / "products.csv", index=False)
    orders_df.to_csv(output_dir / "orders.csv", index=False)
    order_lines_df.to_csv(output_dir / "order_lines.csv", index=False)


if __name__ == "__main__":
    main()