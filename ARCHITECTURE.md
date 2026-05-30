# Arquitectura del proyecto

Documento de referencia sobre **cómo está organizado el código** y, sobre todo,
**cuáles son los contratos** que mantienen todo comparable y extensible. El
[plan.md](plan.md) describe el *orden de trabajo*; este documento describe la
*estructura*. Ante una duda de diseño, este archivo manda.

---

## 1. Principios guía

1. **Generalidad sobre conveniencia.** Las piezas no fijan decisiones que todavía
   no tomamos. Ejemplo concreto: *qué* SKUs se ubican (todos los de stock, solo
   los con demanda, un subconjunto por merchant) es un **parámetro** del
   constructor de la instancia, no algo hardcodeado.
2. **Un solo contrato por rol.** Todos los métodos de slotting implementan la
   misma interfaz; todas las soluciones tienen la misma forma; un solo evaluador
   juzga a todos. Agregar una heurística = una clase nueva, sin tocar el resto.
3. **`objective` ≠ `evaluator`.** Distinción central:
   - **`objective`**: la función de costo (estilo QAP) que las heurísticas
     *optimizan*. Se construye sobre **train**, es rápida y es una *aproximación*.
   - **`evaluator`**: el juez *realista* que simula recorrer los batches de
     **test** bajo una asignación dada. Es la métrica que reportamos.

   Optimizar y evaluar con la misma función sería hacerse trampa al solitario.
4. **Inmutabilidad de los datos del problema.** La `SlottingInstance` es de solo
   lectura. Una solución (`Assignment`) es un objeto aparte; los métodos producen
   asignaciones, nunca mutan la instancia.
5. **Reproducibilidad.** Sin estado global oculto. Semillas explícitas, rutas
   centralizadas en `config.py`, artefactos derivados regenerables con un script.
6. **Simple antes que sofisticado.** Pandas/numpy puro mientras alcance.
   Abstraer solo cuando hay más de un caso real que lo justifique.

---

## 2. Vista en capas

```
            ┌─────────────────────────────────────────────┐
  raw data  │  data/raw/*.parquet  (dataset, inmutable)    │
            └───────────────────────┬─────────────────────┘
                                    │  loaders + schemas
            ┌───────────────────────▼─────────────────────┐
  features  │  demand/   warehouse/   (+ split temporal)   │
            │  demanda, afinidad, costos, distancias       │
            └───────────────────────┬─────────────────────┘
                                    │  builders
            ┌───────────────────────▼─────────────────────┐
  problema  │  slotting/instance.py   SlottingInstance     │
            │  slotting/objective.py  función de costo     │
            └───────────────────────┬─────────────────────┘
                                    │
            ┌───────────────────────▼─────────────────────┐
  métodos   │  methods/   SlottingMethod -> Assignment     │
            │  current · abc · merchant · swaps · ...       │
            └───────────────────────┬─────────────────────┘
                                    │  Assignment
            ┌───────────────────────▼─────────────────────┐
  juicio    │  evaluation/   Evaluator -> Metrics          │
            │  routes · metrics · evaluator (sobre test)   │
            └───────────────────────┬─────────────────────┘
                                    │
            ┌───────────────────────▼─────────────────────┐
  experimen.│  scripts/ · notebooks/   comparación,        │
            │  tablas y figuras -> reports/                │
            └─────────────────────────────────────────────┘
```

Regla de dependencias: cada capa solo conoce a las de **arriba**. `methods/` no
sabe nada de `evaluation/`; `evaluation/` no sabe qué método produjo la
asignación. El pegamento vive en la capa de experimentos.

El flujo de un experimento es siempre el mismo:

```
instance ── method.solve() ──▶ assignment ── evaluator.evaluate() ──▶ metrics
```

---

## 3. Contratos core

Firmas **provisorias** (orientativas, no definitivas). Lo que importa es el rol
y las responsabilidades de cada pieza.

### 3.1 `SlottingInstance` — datos del problema (inmutable)

Todo lo necesario para plantear y resolver una instancia, y nada más.
Representación **numérica por posiciones**: los ids externos se guardan como
arrays y la lógica interna trabaja con índices enteros. Sin pandas adentro.

