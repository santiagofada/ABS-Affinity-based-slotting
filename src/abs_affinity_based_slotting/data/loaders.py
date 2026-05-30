from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class WarehouseDataset:
    coordinates: pd.DataFrame
    distances: pd.DataFrame
    initial_stock: pd.DataFrame
    picking_events: pd.DataFrame
    replenishment_events: pd.DataFrame


class WarehouseDataLoader:
    """
    Loader for the warehouse dataset.

    The class only reads raw files from disk. It does not perform cleaning,
    feature engineering, or optimization-specific transformations.
    """

    def __init__(self, data_dir: str | Path):
        self.data_dir = Path(data_dir)

    def load_coordinates(self) -> pd.DataFrame:
        return self._read_parquet("coordinates.parquet")

    def load_distances(self) -> pd.DataFrame:
        return self._read_parquet("distances.parquet")

    def load_initial_stock(self) -> pd.DataFrame:
        return self._read_parquet("initial_stock.parquet")

    def load_picking_events(self) -> pd.DataFrame:
        return self._read_parquet("picking_events.parquet")

    def load_replenishment_events(self) -> pd.DataFrame:
        return self._read_parquet("replenishment_events.parquet")

    def load_all(self) -> WarehouseDataset:
        return WarehouseDataset(
            coordinates=self.load_coordinates(),
            distances=self.load_distances(),
            initial_stock=self.load_initial_stock(),
            picking_events=self.load_picking_events(),
            replenishment_events=self.load_replenishment_events(),
        )

    def _read_parquet(self, filename: str) -> pd.DataFrame:
        path = self.data_dir / filename

        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        return pd.read_parquet(path)