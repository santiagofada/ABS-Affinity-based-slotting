"""Perfil de actividad de un deposito a partir de picking_events.parquet.

Genera, en el directorio de salida:
  pareto.dat   curva de Pareto de picks por SKU (x = fraccion acumulada de SKU,
               y = fraccion acumulada de picks), 101 puntos
  lineas.dat   distribucion de lineas por orden (k = 1..10 y 11+)
  resumen.txt  totales, parametros y este mismo script

Un pick es una fila de picking_events; no se usa la columna quantity.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path("/home/santiago.fada/personales/ABS-Affinity-based-slotting")
DATASET = sys.argv[1] if len(sys.argv) > 1 else "medium"
DATA_DIR = REPO / "data" / "v2" / DATASET
OUT_DIR = Path(__file__).resolve().parent

COL_SKU = "sku"
COL_ORDER = "order_id"
COL_BATCH = "batch_id"

df = pd.read_parquet(DATA_DIR / "picking_events.parquet",
                     columns=[COL_BATCH, COL_ORDER, COL_SKU, "quantity"])
manifest = json.loads((DATA_DIR / "manifest.json").read_text())

total_picks = len(df)
total_units = int(df["quantity"].sum())

# ---------------------------------------------------------------- 1. Pareto por SKU
picks_por_sku = df.groupby(COL_SKU).size().sort_values(ascending=False)
n_sku = len(picks_por_sku)
cum_picks = np.concatenate([[0.0], np.cumsum(picks_por_sku.to_numpy()) / total_picks])
cum_sku = np.arange(n_sku + 1) / n_sku

xs = np.round(np.linspace(0.0, 1.0, 101), 2)
ys = np.interp(xs, cum_sku, cum_picks)

k20 = int(round(0.2 * n_sku))
frac_20_exacta = cum_picks[k20]
frac_20_interp = float(np.interp(0.2, cum_sku, cum_picks))

# SKUs necesarias para explicar el 50% y el 80% de los picks
k50 = int(np.searchsorted(cum_picks, 0.5))
k80 = int(np.searchsorted(cum_picks, 0.8))

with open(OUT_DIR / "pareto.dat", "w") as f:
    f.write("x y\n")
    for x, y in zip(xs, ys):
        f.write(f"{x:.4f} {y:.4f}\n")

# ---------------------------------------------------------------- 2. lineas por orden
lineas_por_orden = df.groupby(COL_ORDER).size()
n_ordenes = len(lineas_por_orden)
media_lineas = lineas_por_orden.mean()
mediana_lineas = lineas_por_orden.median()
max_lineas = int(lineas_por_orden.max())

filas = []
for k in range(1, 12):
    sel = lineas_por_orden >= 11 if k == 11 else lineas_por_orden == k
    frac_ord = sel.sum() / n_ordenes
    frac_pk = lineas_por_orden[sel].sum() / total_picks
    filas.append((k, frac_ord, frac_pk, "11+" if k == 11 else str(k)))

with open(OUT_DIR / "lineas.dat", "w") as f:
    f.write("k frac_ordenes frac_picks etiqueta\n")
    for k, fo, fp, et in filas:
        f.write(f"{k} {fo:.4f} {fp:.4f} {et}\n")

# ---------------------------------------------------------------- chequeos
assert abs(sum(r[1] for r in filas) - 1) < 1e-9
assert abs(sum(r[2] for r in filas) - 1) < 1e-9
assert ys[0] == 0.0 and abs(ys[-1] - 1.0) < 1e-12
n_batches = df[COL_BATCH].nunique()
dup_orden_sku = total_picks - len(df[[COL_ORDER, COL_SKU]].drop_duplicates())

# ---------------------------------------------------------------- resumen
lineas = [
    f"dataset: {DATASET}  ({DATA_DIR})",
    f"archivo: picking_events.parquet, {total_picks} filas",
    f"manifest: num_orders={manifest['num_orders']}, num_batches={manifest['num_batches']}, "
    f"batch_size={manifest['preset']['batch_size']}, periodo {manifest['start_timestamp']} a {manifest['end_timestamp']}",
    "",
    "columnas usadas: sku (SKU), order_id (orden), batch_id (batch); quantity leida solo para informar unidades",
    "pick = fila de picking_events (no se cuentan unidades)",
    "",
    "--- Pareto de picks por SKU (pareto.dat) ---",
    f"total de picks: {total_picks}",
    f"total de unidades (suma de quantity, solo informativo): {total_units}",
    f"SKU con al menos un pick: {n_sku}",
    f"picks promedio por SKU: {total_picks / n_sku:.2f}",
    f"el 20% de las SKU mas pedidas ({k20} SKU) explica el {frac_20_exacta:.4f} de los picks "
    f"(interpolado en x=0.20: {frac_20_interp:.4f})",
    f"SKU necesarias para el 50% de los picks: {k50} ({k50 / n_sku:.4f} de las SKU)",
    f"SKU necesarias para el 80% de los picks: {k80} ({k80 / n_sku:.4f} de las SKU)",
    f"SKU mas pedida: {picks_por_sku.index[0]} con {int(picks_por_sku.iloc[0])} picks; "
    f"la menos pedida tiene {int(picks_por_sku.iloc[-1])}",
    "curva: puntos (i/n_sku, picks acumulados de las i SKU mas pedidas / total) interpolados "
    "linealmente en x = 0, 0.01, ..., 1",
    "",
    "--- Lineas por orden (lineas.dat) ---",
    f"total de ordenes: {n_ordenes}",
    f"media de lineas por orden: {media_lineas:.4f}",
    f"mediana: {mediana_lineas:.1f}, maximo: {max_lineas}",
    f"total de batches: {n_batches} (ordenes por batch: {n_ordenes / n_batches:.2f})",
    f"filas con (order_id, sku) repetido dentro de la misma orden: {dup_orden_sku} "
    "(se cuentan como picks distintos, son filas distintas)",
    "frac_ordenes = ordenes con k lineas / total de ordenes; "
    "frac_picks = lineas de esas ordenes / total de picks; k=11 agrupa 11 o mas",
    "",
    "--- script (perfil.py) ---",
    Path(__file__).read_text(),
]
(OUT_DIR / "resumen.txt").write_text("\n".join(lineas))
print("\n".join(lineas[:lineas.index("--- script (perfil.py) ---")]))
