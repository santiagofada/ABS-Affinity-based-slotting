# Affinity-Based Slotting — Documentación técnica

**Documento maestro del proyecto.** Fuente única de la documentación técnica:
formulación del problema, modelado, metodología de evaluación, arquitectura de la
implementación, estado y hoja de ruta. Ante una duda de diseño, este archivo manda.

Asume lector con base cuantitativa y de ingeniería de software; no asume
familiaridad previa con optimización combinatoria ni con el dominio logístico.

Documentos complementarios (propósito distinto, se mantienen aparte):
[propuesta de tesis.md](propuesta%20de%20tesis.md) (propuesta formal: directores,
cronograma, bibliografía) y [Resumen y punto de partida.md](Resumen%20y%20punto%20de%20partida.md)
(estado del arte y revisión de literatura).

**Índice**

- Parte A — Problema y modelo: 1 alcance · 2 formulación · 3 datos→modelo · 4 afinidad · 5 evaluación
- Parte B — Arquitectura: 6 principios · 7 capas · 8 contratos · 9 modularidad · 10 convenciones · 11 estructura del paquete · 12 decisiones
- Parte C — Estado y plan: 13 estado · 14 roadmap · 15 abierto/futuro · 16 operación · 17 glosario · 18 referencias

---

# Parte A — Problema y modelo

## 1. Problema y alcance

### 1.1 Contexto operativo

En un centro de distribución (*warehouse*) el costo dominante del cumplimiento de
órdenes es el **desplazamiento del operario** durante el picking: recuperar los
ítems de una orden implica recorrer pasillos hasta cada ubicación. La asignación
de productos a ubicaciones (*slotting*) determina esos recorridos y, por lo tanto,
la productividad del depósito. En la práctica el slotting suele decidirse de forma
heurística (por disponibilidad de hueco o rotación individual), ignorando que los
productos no se demandan de forma aislada: existen **patrones de co-demanda**
(afinidades) que, si no se explotan, producen recorridos redundantes.

### 1.2 Definición del problema

El problema pertenece a la familia **Storage Location Assignment Problem (SLAP)**,
y específicamente a su variante de **correlated storage assignment** /
*affinity-based slotting*: ubicar los SKUs de modo de minimizar el costo de
picking esperado, considerando tanto la **frecuencia individual** de demanda como
la **afinidad** (co-ocurrencia en órdenes) entre pares de SKUs.

### 1.3 Alcance y no-objetivos

| Dentro de alcance | Fuera de alcance (explícito) |
|---|---|
| Slotting **estático** (una asignación SKU→ubicación) | Re-slotting dinámico / mudanzas en el tiempo |
| Minimizar distancia de picking estimada | Modelado de congestión, mano de obra, layout design |
| Comparación rigurosa de estrategias sobre datos retenidos | Resolución exacta a escala industrial |
| Distancia a nivel **bay** (dato provisto) | Modelado del viaje intra-bay (estante/posición) |

El objetivo metodológico central es construir una **base de comparación honesta**
(instancia, función de costo, evaluación out-of-sample) sobre la cual medir
distintas estrategias de asignación.

## 2. Formulación matemática

### 2.1 Notación

| Símbolo | Significado |
|---|---|
| $I$, $n=\lvert I\rvert$ | conjunto de SKUs a ubicar |
| $L$, $m=\lvert L\rvert$ | conjunto de ubicaciones candidatas, $m \ge n$ |
| $f_i \ge 0$ | demanda del SKU $i$ (métrica primaria: `pick_lines`) |
| $c_\ell \ge 0$ | costo de acceso de la ubicación $\ell$ (distancia al dock) |
| $a_{ij} \ge 0$ | afinidad entre SKUs $i,j$; simétrica, $a_{ii}=0$ |
| $D_{\ell k} \ge 0$ | distancia entre ubicaciones $\ell,k$ (vía sus bays); simétrica, $D_{\ell\ell}=0$ |
| $x_{i\ell}\in\{0,1\}$ | variable de decisión: $1$ si $i$ se ubica en $\ell$ |
| $\lambda\in[0,1]$ | peso relativo demanda-acceso vs afinidad-proximidad |

### 2.2 Programa cuadrático binario

