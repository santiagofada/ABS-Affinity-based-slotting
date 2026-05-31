# Guía del proyecto — Affinity-Based Slotting (ABS)

> **Para quién es esto.** Para alguien con base técnica (sabe programar, leer
> Python) pero que **no necesita saber de optimización** ni conocer el proyecto.
> Al terminar de leer vas a entender *qué problema resolvemos*, *qué datos hay*,
> *cómo está organizado el código*, *qué está hecho y qué falta*, y *cómo correrlo*.

Otros documentos del repo y cuándo leerlos:
- [propuesta de tesis.md](propuesta%20de%20tesis.md) — el problema y la motivación (contexto de tesis).
- [Resumen y punto de partida.md](Resumen%20y%20punto%20de%20partida.md) — el marco teórico.
- [ARCHITECTURE.md](ARCHITECTURE.md) — los contratos del código en detalle (más técnico).
- [plan.md](plan.md) — la hoja de ruta paso a paso.
- **Este documento** es el resumen integrador: empezá por acá.

---

## 1. El problema, en palabras simples

Imaginá un **depósito** gigante de e-commerce (un *warehouse*). Cuando llega un
pedido, un operario camina por los pasillos, va a buscar cada producto a su
estante, y los junta para empaquetar. **La mayor parte del tiempo se va en
caminar.** Menos caminata = más pedidos por hora = menos costo.

La pregunta central del proyecto:

> **¿Dónde conviene ubicar cada producto para que los operarios caminen lo menos posible?**

A esto se le llama **slotting** (asignar a cada producto un "slot"/ubicación).

Dos ideas clave que usamos:

1. **Productos muy pedidos cerca de la salida.** Si un producto se pide todo el
   tiempo, ponelo cerca del punto de empaque (el *dock*) para no caminar de más.
2. **Productos que se piden juntos, cerca entre sí.** Si dos productos aparecen
   seguido en el mismo pedido (tienen **afinidad**), conviene que estén pegados,
   así el operario los agarra en un solo tramo del recorrido. Hoy en muchos
   depósitos las ubicaciones se eligen "a ojo" (donde hay hueco libre), sin mirar
   estas relaciones — y ahí está la oportunidad de mejora.

### Vocabulario mínimo (ver [Glosario](#9-glosario) al final)

- **SKU**: un producto distinto (ej. `SKU-00042`). Hay ~27.000.
- **Location** (ubicación): un hueco físico exacto (ej. `A14-21-B-02`). Hay 30.000.
- **Bay**: la "columna" de estantería donde están varias locations (ej. `A14-21`).
  Las distancias se miden entre bays. Hay 1.000 bays + el **dock**.
- **Dock**: el punto de empaque; todo recorrido empieza y termina ahí.
- **Batch**: un lote de pedidos que un operario recolecta de una sola pasada.
  Es nuestra unidad de "qué se pide junto".
- **Afinidad**: una medida de cuánto se piden juntos dos SKUs.

---

## 2. La idea de la solución (sin jerga pesada)

Tenemos el **historial real** de qué se pickeó, cuándo y desde dónde. Lo usamos
para:

1. **Medir la demanda** de cada SKU (¿cuánto se pide?).
2. **Medir la afinidad** entre SKUs (¿qué se pide junto?).
3. **Conocer la geometría** del depósito (¿qué tan lejos está cada cosa?).
4. Con todo eso, **proponer una mejor asignación** SKU → location.
5. **Evaluarla**: simular cuánto se caminaría con esa asignación y compararla
   contra cómo está hoy.

