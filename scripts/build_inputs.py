"""Build the base optimization inputs from the raw dataset.

Produces, under ``data/processed/``:
    picking_train.parquet / picking_test.parquet   temporal split
    sku_demand.parquet                             per-SKU demand (train only)
    location_costs.parquet                         dock distance per location

Run:  python scripts/build_inputs.py
"""

from __future__ import annotations

from abs_affinity_based_slotting.config import PROCESSED_DIR, RAW_DIR
from abs_affinity_based_slotting.data import (
    WarehouseDataLoader,
    split_picking_events,
    write_parquet,
)
from abs_affinity_based_slotting.demand import build_sku_demand
from abs_affinity_based_slotting.warehouse import build_location_costs


def main() -> None:
    data = WarehouseDataLoader(RAW_DIR).load_all()

    split = split_picking_events(data.picking_events, test_size=0.2)
    sku_demand = build_sku_demand(split.train)
    location_costs = build_location_costs(data.initial_stock, data.distances)

    write_parquet(split.train, PROCESSED_DIR / "picking_train.parquet")
    write_parquet(split.test, PROCESSED_DIR / "picking_test.parquet")
    write_parquet(sku_demand, PROCESSED_DIR / "sku_demand.parquet")
    write_parquet(location_costs, PROCESSED_DIR / "location_costs.parquet")

    print(f"cutoff (first test timestamp): {split.cutoff}")
    print(f"train lines: {len(split.train):>7,} | test lines: {len(split.test):>7,}")
    print(f"train batches: {split.train.batch_id.nunique():>4} "
          f"| test batches: {split.test.batch_id.nunique():>4}")
    print(f"sku_demand rows: {len(sku_demand):,}")
    print(f"location_costs rows: {len(location_costs):,}")
    print(f"written to {PROCESSED_DIR}")


if __name__ == "__main__":
    main()