$$
\min_{x}\;\; \lambda \sum_{i\in I}\sum_{\ell\in L} f_i\, c_\ell\, x_{i\ell}
\;+\; (1-\lambda)\sum_{i\in I}\sum_{j\in I}\sum_{\ell\in L}\sum_{k\in L}
a_{ij}\, D_{\ell k}\, x_{i\ell}\, x_{jk}
$$

sujeto a

$$
\sum_{\ell\in L} x_{i\ell}=1\ \ \forall i\in I,\qquad
\sum_{i\in I} x_{i\ell}\le 1\ \ \forall \ell\in L,\qquad
x_{i\ell}\in\{0,1\}.
$$

El **término lineal** modela "ubicar SKUs frecuentes en posiciones de bajo costo
de acceso"; el **término cuadrático** penaliza ubicar lejos a SKUs con alta
afinidad. Las restricciones imponen que cada SKU ocupe exactamente una ubicación y
cada ubicación a lo sumo un SKU (la desigualdad admite ubicaciones vacías, $m>n$).

### 2.3 Vista como permutación y relación con el QAP

Restringido a las $n$ ubicaciones efectivamente usadas, una solución factible es
una **inyección** $\pi: I \to L$, y el costo se reescribe como

$$
C(\pi)=\lambda\sum_{i} f_i\, c_{\pi(i)}
\;+\;(1-\lambda)\sum_{i}\sum_{j} a_{ij}\, D_{\pi(i)\pi(j)} .
$$

Esta es la forma de **Koopmans–Beckmann** del **Quadratic Assignment Problem
(QAP)** con término lineal. El QAP es **NP-hard** y difícil incluso para instancias
moderadas; no admite resolución exacta a la escala de este problema. De ahí la
estrategia por baselines + heurísticas (sección 14).

### 2.4 Escala y consecuencias computacionales

Con $n\approx 27\,000$ y $m\approx 30\,000$: variables binarias
$n\cdot m \approx 8.1\times 10^{8}$; afinidad densa $n^2 \approx 7.3\times 10^{8}$
entradas; evaluación completa del término cuadrático $O(n^2)$. Dos consecuencias de
diseño, ambas adoptadas:

1. **Afinidad dispersa.** $a_{ij}$ se almacena como matriz **CSR** y se restringe a
   los vínculos más fuertes (top-$k$ por SKU, sección 4.2): aristas de $O(n^2)$ a $O(nk)$.
2. **Evaluación incremental de movimientos.** La búsqueda local no recomputa
   $C(\pi)$ sino su **delta** ante un intercambio (sección 2.5).

### 2.5 Delta de costo de un intercambio (swap)

