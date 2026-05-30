"""Project-wide paths and constants."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"

#: Identifier of the dock / packing station in the layout tables.
DOCK = "DOCK"

#: Distances and coordinates in the dataset are stored in inches.
INCHES_PER_METER = 39.3701


def inches_to_meters(inches: float) -> float:
    return inches / INCHES_PER_METER