```python
@dataclass(frozen=True, eq=False, repr=False)
class SlottingInstance:
    # ids externos (posición i del array <-> índice interno i)
    sku_ids: np.ndarray
    location_ids: np.ndarray
    bay_ids: np.ndarray
    # datos numéricos alineados por posición
    demand: np.ndarray          # (n_skus,)        demanda por SKU
    location_cost: np.ndarray   # (n_locations,)   costo de acceso (al dock)
    location_bay: np.ndarray    # (n_locations,)   índice de bay de cada location
    bay_distance: np.ndarray    # (n_bays, n_bays) distancias entre bays
    affinity: csr_matrix        # (n_skus, n_skus) afinidad dispersa (CSR)
    merchant_ids: np.ndarray | None = None
```

- **Espacio de índices vs ids.** Métodos y objetivo operan con índices enteros
  (rápido); la traducción a ids ocurre solo en los bordes vía `sku_index` /
  `location_index` / `bay_index` y sus inversos.
- El **universo de SKUs y de locations se pasa al builder**, no se asume. Esto
  deja abierto: todos los SKUs, solo los con demanda, por merchant, etc.
- **Afinidad dispersa (CSR)** y distancias a nivel bay porque son las que escalan
  mal (ver QAP en
  [Resumen y punto de partida.md](Resumen%20y%20punto%20de%20partida.md)).
- Validación exhaustiva en `__post_init__` (unicidad, shapes, NaN,
  no-negatividad, índices de bay en rango, factibilidad `n_locations >= n_skus`).
- **El armado desde las tablas pandas vive aparte** (`slotting/build.py`,
  `build_instance(...)`), para que la instancia no toque pandas ni al construirse.

### 3.2 `Assignment` — una solución (biyección parcial)

```python
class Assignment:
    """Mapa SKU <-> location. Cada SKU en una location; cada location <= un SKU."""
    def location_of(self, sku) -> location
    def sku_at(self, location) -> sku | None
    def to_frame(self) -> pd.DataFrame      # representación canónica, serializable
    def to_dict(self) -> dict               # copia del mapa sku -> location
    def swap(self, sku_a, sku_b) -> None     # in-place, O(1), para búsqueda local
    def copy(self) -> "Assignment"           # snapshot independiente
```

- **Mutable in-place**: `swap` modifica el objeto (O(1) con dos dicts) porque la
  búsqueda local hace miles de swaps; `copy()` da un snapshot de la mejor solución.
- Representación **canónica** = DataFrame (`sku`, `location_id`), fácil de
  guardar y comparar entre estrategias.

### 3.3 `SlottingMethod` — estrategia (patrón Strategy)

```python
class SlottingMethod(Protocol):
    name: str
    def solve(self, instance: SlottingInstance) -> Assignment: ...
```

Cada baseline o heurística es una clase que implementa `solve`. Comparten firma,
así que el código de experimentos las trata de forma uniforme. Familias previstas
en `methods/`: `current` (estado actual), `abc` (frecuencia), `merchant`,
`swaps` (búsqueda local), `clustering`, `anchors`.

### 3.4 `objective` — función de costo a optimizar

```python
def slotting_cost(assignment, instance, *, lam: float) -> float
```

Combina el término lineal (demanda × costo de acceso) y el cuadrático
(afinidad × distancia), con `lam` ponderando ambos. Es lo que minimizan las
heurísticas. Necesita un **delta de costo** eficiente para swaps:

```python
def swap_delta(assignment, instance, sku_a, sku_b, *, lam) -> float
```

### 3.5 `Evaluator` — el juez (sobre test)

```python
@dataclass(frozen=True)
class Metrics:
    total_distance: float
    mean_batch_distance: float
    median_batch_distance: float
    p95_batch_distance: float
    runtime_seconds: float | None = None

class Evaluator:
    def evaluate(self, assignment: Assignment,
                 picking_test: pd.DataFrame) -> Metrics: ...
```

Para cada batch de test: re-ubica sus SKUs según `assignment`, ordena el
recorrido (snake / orden de picking) y suma distancias. Es independiente del
método que generó la asignación.

---

## 4. Convenciones

- **Granularidad espacial.** Los SKUs se ubican en `location`, pero el costo y la
  distancia se aproximan a nivel `bay` (no se modela el viaje dentro del bay).
- **Unidad de coocurrencia y de evaluación.** El `batch_id`. El split temporal se
  hace a nivel batch para no partir un batch entre train y test.
- **Train vs test.** Demanda y afinidad se construyen **solo con train**. El
  `Evaluator` usa **solo test**. Nunca al revés.