El núcleo matemático (el "ubicar óptimamente") es un problema conocido y **difícil**
(formalmente, un *Quadratic Assignment Problem*; no escala si se resuelve de forma
exacta). Por eso la estrategia es: primero **baselines** simples (reglas fáciles de
entender), después **heurísticas** (métodos aproximados más astutos), y comparar
todo contra el estado actual. **Esa parte de "resolver" todavía no está implementada**
— ver [sección 6](#6-qué-está-hecho-y-qué-falta). Lo que **sí** está listo es toda la
base que la rodea.

### El flujo de una comparación

Todo experimento tiene la misma forma (esta es la columna vertebral del proyecto):

```
   datos del problema        un método propone        el "juez" mide
        (instancia)   ───▶   una asignación   ───▶   cuánto se camina
   SlottingInstance          SlottingMethod           Evaluator
                             → Assignment              → Metrics
```

---

## 3. Los datos

Un dataset **sintético** (generado, no de un cliente real) que describe un
depósito de zona única y un mes de actividad. Están en
[data/raw/](data/raw/) como archivos `.parquet`. La descripción completa de
columnas está en [data/readme.txt](data/readme.txt). Resumen:

| Archivo | Qué es | Tamaño |
|---|---|---|
| `coordinates.parquet` | Cada bay con su posición (pasillo, número, x/y). | 1.001 filas |
| `distances.parquet` | Distancia caminando entre cada par de bays. | 500.500 filas |
| `initial_stock.parquet` | Qué SKU vive en cada location al inicio. | 30.000 filas |
| `picking_events.parquet` | Cada línea de picking: batch, momento, SKU, ubicación. | 174.597 filas |
| `replenishment_events.parquet` | Reposiciones de stock (incl. mudanzas de SKU). | 14.647 filas |

Números útiles para tener en la cabeza:
- **30 días** de historia (enero 2025), ~5.700 picks/día.
- **2.000 batches**, ~87 líneas por batch, **10 merchants** (vendedores).
- **27.000 SKUs** con ubicación, **3.000 locations vacías**.
- Distancias **en pulgadas** (se convierten a metros solo para reportar).

> **Dos decisiones importantes sobre los datos:**
> - **Slotting estático.** Los SKUs en realidad se mudan en el tiempo (hay 6.452
>   mudanzas por reposición). Nosotros ignoramos eso a propósito y trabajamos con
>   una "foto" fija: cada SKU vive en un lugar. Es el alcance clásico del problema.
> - **Distancia a nivel bay.** No modelamos cuánto se camina *dentro* de una bay
>   (entre estantes); dos productos en la misma bay están "a distancia 0".

---

## 4. Cómo está organizado el código

El paquete es [src/abs_affinity_based_slotting/](src/abs_affinity_based_slotting/).
Está pensado en **capas**, donde cada capa solo usa las de arriba:

```
 datos crudos   →  data/         leer y partir el historial
 features       →  demand/ warehouse/   demanda, afinidad, costos, distancias
 problema       →  slotting/     juntar todo en "la instancia" + la solución
 métodos        →  methods/      estrategias que proponen una asignación
 evaluación     →  evaluation/   el juez que mide cuánto se camina
 experimentos   →  scripts/ notebooks/   correr y comparar
```

Hay dos ideas de diseño que conviene entender porque se repiten:

**(a) "Datos del problema" (instancia) vs "una solución" (asignación).**
La `SlottingInstance` es de **solo lectura**: contiene lo dado (qué SKUs, qué
locations, demanda, distancias, afinidad). Una `Assignment` es **una propuesta**
de dónde poner cada SKU. Un método lee la instancia y devuelve una asignación;
nunca modifica la instancia.

**(b) Lo "computado" trabaja con números, no con nombres.**
Por dentro, la instancia usa **índices enteros** (el SKU número 0, 1, 2…) y
matrices de NumPy/SciPy, que son rápidas. Los nombres lindos (`SKU-00042`,
`A14-21`) se guardan aparte y se traducen solo en los bordes. Pandas se usa para
leer/escribir archivos, **no** en el cálculo pesado.

**(c) Las piezas intercambiables siguen un patrón único: contrato + registro.**
Hay tres "familias" que tendrán muchas variantes (métodos de optimización, formas
de medir afinidad, formas de clusterizar). Para que sean **modulares**, cada
familia define un *contrato* (una interfaz) y un *registro* (un diccionario
`nombre → implementación`). Agregar una variante nueva = escribir una clase y
registrarla; nada más cambia. (Detalle en [ARCHITECTURE.md §3.6](ARCHITECTURE.md).)

---

## 5. Recorrido por los módulos (qué hace cada uno)

### Configuración y utilidades
- [config.py](src/abs_affinity_based_slotting/config.py) — rutas del proyecto,
  la constante `DOCK`, y la conversión pulgadas↔metros.
- [registry.py](src/abs_affinity_based_slotting/registry.py) — el `Registry`
  genérico (`nombre → implementación`) que comparten las familias modulares.

### `data/` — leer y preparar el historial
- [data/loaders.py](src/abs_affinity_based_slotting/data/loaders.py) —
  `WarehouseDataLoader`: lee los 5 parquets crudos a DataFrames.
- [data/schemas.py](src/abs_affinity_based_slotting/data/schemas.py) — valida
  que cada tabla tenga las columnas esperadas.
- [data/io.py](src/abs_affinity_based_slotting/data/io.py) — leer/escribir los
  artefactos derivados (`read_parquet`, `write_parquet`).
- [data/split.py](src/abs_affinity_based_slotting/data/split.py) —
  `split_picking_events`: parte el historial en **train** (para aprender demanda
  y afinidad) y **test** (para evaluar). El corte es temporal y **respeta batches
  enteros** para no "hacer trampa" (no mezclar info del futuro en el pasado).

### `demand/` — qué se pide y qué se pide junto
- [demand/sku_demand.py](src/abs_affinity_based_slotting/demand/sku_demand.py) —
  `build_sku_demand`: una fila por SKU con su demanda (líneas de pick, unidades,
  en cuántos batches aparece, etc.).
- [demand/affinity.py](src/abs_affinity_based_slotting/demand/affinity.py) — el
  **contrato** `AffinityBuilder` (cómo se construye la matriz de afinidad `A`) +
  su registro. Las fórmulas concretas (Jaccard, coseno, lift…) son parte de la
  optimización y **aún no están implementadas**.

### `warehouse/` — el espacio físico
- [warehouse/locations.py](src/abs_affinity_based_slotting/warehouse/locations.py)
  — locations a partir del stock inicial (con flag de "vacía").
- [warehouse/distances.py](src/abs_affinity_based_slotting/warehouse/distances.py)
  — matriz simétrica de distancias entre bays y distancia de cada bay al dock.
- [warehouse/costs.py](src/abs_affinity_based_slotting/warehouse/costs.py) —
  `build_location_costs`: el "costo de acceso" de cada location (= su distancia
  al dock).

### `slotting/` — el problema y la solución
- [slotting/instance.py](src/abs_affinity_based_slotting/slotting/instance.py) —
  `SlottingInstance`: el objeto-problema, **inmutable y numérico**. Junta SKUs,
  locations, demanda, costos, geometría y afinidad. Valida que todo sea coherente.
- [slotting/build.py](src/abs_affinity_based_slotting/slotting/build.py) —
  `build_instance`: arma la instancia a partir de las tablas (es el único lugar
  donde pandas toca la instancia).
- [slotting/assignment.py](src/abs_affinity_based_slotting/slotting/assignment.py)
  — `Assignment`: una solución (mapa SKU↔location). Permite consultar e
  intercambiar ubicaciones de forma eficiente (clave para las heurísticas).

### `methods/` — las estrategias que proponen una asignación
- [methods/base.py](src/abs_affinity_based_slotting/methods/base.py) — el
  **contrato** `SlottingMethod` (`solve(instancia) → asignación`) + su registro.
- [methods/current.py](src/abs_affinity_based_slotting/methods/current.py) — el
  baseline **estado actual**: lee del stock inicial dónde está hoy cada SKU. Es
  el punto de comparación principal. (Los demás métodos están vacíos: ver abajo.)

### `clustering.py` — agrupar SKUs (para métodos en dos etapas)
- [clustering.py](src/abs_affinity_based_slotting/clustering.py) — el **contrato**
  `ClusteringStrategy` (`cluster(instancia) → etiqueta por SKU`) + su registro.
  Implementaciones, aún no.

### `evaluation/` — el juez
- [evaluation/routes.py](src/abs_affinity_based_slotting/evaluation/routes.py) —
  la matemática de **un recorrido**: dado el orden de visita, suma las distancias
  `dock → ubicaciones → dock`.
- [evaluation/metrics.py](src/abs_affinity_based_slotting/evaluation/metrics.py) —
  `Metrics` y `summarize`: agrega los costos de todos los batches (total, media,
  mediana, percentil 95).
- [evaluation/evaluator.py](src/abs_affinity_based_slotting/evaluation/evaluator.py)
  — `Evaluator`: para cada batch de test, mira dónde pone la asignación cada SKU,
  ordena el recorrido en "snake" (recorriendo pasillos en orden) y suma distancias.
  **Exige cobertura 100%**: si un SKU del test no está ubicado, es un error (no lo
  tapa).

### Orquestación
- [scripts/build_inputs.py](scripts/build_inputs.py) — corre la preparación de
  datos y deja los artefactos en `data/processed/`.
- [notebooks/00_EDA.ipynb](notebooks/00_EDA.ipynb) — exploración inicial de datos.
- [notebooks/test.ipynb](notebooks/test.ipynb) — pruebas que validan que todo lo
  construido funciona (smoke-tests).

---

## 6. Qué está hecho y qué falta

### ✅ Hecho — toda la base "pre-optimización"

Hay un **camino completo que funciona de punta a punta**: leer datos → armar la
instancia → tomar una asignación → evaluarla y obtener un número. Ya corrimos el
**primer benchmark** (el costo del slotting actual sobre el test):

| Slotting actual sobre test | pulgadas | metros |
|---|---|---|
| batches evaluados | 400 | — |
| distancia total | 20.959.192 | ~532.363 m |
| media por batch | 52.398 | ~1.331 m |
| mediana por batch | 52.540 | ~1.335 m |
| p95 por batch | 57.233 | ~1.454 m |

Concretamente, está listo: configuración, lectura y validación de datos, split
train/test, demanda por SKU, distancias y costos del depósito, la instancia del
problema (+ su builder), la representación de una solución, el baseline `current`,
el evaluador completo, y **los tres contratos modulares** (métodos, afinidad,
clustering) con su sistema de registro.

### ⏳ Falta — la parte de optimización (y dos cosas de soporte)

**Soporte (no es optimización, son insumos/herramientas):**
- [demand/cooccurrence.py](src/abs_affinity_based_slotting/demand/cooccurrence.py)
  — contar qué pares de SKU aparecen en los mismos batches. Es el **insumo** de
  toda afinidad (puro conteo).
- [demand/merchants.py](src/abs_affinity_based_slotting/demand/merchants.py) —
  análisis por merchant/vendedor.
- [plotting.py](src/abs_affinity_based_slotting/plotting.py) — figuras.
- **Harness de experimentos** — un comparador que recorra los métodos
  registrados, los evalúe y arme una tabla de resultados.

**Optimización propiamente dicha (el corazón de la tesis, aún por hacer):**
- Implementar los `AffinityBuilder` (Jaccard, coseno, lift…) en
  [demand/affinity.py](src/abs_affinity_based_slotting/demand/affinity.py).
- [slotting/objective.py](src/abs_affinity_based_slotting/slotting/objective.py)
  — la función de costo (estilo QAP) que las heurísticas minimizan.
- Los métodos `.solve` en [methods/](src/abs_affinity_based_slotting/methods/):
  `abc.py` (por frecuencia), `merchant.py`, `swaps.py` (búsqueda local),
  `clustering.py` (dos etapas), `anchors.py` (productos ancla).
- Las `ClusteringStrategy` concretas.

> **Importante:** todo lo que falta **enchufa** sobre lo que ya existe sin
> reescribir nada. Un método nuevo es una clase que implementa `solve` y se
> registra; el evaluador y el harness no se tocan.

---

## 7. Cómo correrlo

Requisitos: Python ≥ 3.11. El entorno se creó con [`uv`](https://github.com/astral-sh/uv).

```bash
# 1. Crear el entorno e instalar el paquete (editable)
uv venv
uv pip install -e .

# 2. Generar los artefactos derivados (split, demanda, costos)
.venv/bin/python scripts/build_inputs.py
#   -> escribe data/processed/{picking_train,picking_test,sku_demand,location_costs}.parquet

# 3. Validar que todo funciona
#   abrir notebooks/test.ipynb con el kernel del .venv y correr las celdas
```

Ejemplo mínimo de uso del pipeline completo (obtener el benchmark actual):

```python
from abs_affinity_based_slotting.config import RAW_DIR, PROCESSED_DIR
from abs_affinity_based_slotting.data import WarehouseDataLoader, read_parquet
from abs_affinity_based_slotting.warehouse import build_bay_distance_matrix
from abs_affinity_based_slotting.slotting import build_instance
from abs_affinity_based_slotting.methods import method_registry
from abs_affinity_based_slotting.evaluation import Evaluator

data = WarehouseDataLoader(RAW_DIR).load_all()
inst = build_instance(
    read_parquet(PROCESSED_DIR / "sku_demand.parquet"),
    read_parquet(PROCESSED_DIR / "location_costs.parquet"),
    build_bay_distance_matrix(data.distances),
    skus=data.initial_stock["sku"].dropna().to_numpy(),  # universo = todos los SKUs
)
method = method_registry.get("current")(data.initial_stock)
assignment = method.solve(inst)

evaluator = Evaluator.from_tables(data.coordinates, data.distances, data.initial_stock)
metrics = evaluator.evaluate(assignment, read_parquet(PROCESSED_DIR / "picking_test.parquet"))
print(metrics)
```

---

## 8. Decisiones de diseño ya tomadas (para no rediscutir)

| Decisión | Elección | Por qué |
|---|---|---|
| Qué SKUs se ubican | **Todos** los ~27.000 del stock | Garantiza que el test se pueda evaluar al 100% (toda asignación ubica todo). |
| Dinámica de stock | **Estática** (una foto fija) | Alcance clásico del problema; las mudanzas se ignoran a propósito. |
| Distancia | A nivel **bay** | Es como vienen los datos; no se modela el viaje dentro de una bay. |
| Corte train/test | Temporal, **por batch** | Evita filtrar información del futuro al pasado. |
| Demanda principal | `pick_lines` | Cada línea es una acción real de picking. |
| Orden de recorrido | **Snake** (por pasillo) | Como camina un operario real; recalculado según la asignación que se evalúa. |
| SKU de test sin ubicar | **Error** | Con cobertura 100% no debería pasar; si pasa, es un bug. |

---

## 9. Glosario

- **SKU** (*Stock Keeping Unit*): un producto distinto.
- **Location**: hueco físico exacto donde vive un SKU.
- **Bay**: columna de estantería; unidad a la que se miden las distancias.
- **Dock**: estación de empaque; inicio y fin de cada recorrido.
- **Batch**: lote de pedidos recolectado de una sola pasada; unidad de "qué se pide junto".
- **Picking**: el acto de ir a buscar productos para un pedido.
- **Slotting**: decidir en qué location va cada SKU.
- **Afinidad**: medida de cuánto se piden juntos dos SKUs.
- **Demanda**: cuánto se pide un SKU.
- **Baseline**: método simple de referencia (ej. el estado actual).
- **Heurística**: método aproximado que busca una buena solución sin garantizar la óptima.
- **Train / Test**: datos para *aprender* (pasado) vs para *evaluar* (futuro).
- **Instancia**: todos los datos de un problema concreto a resolver.
- **Asignación**: una propuesta de SKU → location.
- **QAP** (*Quadratic Assignment Problem*): la formulación matemática del problema;
  es difícil de resolver de forma exacta a gran escala.
- **Contrato / Registro**: una interfaz común + un catálogo de implementaciones,
  para que las piezas sean intercambiables.
```
