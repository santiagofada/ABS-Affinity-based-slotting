from __future__ import annotations

import numpy as np
import pandas as pd


def build_product_frequency(
    order_lines: pd.DataFrame,
    product_col: str = "product_id",
    order_col: str = "order_id",
) -> pd.Series:
    df = order_lines[[order_col, product_col]].drop_duplicates()
    freq = df.groupby(product_col).size().sort_index()
    return freq.astype(float)

def build_location_grid(n_rows: int, n_cols: int) -> pd.DataFrame:
    if n_rows <= 0 or n_cols <= 0:
        raise ValueError("n_rows y n_cols deben ser positivos")

    rows = []
    location_id = 0

    for r in range(n_rows):
        for c in range(n_cols):
            rows.append(
                {
                    "location_id": location_id,
                    "row": r,
                    "col": c,
                }
            )
            location_id += 1

    return pd.DataFrame(rows)


def build_location_costs(
    n_rows: int,
    n_cols: int,
    depot_row: int | None = None,
    depot_col: int | None = None,
) -> np.ndarray:
    grid = build_location_grid(n_rows, n_cols)

    if depot_row is None:
        depot_row = 0
    if depot_col is None:
        depot_col = n_cols // 2

    if not (0 <= depot_row < n_rows):
        raise ValueError("depot_row fuera de rango")
    if not (0 <= depot_col < n_cols):
        raise ValueError("depot_col fuera de rango")

    # costo = salir horizontalmente al pasillo central
    #       + recorrer verticalmente hasta el depot(o en sentido inverso)
    costs = (
        np.abs(grid["col"].to_numpy() - depot_col)
        + np.abs(grid["row"].to_numpy() - depot_row)
    ).astype(float)

    return costs + 1


def build_location_distance_matrix(
    n_rows: int,
    n_cols: int,
    central_col: int | None = None,
) -> np.ndarray:
    grid = build_location_grid(n_rows, n_cols)

    if central_col is None:
        central_col = n_cols // 2

    if not (0 <= central_col < n_cols):
        raise ValueError("central_col fuera de rango")

    rows = grid["row"].to_numpy()
    cols = grid["col"].to_numpy()

    n_locations = len(grid)
    D = np.zeros((n_locations, n_locations), dtype=float)

    for i in range(n_locations):
        for j in range(n_locations):
            if i == j:
                continue

            if cols[i] == cols[j]:
                D[i, j] = abs(rows[i] - rows[j])

            else:
                # puedo ir por arriba y bajar
                # o bajar y despues subir
                # pero siempre son 3 movimientos
                # salgo del pasillo + me muevo por el central + entro al otro pasillo
                d_top = (rows[i] + 1) + (rows[j] + 1) + abs(cols[i] - cols[j])
                d_bottom = (n_rows - rows[i]) + (n_rows - rows[j]) + abs(cols[i] - cols[j])
                D[i, j] = min(d_top, d_bottom)

    return D