- **Datos.** Parquet para todo lo tabular. `data/raw/` es inmutable y versionado;
  `data/processed/` es derivado y regenerable (`scripts/build_inputs.py`).
- **Rutas y constantes.** Centralizadas en
  [config.py](src/abs_affinity_based_slotting/config.py). Nada de paths relativos
  sueltos. Distancias en pulgadas; conversión a metros solo para reportar.
- **API pública.** Cada subpaquete expone su interfaz en su `__init__.py`.
- **Notebooks.** Solo exploración y figuras. La lógica vive en `src/`; los
  notebooks la importan, no la definen.
- **Naming del dataset.** Ver [data/readme.txt](data/readme.txt)
  (`bay_id`, `location_name`, `sku`, `merchant`, `DOCK`).

---

## 5. Mapa del paquete

```
src/abs_affinity_based_slotting/
├── config.py            rutas, constante DOCK, conversión pulgadas<->metros   [hecho]
├── data/
│   ├── loaders.py       lectura de data/raw (WarehouseDataLoader)             [hecho]
│   ├── schemas.py       validación de columnas                                [hecho]
│   ├── io.py            read/write de artefactos processed                    [hecho]
│   └── split.py         split temporal train/test a nivel batch               [hecho]
├── demand/
│   ├── sku_demand.py    demanda por SKU desde picking                         [hecho]
│   ├── cooccurrence.py  pares de SKU coocurrentes por batch                   [pendiente]
│   ├── affinity.py      métricas de afinidad (jaccard, cosine, lift, ...)     [pendiente]
│   └── merchants.py     estructura/afinidad por merchant                      [pendiente]
├── warehouse/
│   ├── locations.py     locations desde initial_stock (+ is_empty)            [hecho]
│   ├── distances.py     matriz de distancias entre bays / al dock            [hecho]
│   └── costs.py         costo de acceso por location                          [hecho]
├── slotting/
│   ├── instance.py      SlottingInstance (datos del problema, numérico)       [hecho]
│   ├── build.py         build_instance: tablas processed -> instancia         [pendiente]
│   ├── assignment.py    Assignment (solución, biyección parcial)              [hecho]
│   └── objective.py     función de costo + delta de swap                      [pendiente]
├── methods/
│   ├── current.py       baseline: slotting actual (snapshot)                  [pendiente]
│   ├── abc.py           baseline: frecuencia / ABC                            [pendiente]
│   ├── merchant.py      baseline: agrupado por merchant                       [pendiente]
│   ├── swaps.py         heurística: búsqueda local por swaps                  [pendiente]
│   ├── clustering.py    heurística: clustering por afinidad                   [pendiente]
│   └── anchors.py       heurística: productos ancla                           [pendiente]
├── evaluation/
│   ├── routes.py        costo de recorrido de un batch                        [pendiente]
│   ├── metrics.py       Metrics + agregaciones                                [pendiente]
│   └── evaluator.py     Evaluator (orquesta sobre test)                       [pendiente]
└── plotting.py          figuras para el documento                            [pendiente]

scripts/build_inputs.py  genera data/processed/*                               [hecho]
```

---

## 6. Decisiones de diseño registradas

| Decisión | Elección | Motivo / estado |
|---|---|---|
| Universo de SKUs a ubicar | **Configurable** (parámetro de la instancia) | Aún no decidido; mantenerlo general. |
| Dinámica de stock (relocations) | **Slotting estático** (snapshot) | Alcance clásico del SLAP; simplificación documentada. Hay 6.452 relocations en los datos que ignoramos a propósito. |
| Granularidad de distancia | Nivel **bay** | Es como vienen las distancias; viaje intra-bay no modelado. |
| Unidad del split temporal | **batch** | Evita fuga; batch es unidad de coocurrencia y evaluación. |
| Métrica de demanda primaria | `pick_lines` | Cada línea es una acción operativa de picking. |
| Métrica de afinidad inicial | A definir (jaccard candidato) | Se comparan varias antes de fijar una. |

---

## 7. Preguntas abiertas

- Universo de SKUs definitivo y qué hacer con SKUs que aparecen en test pero no
  en train.
- Cómo se asignan locations vacías / sobrantes (hay más locations que SKUs).
- Orden de recorrido exacto en el `Evaluator` (snake puro vs. heurística de ruta).
- Valor(es) de `lam` en la función objetivo y cómo se calibra.
- Definición de "zona" para los métodos en dos etapas (clustering, merchant).
```
