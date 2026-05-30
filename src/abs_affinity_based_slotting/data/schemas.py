import pandas as pd


EXPECTED_COLUMNS = {
    "coordinates": {
        "bay_id",
        "zone",
        "aisle",
        "bay_number",
        "side",
        "x",
        "y",
    },
    "distances": {
        "bay_a",
        "bay_b",
        "distance_in",
    },
    "initial_stock": {
        "location_id",
        "location_name",
        "bay_id",
        "sku",
        "merchant_account_id",
        "units",
    },
    "picking_events": {
        "batch_id",
        "timestamp",
        "user_id",
        "location_id",
        "location_name",
        "bay_name",
        "sku",
        "merchant_account_id",
        "quantity",
    },
    "replenishment_events": {
        "timestamp",
        "user_id",
        "source_location_id",
        "target_location_id",
        "location_name",
        "sku",
        "merchant_account_id",
        "quantity",
    },
}


def validate_columns(df: pd.DataFrame, table_name: str) -> None:
    """
    Validate that a DataFrame contains the expected columns for a given table.
    """
    if table_name not in EXPECTED_COLUMNS:
        raise ValueError(f"Unknown table name: {table_name}")

    expected = EXPECTED_COLUMNS[table_name]
    actual = set(df.columns)

    missing = expected - actual

    if missing:
        raise ValueError(
            f"Table '{table_name}' is missing columns: {sorted(missing)}"
        )


def validate_dataset_tables(
    coordinates: pd.DataFrame,
    distances: pd.DataFrame,
    initial_stock: pd.DataFrame,
    picking_events: pd.DataFrame,
    replenishment_events: pd.DataFrame,
) -> None:
    """
    Validate the main input tables of the warehouse dataset.
    """
    validate_columns(coordinates, "coordinates")
    validate_columns(distances, "distances")
    validate_columns(initial_stock, "initial_stock")
    validate_columns(picking_events, "picking_events")
    validate_columns(replenishment_events, "replenishment_events")