Intercambiar las ubicaciones de dos SKUs $u,v$ con $p=\pi(u)$, $q=\pi(v)$. El
cambio $\Delta = C(\pi')-C(\pi)$ se calcula sin recomputar la suma global. Con $a$
y $D$ simétricas y diagonal nula:

$$
\Delta_{\text{lin}} = (f_u - f_v)\,(c_q - c_p),
$$

$$
\Delta_{\text{quad}} = 2\!\!\sum_{k\neq u,v}\!\! (a_{uk}-a_{vk})\,
\bigl(D_{q,\pi(k)}-D_{p,\pi(k)}\bigr),
\qquad
\Delta = \lambda\,\Delta_{\text{lin}} + (1-\lambda)\,\Delta_{\text{quad}} .
$$

(El factor $2$ corresponde a sumar pares ordenados; el término $a_{uv}D_{pq}$ no
cambia porque $D$ es simétrica.) El costo es $O(n)$ denso, pero
$O(\deg(u)+\deg(v))=O(k)$ con afinidad top-$k$: este es el argumento que habilita
la búsqueda local sobre decenas de miles de SKUs.

## 3. De los datos al modelo

### 3.1 Dataset

Dataset sintético de un depósito de zona única y 30 días de actividad
([data/raw/](data/raw/), esquema completo en [data/readme.txt](data/readme.txt)).
Unidades de distancia en pulgadas; conversión a metros sólo para reporte.

| Tabla | Contenido | Filas |
|---|---|---|
| `coordinates` | bays con pasillo, número, lado y coordenadas $(x,y)$ | 1.001 |
| `distances` | distancia camino-mínimo (Dijkstra) entre pares de bays | 500.500 |
| `initial_stock` | SKU y stock por ubicación (incluye vacías) | 30.000 |
| `picking_events` | una fila por línea de pick (batch, timestamp, ubicación, SKU) | 174.597 |
| `replenishment_events` | reposiciones, incluidas relocations de SKU | 14.647 |

Magnitudes: $\sim$2.000 batches ($\approx$87 líneas/batch), 10 merchants, 27.000
SKUs ubicados, 3.000 ubicaciones vacías, 1.000 bays + dock.

### 3.2 Construcción de los parámetros del modelo

| Parámetro | Fuente | Construcción |
|---|---|---|
| $f_i$ | `picking_events` (train) | conteo de líneas de pick por SKU ([demand/sku_demand.py](src/abs_affinity_based_slotting/demand/sku_demand.py)) |
| $c_\ell$ | `distances` | distancia bay($\ell$)→dock ([warehouse/costs.py](src/abs_affinity_based_slotting/warehouse/costs.py)) |
| $D_{\ell k}$ | `distances` | $D_{\ell k} = \text{dist}(\text{bay}(\ell),\text{bay}(k))$ ([warehouse/distances.py](src/abs_affinity_based_slotting/warehouse/distances.py)) |
| $a_{ij}$ | `picking_events` (train) | co-ocurrencia por batch → métrica de afinidad (sección 4) |

La aproximación a nivel bay refleja que el dato de distancia es bay-a-bay y que el
viaje intra-bay no está modelado; ítems en la misma bay quedan a distancia 0.

### 3.3 Protocolo de validación temporal

Para estimar desempeño **fuera de muestra** se particiona `picking_events` en train
(construcción de $f_i$ y $a_{ij}$) y test (evaluación). El corte es **temporal** y a
**granularidad de batch**: cada batch se asigna íntegramente a una partición según
el timestamp de su primer pick, y la fracción más reciente constituye el test
([data/split.py](src/abs_affinity_based_slotting/data/split.py)). Esto evita dos
fugas: (i) usar el futuro para construir features del pasado, y (ii) partir un
batch — la unidad de co-ocurrencia y de evaluación — entre particiones. Con
`test_size = 0.2`: 1.600 batches de train, 400 de test.

## 4. Métricas de afinidad

### 4.1 Espacio de métricas

Sea $N$ el número de batches de train, $s_i$ el **soporte** (batches que contienen a
$i$) y $n_{ij}$ la **co-ocurrencia** (batches con ambos). Todas derivan de
$(n_{ij}, s_i, N)$:

| Métrica | Definición | Interpretación |
|---|---|---|
| Co-ocurrencia | $a_{ij}=n_{ij}$ | conteo crudo; sesgado a SKUs frecuentes |
| Jaccard | $a_{ij}=\dfrac{n_{ij}}{s_i+s_j-n_{ij}}$ | solapamiento normalizado $\in[0,1]$ |
| Coseno | $a_{ij}=\dfrac{n_{ij}}{\sqrt{s_i s_j}}$ | similitud de vectores de incidencia |
| Lift | $a_{ij}=\dfrac{N\,n_{ij}}{s_i s_j}$ | co-ocurrencia vs independencia ($>1$: atracción) |
| Confianza | $a_{i\to j}=\dfrac{n_{ij}}{s_i}$ | dirigida; requiere simetrización |

La co-ocurrencia se obtiene de la matriz de incidencia batch×SKU $B$ (binaria):
$C = B^\top B$, con $C_{ij}=n_{ij}$ fuera de la diagonal y $C_{ii}=s_i$. La elección
de métrica es una **variable de diseño experimental**, no una constante del problema.

### 4.2 Dispersión top-$k$

Por cada SKU se conservan sólo sus $k$ vecinos de mayor afinidad, con umbral mínimo
de soporte $n_{ij}\ge\tau$ para descartar ruido. Reduce las aristas a $O(nk)$ y
descarta correlaciones débiles que aportan poco a la solución y mucho al costo (sección 2.5).

## 5. Metodología de evaluación

La evaluación vuelve comparables a las estrategias; su rigor condiciona todas las
conclusiones del trabajo.

### 5.1 Modelo de costo de ruta

Para un batch $B$ y una asignación $\pi$, sea $V(B)$ el conjunto de bays distintas
visitadas (mapeando cada SKU de $B$ a su ubicación y ésta a su bay). Las bays se
ordenan según una clave **snake** $\sigma$ (pasillo, luego número de bay), dando la
secuencia $b_1,\dots,b_T$. El costo de ruta es

$$
R(B;\pi)=D_0(\text{dock}, b_1)+\sum_{t=1}^{T-1} D(b_t,b_{t+1})+D_0(b_T,\text{dock}),
$$

con $D$ la distancia bay-a-bay y $D_0$ la distancia al dock. Picks en la misma bay
no agregan distancia (modelo bay-level). Decisiones del modelo:

- **Orden recalculado, no histórico.** El orden de visita se recomputa según las
  ubicaciones que propone $\pi$, no según el orden en que se pickeó realmente. Sin
  esto la comparación entre estrategias sería inconsistente.
- **Ruteo de orden fijo (snake), no TSP óptimo.** Aproximación deliberada: los
  depósitos reales usan políticas tipo S-shape, y resolver un TSP por batch
  confundiría la calidad del *ruteo* con la del *slotting*. El refinamiento a
  S-shape estricto (boustrophedon) queda como extensión.

### 5.2 Función objetivo (surrogate) vs evaluador (simulación)

| | Objetivo $C(\pi)$ | Evaluador $R$ |
|---|---|---|
| Rol | guía la búsqueda (qué optimizan las heurísticas) | KPI reportado |
| Datos | afinidad/demanda de **train** | batches de **test** |
| Forma | suma sobre pares (cuadrática, descomponible) | simulación discreta de recorridos |
| Propiedad | barata, con delta incremental | fiel al costo operativo |

El objetivo es un **surrogate** suave y eficiente; el evaluador es una **simulación**
sobre datos retenidos. Separarlos evita sobreajustar el surrogate y provee una
estimación honesta de generalización. Optimizar y evaluar con la misma función sería
hacerse trampa al solitario.

### 5.3 Invariante de cobertura

Toda asignación debe ubicar el **100%** de los SKUs que pueden aparecer en test.
Esto se garantiza por construcción tomando como universo **todos los SKUs ocupados
en `initial_stock`** (sección 12), dado que todo SKU pickeado pertenece al stock. La
cobertura no es una *política* del evaluador sino un **invariante**: un SKU de test
sin ubicar es un error y el evaluador lanza excepción en lugar de enmascararlo
([evaluation/evaluator.py](src/abs_affinity_based_slotting/evaluation/evaluator.py)).

### 5.4 Métricas reportadas

Sobre $\{R(B;\pi)\}_{B\in\text{test}}$ se reporta total, media, mediana y percentil
95 ([evaluation/metrics.py](src/abs_affinity_based_slotting/evaluation/metrics.py)).
Mediana y p95 caracterizan el caso típico y la cola (batches caros). La comparación
entre métodos se expresa como **mejora relativa** respecto del baseline `current`.
Complejidad: $O\!\left(\sum_B |B|\log|B|\right)$ por el ordenamiento; $\sim$0.16 s
para los 400 batches de test.

---

# Parte B — Arquitectura del sistema

## 6. Principios de diseño

1. **Generalidad sobre conveniencia.** Las piezas no fijan decisiones aún no
   tomadas (p. ej. el universo de SKUs es parámetro del builder, no hardcodeado).
2. **Un solo contrato por rol.** Todos los métodos comparten interfaz; todas las
   soluciones tienen la misma forma; un solo evaluador juzga a todos.
3. **`objective` ≠ `evaluator`** (sección 5.2): surrogate de train vs simulación de test.
4. **Inmutabilidad de los datos del problema.** La `SlottingInstance` es de solo
   lectura; los métodos producen `Assignment`, nunca mutan la instancia.
5. **Reproducibilidad.** Sin estado global oculto; rutas en `config.py`; artefactos
   derivados regenerables con un script.
6. **Simple antes que sofisticado.** NumPy/SciPy en el núcleo, pandas en el borde;
   abstraer sólo cuando hay más de un caso real que lo justifique.

## 7. Vista en capas y flujo

```
  raw data     data/raw/*.parquet  (inmutable)
     │         loaders + schemas
  features     demand/  warehouse/         f, a, c, D
     │         builders
  problema     slotting/   SlottingInstance · objective
     │
  métodos      methods/    SlottingMethod → Assignment
     │         Assignment
  juicio       evaluation/ Evaluator → Metrics  (sobre test)
     │
  experimentos scripts/ · notebooks/   comparación, tablas, figuras
```

Dependencias unidireccionales: cada capa sólo conoce a las de arriba. `methods/` no
sabe de `evaluation/`; `evaluation/` no sabe qué método produjo la asignación. El
flujo invariante de un experimento:

$$
\text{instancia} \xrightarrow{\;\text{método}.solve\;} \text{asignación}
\xrightarrow{\;\text{evaluador}.evaluate\;} \text{métricas}.
$$

## 8. Contratos core

### 8.1 `SlottingInstance` — datos del problema (inmutable, numérico)

Representación **numérica por posiciones**: ids externos como arrays, lógica interna
en índices enteros. Sin pandas adentro.
([slotting/instance.py](src/abs_affinity_based_slotting/slotting/instance.py))

```python
@dataclass(frozen=True, eq=False, repr=False)
class SlottingInstance:
    sku_ids: np.ndarray          # ids externos; posición i <-> índice interno i
    location_ids: np.ndarray
    bay_ids: np.ndarray
    demand: np.ndarray           # (n_skus,)        f_i
    location_cost: np.ndarray    # (n_locations,)   c_l (al dock)
    location_bay: np.ndarray     # (n_locations,)   índice de bay de cada location
    bay_distance: np.ndarray     # (n_bays, n_bays) D entre bays
    affinity: csr_matrix         # (n_skus, n_skus) a_ij dispersa
    merchant_ids: np.ndarray | None = None
```

Métodos y objetivo operan en índices (rápido); la traducción a ids ocurre en los
bordes vía `sku_index`/`location_index`/`bay_index` y sus inversos. Validación
exhaustiva en `__post_init__` (unicidad, shapes, NaN, no-negatividad, índices de bay
en rango, factibilidad $m\ge n$). El armado desde tablas pandas vive aparte
([slotting/build.py](src/abs_affinity_based_slotting/slotting/build.py),
`build_instance(...)`), con el universo de SKUs como parámetro.

### 8.2 `Assignment` — una solución (biyección parcial)

([slotting/assignment.py](src/abs_affinity_based_slotting/slotting/assignment.py))
Respaldada por dos diccionarios ($\text{sku}\!\to\!\text{loc}$, $\text{loc}\!\to\!\text{sku}$):

| Operación | Costo | Uso |
|---|---|---|
| `location_of`, `sku_at` | $O(1)$ | consultas |
| `swap` (in-place) | $O(1)$ | búsqueda local |
| `copy` | $O(n)$ | snapshot de la mejor solución |
| `to_frame` / `to_dict` | $O(n)$ | serialización / comparación |

**Mutable in-place** a propósito: la búsqueda local hace "intercambiar → medir delta
→ deshacer si no mejora", patrón que exige swaps $O(1)$.

### 8.3 `SlottingMethod` — estrategia (patrón Strategy)

([methods/base.py](src/abs_affinity_based_slotting/methods/base.py))

```python
class SlottingMethod(Protocol):
    name: str
    def solve(self, instance: SlottingInstance) -> Assignment: ...
```

Cada baseline/heurística implementa `solve`; el código de experimentos las trata de
forma uniforme.

### 8.4 `objective` — función de costo a optimizar (pendiente)

Implementa $C(\pi)$ de la sección 2.3 y el delta de la sección 2.5
(pendiente — vivirá en `heuristics/` dado que solo lo usan las heurísticas):

```python
def slotting_cost(assignment, instance, *, lam: float) -> float
def swap_delta(assignment, instance, sku_a, sku_b, *, lam: float) -> float
```

### 8.5 `Evaluator` y `Metrics` — el juez (sobre test)

([evaluation/](src/abs_affinity_based_slotting/evaluation/))

```python
@dataclass(frozen=True)
class Metrics:
    n_batches: int
    total_distance: float
    mean_batch_distance: float
    median_batch_distance: float
    p95_batch_distance: float
    runtime_seconds: float | None = None   # tiempo de solve, lo fija el caller

class Evaluator:
    def evaluate(self, assignment: Assignment, picking_test) -> Metrics: ...
```

Implementa la sección 5: re-ruteo snake por batch, costo de ruta, agregación, invariante de
cobertura. Independiente del método que generó la asignación.

## 9. Modularidad: contrato + registro

Las tres familias con múltiples variantes siguen el mismo patrón: un `Protocol` fija
el contrato y un `Registry` ([registry.py](src/abs_affinity_based_slotting/registry.py))
mapea `nombre → implementación`. Agregar una variante = una clase nueva +
registrarla; el resto del sistema no se modifica.

```python
@method_registry.register("abc")
class ABCFrequency:
    name = "abc"
    def solve(self, instance) -> Assignment: ...
```

| Familia | Contrato | Registro | Módulo |
|---|---|---|---|
| Métodos | `SlottingMethod.solve(instance) → Assignment` | `method_registry` | [methods/base.py](src/abs_affinity_based_slotting/methods/base.py) |
| Afinidad | `AffinityBuilder.build(cooccurrence, support, N) → csr` | `affinity_registry` | [demand/affinity.py](src/abs_affinity_based_slotting/demand/affinity.py) |
| Clustering | `ClusteringStrategy.cluster(instance) → labels` | `clustering_registry` | [clustering/base.py](src/abs_affinity_based_slotting/clustering/base.py) |

## 10. Convenciones

- **Granularidad espacial:** SKUs en `location`; costo y distancia a nivel `bay`.
- **Unidad de co-ocurrencia y evaluación:** `batch_id`; el split es a nivel batch.
- **Train vs test:** demanda y afinidad sólo con train; el evaluador sólo con test.
- **Datos:** parquet; `data/raw/` inmutable y versionado, `data/processed/` derivado
  y regenerable ([scripts/build_inputs.py](scripts/build_inputs.py)).
- **Rutas/constantes:** centralizadas en
  [config.py](src/abs_affinity_based_slotting/config.py). Distancias en pulgadas;
  metros sólo para reporte.
- **API pública:** cada subpaquete la expone en su `__init__.py`.
- **Notebooks:** sólo exploración y figuras; la lógica vive en `src/`.

## 11. Estructura del paquete (`src/`)

Todo el código vive en `src/abs_affinity_based_slotting/`. Cada subcarpeta es una
etapa del pipeline (numeradas 01-07 en orden de ejecucion) y su `__init__.py`
reune lo que el subpaquete expone. Estado `[hecho]` / `[pendiente]`:

```
src/abs_affinity_based_slotting/
├── __init__.py          raiz del paquete                              [hecho]
├── config.py            rutas, DOCK y conversion de unidades          [hecho]
├── registry.py          mapea nombre -> implementacion (modularidad)  [hecho]
│
├── 01 data/   ── objetivo: leer el historial crudo y separarlo en train/test
│   ├── __init__.py      interfaz del subpaquete                       [hecho]
│   ├── loaders.py       carga los 5 parquets crudos                   [hecho]
│   ├── schemas.py       valida las columnas de cada tabla             [hecho]
│   ├── io.py            lee/escribe artefactos derivados              [hecho]
│   └── split.py         corta train/test por batch (sin fuga)          [hecho]
│
├── 02 demand/   ── objetivo: derivar la demanda f y la afinidad a desde train
│   ├── __init__.py      interfaz del subpaquete                       [hecho]
│   ├── sku_demand.py    demanda f por SKU                             [hecho]
│   ├── cooccurrence.py  cuenta pares co-ocurrentes por batch          [hecho]
│   └── affinity.py      contrato + metricas cooccurrence y jaccard    [hecho]
│                        metricas cosine/lift                     [pendiente]
│
├── 03 warehouse/   ── objetivo: describir la geometria del deposito (c, D)
│   ├── __init__.py      interfaz del subpaquete                       [hecho]
│   ├── locations.py     ubicaciones desde el stock inicial            [hecho]
│   ├── distances.py     distancias entre bays y al dock               [hecho]
│   └── costs.py         costo de acceso c de cada ubicacion           [hecho]
│
├── 04 slotting/   ── objetivo: definir el problema y representar una solucion
│   ├── __init__.py      interfaz del subpaquete                       [hecho]
│   ├── instance.py      datos del problema (numerico, inmutable)      [hecho]
│   ├── build.py         arma la instancia desde las tablas            [hecho]
│   └── assignment.py    representa la solucion; swap en O(1)          [hecho]
│
├── 05 clustering/   ── objetivo: agrupar SKUs, una etiqueta entera por SKU
│   ├── __init__.py      interfaz del subpaquete                       [hecho]
│   ├── base.py          contrato ClusteringStrategy y registro        [hecho]
│   ├── abc.py           clases A/B/C por participacion de demanda      [hecho]
│   ├── merchant.py      una clase por vendor                          [hecho]
│   └── affinity.py      componentes conexas del grafo (top-k)         [hecho]
│
├── 06 methods/   ── objetivo: resolver el problema y producir un Assignment
│   ├── __init__.py      interfaz del subpaquete                       [hecho]
│   ├── base.py          contrato SlottingMethod y method_registry     [hecho]
│   └── current.py       baseline: slotting actual (snapshot)          [hecho]
│
└── 07 evaluation/   ── objetivo: medir una asignacion sobre test (el juez)
    ├── __init__.py      interfaz del subpaquete                       [hecho]
    ├── routes.py        costo de un recorrido (orden snake)           [hecho]
    ├── metrics.py       metricas agregadas (media, mediana, p95)      [hecho]
    └── evaluator.py     orquesta el calculo sobre test                [hecho]
```

## 12. Decisiones de diseño registradas

| Decisión | Elección | Motivo |
|---|---|---|
| Universo de SKUs | **Todos los ocupados** de `initial_stock` (~27.000) | Cobertura 100% en test; SKUs sin demanda en train entran con $f=0$. Builder igual lo deja configurable. |
| Dinámica de stock | **Estática** (snapshot) | Alcance clásico del SLAP; las 6.452 relocations se ignoran a propósito. |
| Granularidad de distancia | Nivel **bay** | Es como vienen los datos; viaje intra-bay no modelado. |
| Unidad del split | **batch** | Evita fuga; batch es unidad de co-ocurrencia y evaluación. |
| Demanda primaria | `pick_lines` | Cada línea es una acción operativa de picking. |
| Orden de recorrido | **Snake** a nivel bay (aisle, bay_number) | Recalculado según la asignación; intra-bay = 0. |
| SKU de test sin ubicar | **Error** | Con cobertura 100% es un bug; el evaluador lanza excepción. |
| Métrica de afinidad | A definir (Jaccard candidato) | Se comparan varias antes de fijar una. |

---

# Parte C — Estado y plan

## 13. Estado actual y resultado preliminar

**Implementado y verificado de punta a punta**: configuración, E/S y validación de
datos, split temporal, demanda por SKU, geometría y costos, `SlottingInstance` +
builder, `Assignment`, baseline `current`, evaluador completo, y los tres contratos
modulares con su registro. El pipeline corre y produce el primer benchmark.

**Benchmark — slotting actual sobre test** (400 batches):

| Métrica | pulgadas | metros |
|---|---|---|
| total | 20.959.192 | $\approx$532.363 |
| media / batch | 52.398 | $\approx$1.331 |
| mediana / batch | 52.540 | $\approx$1.335 |
| p95 / batch | 57.233 | $\approx$1.454 |

Este valor fija la línea base contra la cual se medirá toda estrategia posterior.

## 14. Hoja de ruta

**Orden de construcción** (lo hecho marcado ✓):

```
✓ EDA  →  ✓ inputs de optimización (demanda, costos, distancias, instancia)
       →  ✓ evaluación (rutas, métricas, evaluador)  →  ✓ baseline current
       →  contratos modulares ✓
       →  [PENDIENTE] afinidad  →  heurísticas  →  experimentos  →  escritura
```

**Soporte pendiente (no es optimización):**
[demand/cooccurrence.py](src/abs_affinity_based_slotting/demand/cooccurrence.py)
(insumo de afinidad, puro conteo), `merchants`, `plotting`, y un **harness de
experimentos** que recorra `method_registry`, evalúe y tabule resultados.

**Optimización pendiente (núcleo de la tesis):**

- *Afinidad:* co-ocurrencia y Jaccard hechos; pendiente coseno/lift y top-$k$.
- *Baselines:* `abc`, `merchant`, `affinity_greedy` (pendiente).
- *Objetivo:* $C(\pi)$ y delta de swap para las heurísticas (pendiente).
- *Heurísticas:* swaps, two-stage clustering, anchors (pendiente).
- *Heurísticas:* `swaps` (búsqueda local con delta incremental), `clustering` (dos
  etapas: agrupar afines → ubicar clusters en zonas → resolver dentro), `anchors`
  (ubicar SKUs de alta demanda/conectividad y rodearlos de sus vecinos afines).
- *Metaheurísticas* (extensión): tabu search, simulated annealing, GA si las
  heurísticas simples quedan en óptimos locales pobres.

Todo lo pendiente **enchufa** sobre los contratos existentes sin reescritura.

## 15. Preguntas abiertas, limitaciones y trabajo futuro

- **Locations vacías/sobrantes:** política de asignación de los huecos no usados
  ($m>n$).
- **Snake simple vs S-shape real** (boustrophedon): se arranca con el simple.
- **Calibración de $\lambda$** y de la métrica de afinidad: hiperparámetros a
  estudiar empíricamente (sensibilidad sobre test).
- **Definición de "zona"** para los métodos en dos etapas.
- **Slotting estático:** ignora relocations; modelar la dinámica es extensión.
- **Distancia a nivel bay:** no modela el viaje intra-bay.
- **Generalización temporal:** un único corte train/test; convendría validación con
  múltiples ventanas.

## 16. Cómo correrlo

Requisitos: Python ≥ 3.11. Entorno con [`uv`](https://github.com/astral-sh/uv).

```bash
uv venv && uv pip install -e .                 # entorno + paquete editable
.venv/bin/python scripts/build_inputs.py       # genera data/processed/*
# validación: abrir notebooks/test.ipynb con el kernel del .venv
```

Pipeline completo (obtener el benchmark actual):

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
    skus=data.initial_stock["sku"].dropna().to_numpy(),   # universo = todos los SKUs
)
method = method_registry.get("current")(data.initial_stock)
metrics = Evaluator.from_tables(
    data.coordinates, data.distances, data.initial_stock
).evaluate(method.solve(inst), read_parquet(PROCESSED_DIR / "picking_test.parquet"))
print(metrics)
```

## 17. Glosario y notación

- **SKU**: producto distinto. **Location**: hueco físico exacto. **Bay**: columna de
  estantería, unidad de distancia. **Dock**: estación de empaque, inicio/fin de ruta.
- **Batch**: lote de pedidos recolectado de una pasada; unidad de co-ocurrencia y
  evaluación. **Picking**: recuperar ítems para una orden. **Slotting**: asignar
  location a cada SKU.
- **Afinidad** $a_{ij}$: cuánto se piden juntos dos SKUs. **Demanda** $f_i$: cuánto
  se pide un SKU. **Costo de acceso** $c_\ell$: distancia al dock.
- **Baseline**: método de referencia simple. **Heurística**: método aproximado sin
  garantía de optimalidad. **Surrogate**: función de costo aproximada que guía la
  búsqueda.
- **Instancia** ($\pi$ sobre $I,L$): datos de un problema. **Asignación**: propuesta
  SKU→location. **QAP**: Quadratic Assignment Problem; NP-hard.

## 18. Referencias

- Koopmans, T. C., & Beckmann, M. (1957). *Assignment problems and the location of
  economic activities.* Econometrica.
- Bartholdi, J. J., & Hackman, S. T. (2014). *Warehouse & Distribution Science*
  (Rel. 0.96). Georgia Institute of Technology.
- Viveros, P., et al. (2021). *Slotting Optimization Model for a Warehouse with
  Divisible First-Level Accommodation Locations.* Applied Sciences, 11(3), 936.
