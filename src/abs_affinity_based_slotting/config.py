"""Project-wide paths and constants."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"

#: Warehouse sizes available in the second dataset. Variants of a size generated
#: with other parameters live next to them under ``data/v2`` (for example
#: ``medium-alpha-1.3``, the medium preset with a steeper Pareto demand).
V2_SIZES = ("small", "medium", "big")


def dataset_dir(version: str, size: str | None = None) -> Path:
    """Return the folder holding the five parquet tables of one dataset.

    ``v1`` is the original 30-day warehouse (no order id), a single folder.
    ``v2`` (2026-09) comes in three sizes, each with six months of history and
    an ``order_id`` column in the picking events; ``size`` picks one. Any other
    folder under ``data/v2`` (a variant such as ``medium-alpha-1.3``) is accepted
    as long as it exists.
    """
    if version == "v1":
        if size is not None:
            raise ValueError("dataset v1 has a single warehouse; do not pass size")
        path = DATA_DIR / "v1" / "raw"
    elif version == "v2":
        if size is None:
            raise ValueError(f"dataset v2 needs a size: one of {V2_SIZES} or a variant folder under {DATA_DIR / 'v2'}")
        path = DATA_DIR / "v2" / size
    else:
        raise ValueError(f"unknown dataset version {version!r}; expected 'v1' or 'v2'")

    if not path.is_dir():
        raise FileNotFoundError(f"dataset folder not found: {path}")
    return path

#: Identifier of the dock / packing station in the layout tables.
DOCK = "DOCK"

#: Distances and coordinates in the dataset are stored in inches.
INCHES_PER_METER = 39.3701


def inches_to_meters(inches: float) -> float:
    return inches / INCHES_PER_METER


def _load_dotenv(path: Path = PROJECT_ROOT / ".env") -> None:
    """Load KEY=VALUE lines from a .env file into os.environ (no overwrite).

    Minimal parser so secrets (e.g. the optimization solver license) live in a
    gitignored .env instead of in the source. Lines that are blank or start with
    '#' are skipped. Existing environment variables take precedence.
    """
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def solver_license_params() -> dict | None:
    """Return the optimization solver's license parameters, or None.

    Reads SOLVER_LICENSE_ACCESS_ID, SOLVER_LICENSE_SECRET and SOLVER_LICENSE_ID
    from the environment (loading .env first). Returns None if any is missing, in
    which case the solver falls back to its default license discovery.
    """
    _load_dotenv()
    access_id = os.environ.get("SOLVER_LICENSE_ACCESS_ID")
    secret = os.environ.get("SOLVER_LICENSE_SECRET")
    license_id = os.environ.get("SOLVER_LICENSE_ID")

    if not (access_id and secret and license_id):
        return None

    # These keys are the solver backend's expected names (the boundary where the
    # specific backend is touched).
    return {
        "WLSACCESSID": access_id,
        "WLSSECRET": secret,
        "LICENSEID": int(license_id),
    }


def make_solver_env():
    """Build the optimization solver environment, with the license if present.

    The backend is imported lazily so the rest of the package does not depend on
    it. Falls back to the solver's default license discovery when no license
    parameters are set.
    """
    import gurobipy as gp

    params = solver_license_params()
    if params is None:
        return gp.Env()
    return gp.Env(params=params)
