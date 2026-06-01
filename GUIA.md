# Affinity-Based Slotting — Documento técnico

Documento de referencia técnica del proyecto: formulación del problema, decisiones
de modelado, metodología de evaluación y arquitectura de la implementación. Asume
lector con base cuantitativa y de ingeniería de software; no asume familiaridad
previa con optimización combinatoria ni con el dominio logístico.

Documentos complementarios: [propuesta de tesis.md](propuesta%20de%20tesis.md)
(motivación y encuadre), [Resumen y punto de partida.md](Resumen%20y%20punto%20de%20partida.md)
(estado del arte), [ARCHITECTURE.md](ARCHITECTURE.md) (contratos de código en
detalle), [plan.md](plan.md) (hoja de ruta).

---

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

---

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
cada ubicación a lo sumo un SKU (la desigualdad admite ubicaciones vacías, ya que
$m>n$).

### 2.3 Vista como permutación y relación con el QAP

Cuando se restringe a las $n$ ubicaciones efectivamente usadas, una solución
factible es una **inyección** $\pi: I \to L$ (SKU $i$ → ubicación $\pi(i)$), y el
costo se reescribe como

$$
C(\pi)=\lambda\sum_{i} f_i\, c_{\pi(i)}
\;+\;(1-\lambda)\sum_{i}\sum_{j} a_{ij}\, D_{\pi(i)\pi(j)} .
$$

Esta es la forma de **Koopmans–Beckmann** del **Quadratic Assignment Problem
(QAP)** con término lineal. El QAP es **NP-hard** y notoriamente difícil incluso
para instancias moderadas; no admite resolución exacta a la escala de este
problema. De ahí la estrategia por baselines + heurísticas (sección 7).

### 2.4 Escala y consecuencias computacionales

Con $n\approx 27\,000$ y $m\approx 30\,000$:

- variables binarias $n\cdot m \approx 8.1\times 10^{8}$;
- la matriz de afinidad densa tendría $n^2 \approx 7.3\times 10^{8}$ entradas;
- una evaluación completa del término cuadrático es $O(n^2)$.

Dos consecuencias de diseño, ambas adoptadas:

1. **Afinidad dispersa.** $a_{ij}$ se almacena como matriz **CSR** y se restringe
   a los vínculos más fuertes (top-$k$ por SKU, sección 4.2), llevando los aristas
   de $O(n^2)$ a $O(nk)$.
2. **Evaluación incremental de movimientos.** Las heurísticas de búsqueda local no
   recomputan $C(\pi)$ sino su **delta** ante un intercambio (sección 2.5).

### 2.5 Delta de costo de un intercambio (swap)

Para búsqueda local interesa el costo de intercambiar las ubicaciones de dos SKUs
$u,v$ con $p=\pi(u)$, $q=\pi(v)$. El cambio de costo $\Delta = C(\pi')-C(\pi)$ se
calcula sin recomputar la suma global. Con $a$ y $D$ simétricas y diagonal nula:

$$
\Delta_{\text{lin}} = (f_u - f_v)\,(c_q - c_p),
$$

$$
\Delta_{\text{quad}} = 2\!\!\sum_{k\neq u,v}\!\! (a_{uk}-a_{vk})\,
\bigl(D_{q,\pi(k)}-D_{p,\pi(k)}\bigr),
$$

$$
\Delta = \lambda\,\Delta_{\text{lin}} + (1-\lambda)\,\Delta_{\text{quad}} .
$$

(El factor $2$ corresponde a sumar pares ordenados; el término $a_{uv}D_{pq}$ no
cambia porque $D$ es simétrica.) El costo de $\Delta_{\text{quad}}$ es $O(n)$
denso, pero $O(\deg(u)+\deg(v))=O(k)$ con afinidad top-$k$: este es el argumento
de escalabilidad que habilita la búsqueda local sobre decenas de miles de SKUs.

---

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

La aproximación a nivel bay ($D_{\ell k}$ depende sólo de las bays) refleja que el
dato de distancia es bay-a-bay y que el viaje intra-bay no está modelado; ítems en
la misma bay quedan a distancia 0.

### 3.3 Protocolo de validación temporal

Para estimar desempeño **fuera de muestra** se particiona `picking_events` en
train (construcción de $f_i$ y $a_{ij}$) y test (evaluación). El corte es
**temporal** y se realiza a **granularidad de batch**: cada batch se asigna
íntegramente a una partición según el timestamp de su primer pick, y la fracción
más reciente constituye el test ([data/split.py](src/abs_affinity_based_slotting/data/split.py)).
Esto evita dos fugas: (i) usar el futuro para construir features del pasado, y
(ii) partir un batch — la unidad de co-ocurrencia y de evaluación — entre ambas
particiones. Con `test_size = 0.2`: 1.600 batches de train, 400 de test.

---

## 4. Métricas de afinidad

### 4.1 Espacio de métricas

Sea $N$ el número de batches de train, $s_i$ el **soporte** (batches que contienen
a $i$) y $n_{ij}$ la **co-ocurrencia** (batches que contienen a $i$ y $j$). Todas
las métricas derivan de $(n_{ij}, s_i, N)$:

| Métrica | Definición | Interpretación |
|---|---|---|
| Co-ocurrencia | $a_{ij}=n_{ij}$ | conteo crudo; sesgado a SKUs frecuentes |
| Jaccard | $a_{ij}=\dfrac{n_{ij}}{s_i+s_j-n_{ij}}$ | solapamiento normalizado $\in[0,1]$ |
| Coseno | $a_{ij}=\dfrac{n_{ij}}{\sqrt{s_i s_j}}$ | similitud de vectores de incidencia |
| Lift | $a_{ij}=\dfrac{N\,n_{ij}}{s_i s_j}$ | co-ocurrencia vs independencia ($>1$: atracción) |
| Confianza | $a_{i\to j}=\dfrac{n_{ij}}{s_i}$ | dirigida; requiere simetrización |

La co-ocurrencia se obtiene de la matriz de incidencia batch×SKU $B$ (binaria):
$C = B^\top B$, con $C_{ij}=n_{ij}$ fuera de la diagonal y $C_{ii}=s_i$.

La elección de métrica es una **variable de diseño experimental**, no una
constante del problema; el sistema permite compararlas (sección 6.3).

### 4.2 Dispersión top-$k$

Para tratabilidad se conserva, por cada SKU, sólo sus $k$ vecinos de mayor
afinidad, con un umbral mínimo de soporte $n_{ij}\ge\tau$ para descartar ruido.
Esto reduce las aristas a $O(nk)$ y descarta correlaciones débiles que aportarían
poco a la solución y mucho al costo computacional (ver sección 2.5).

---

## 5. Metodología de evaluación

La evaluación es la pieza que vuelve comparables a las estrategias; su rigor
condiciona todas las conclusiones del trabajo.

### 5.1 Modelo de costo de ruta

Para un batch $B$ y una asignación $\pi$, sea $V(B)$ el conjunto de bays distintas
visitadas (mapeando cada SKU de $B$ a su ubicación y ésta a su bay). Las bays se
ordenan según una clave **snake** $\sigma$ (pasillo, luego número de bay),
obteniendo la secuencia $b_1,\dots,b_T$. El costo de ruta es

$$
R(B;\pi)=D_0(\text{dock}, b_1)+\sum_{t=1}^{T-1} D(b_t,b_{t+1})+D_0(b_T,\text{dock}),
$$

con $D$ la distancia bay-a-bay y $D_0$ la distancia al dock. Picks en la misma bay
no agregan distancia (modelo bay-level).

Decisiones del modelo de ruta:

- **Orden recalculado, no histórico.** El orden de visita se recomputa según las
  ubicaciones que propone $\pi$, no según el orden en que se pickeó realmente
  (que corresponde a las ubicaciones originales). Sin esto, la comparación entre
  estrategias sería inconsistente.
- **Ruteo de orden fijo (snake), no TSP óptimo.** Es una aproximación deliberada:
  los depósitos reales usan políticas de ruteo tipo S-shape, y resolver un TSP por
  batch confundiría la calidad del *ruteo* con la del *slotting*. El refinamiento
  a S-shape estricto (boustrophedon) queda como extensión.

### 5.2 Función objetivo (surrogate) vs evaluador (simulación)

Se distinguen dos funciones que es habitual (y erróneo) confundir:

| | Objetivo $C(\pi)$ | Evaluador $R$ |
|---|---|---|
| Rol | guía la búsqueda (qué optimizan las heurísticas) | KPI reportado |
| Datos | afinidad/demanda de **train** | batches de **test** |
| Forma | suma sobre pares (cuadrática, descomponible) | simulación discreta de recorridos |
| Propiedad | barata, con delta incremental | fiel al costo operativo |

El objetivo es un **surrogate** suave y eficiente; el evaluador es una
**simulación** sobre datos retenidos. Separarlos evita sobreajustar el surrogate y
provee una estimación honesta de generalización.

### 5.3 Invariante de cobertura

Toda asignación debe ubicar el **100%** de los SKUs que pueden aparecer en test.
Esto se garantiza por construcción tomando como universo de SKUs **todos los
ocupados en `initial_stock`** (sección 8), dado que todo SKU pickeado pertenece al
stock. En consecuencia la cobertura no es una *política* del evaluador sino un
**invariante**: un SKU de test sin ubicar es un error y el evaluador lanza
excepción en lugar de enmascararlo
([evaluation/evaluator.py](src/abs_affinity_based_slotting/evaluation/evaluator.py)).

### 5.4 Métricas reportadas

Sobre el conjunto de costos por batch $\{R(B;\pi)\}_{B\in\text{test}}$ se reporta
total, media, mediana y percentil 95
([evaluation/metrics.py](src/abs_affinity_based_slotting/evaluation/metrics.py)).
La mediana y el p95 caracterizan, respectivamente, el caso típico y la cola
(batches caros). La comparación entre métodos se expresa como **mejora relativa**
respecto del baseline `current`. Complejidad de la evaluación:
$O\!\left(\sum_B |B|\log|B|\right)$ por el ordenamiento; $\sim$0.16 s para los 400
batches de test.

---

## 6. Arquitectura de la implementación

### 6.1 Capas y dependencias

Paquete [src/abs_affinity_based_slotting/](src/abs_affinity_based_slotting/),
organizado en capas con dependencias unidireccionales (cada capa sólo usa las
superiores):

```
data/        lectura, validación y partición del historial
demand/, warehouse/   parámetros del modelo (f, a, c, D)
slotting/    SlottingInstance (problema), Assignment (solución), objective
methods/     estrategias .solve  →  Assignment
evaluation/  Evaluator  →  Metrics
scripts/, notebooks/   orquestación y experimentos
```

El flujo invariante de un experimento:

$$
\text{instancia} \xrightarrow{\;\text{método}.solve\;} \text{asignación}
\xrightarrow{\;\text{evaluador}.evaluate\;} \text{métricas}.
$$

### 6.2 Estructuras de datos núcleo

**`SlottingInstance`** ([slotting/instance.py](src/abs_affinity_based_slotting/slotting/instance.py))
— representación **numérica por posiciones** e **inmutable** del problema. Los
identificadores externos (`sku_ids`, `location_ids`, `bay_ids`) se guardan como
arrays; la lógica interna opera en **espacio de índices enteros** con mapas
$\text{id}\!\to\!\text{índice}$ y sus inversos. Datos numéricos en NumPy
($f$, $c$, `location_bay`, $D$ a nivel bay) y afinidad en **SciPy CSR**. Validación
exhaustiva en construcción (unicidad, shapes, no-negatividad, factibilidad
$m\ge n$). Esta representación mapea directamente al álgebra del QAP y evita pandas
en el cálculo. El ensamblado desde las tablas vive aparte
([slotting/build.py](src/abs_affinity_based_slotting/slotting/build.py)), de modo
que pandas queda confinado al borde de E/S.

**`Assignment`** ([slotting/assignment.py](src/abs_affinity_based_slotting/slotting/assignment.py))
— una solución, respaldada por dos diccionarios ($\text{sku}\!\to\!\text{loc}$ y
$\text{loc}\!\to\!\text{sku}$):

| Operación | Costo | Uso |
|---|---|---|
| `location_of`, `sku_at` | $O(1)$ | consultas |
| `swap` (in-place) | $O(1)$ | búsqueda local |
| `copy` | $O(n)$ | snapshot de la mejor solución |
| `to_frame` | $O(n)$ | serialización / comparación |

Es **mutable in-place** a propósito: el bucle de búsqueda local realiza
"intercambiar → medir delta → deshacer si no mejora", patrón que exige swaps
$O(1)$ sin reasignación de memoria.

### 6.3 Modularidad: contrato + registro

Las tres familias con múltiples variantes siguen el mismo patrón: un `Protocol`
fija el contrato y un `Registry` ([registry.py](src/abs_affinity_based_slotting/registry.py))
mapea `nombre → implementación`. Agregar una variante es definir una clase y
registrarla; el resto del sistema (evaluador, harness) no se modifica.

| Familia | Contrato | Registro | Módulo |
|---|---|---|---|
| Métodos | `SlottingMethod.solve(instance) → Assignment` | `method_registry` | [methods/base.py](src/abs_affinity_based_slotting/methods/base.py) |
| Afinidad | `AffinityBuilder.build(cooccurrence, support, N) → csr` | `affinity_registry` | [demand/affinity.py](src/abs_affinity_based_slotting/demand/affinity.py) |
| Clustering | `ClusteringStrategy.cluster(instance) → labels` | `clustering_registry` | [clustering.py](src/abs_affinity_based_slotting/clustering.py) |

### 6.4 Decisiones de implementación

- **NumPy/SciPy en el núcleo, pandas en el borde.** El cálculo opera sobre arrays
  e índices; pandas sólo en E/S y construcción.
- **Afinidad CSR dispersa.** Por escala (sección 2.4) y por el delta $O(k)$.
- **Inmutabilidad de la instancia / mutabilidad de la solución.** Separa lo dado
  de lo que se explora; previene efectos colaterales sobre el problema.
- **Entorno reproducible.** Rutas centralizadas en
  [config.py](src/abs_affinity_based_slotting/config.py); artefactos derivados
  regenerables vía [scripts/build_inputs.py](scripts/build_inputs.py).

---

## 7. Estrategias de resolución (roadmap algorítmico)

Esta es la parte de optimización, **aún no implementada** (los contratos sí
existen). Las variantes registradas se compararán con la misma metodología.

**Baselines.**
- *Current* (implementado): la asignación vigente leída de `initial_stock`;
  referencia principal.
- *ABC / frecuencia*: ordenar SKUs por $f_i$ desc. y ubicaciones por $c_\ell$ asc.,
  asignar en orden. Óptimo del **término lineal**; ignora afinidad. $O(n\log n)$.
- *Por merchant*: respetar la estructura por vendedor como restricción/agrupador.

**Heurísticas.**
- *Búsqueda local por swaps*: desde una solución inicial (ABC), intercambiar pares
  mientras $\Delta<0$ (sección 2.5); $\Delta$ en $O(k)$ con afinidad top-$k$.
- *Clustering en dos etapas*: agrupar SKUs afines, ubicar clusters en zonas
  cercanas, luego resolver dentro de cada cluster.
- *Productos ancla*: ubicar primero SKUs de alta demanda/conectividad y colocar a
  su alrededor los vecinos afines.

**Metaheurísticas** (extensión): tabu search, simulated annealing, algoritmos
genéticos, si las heurísticas simples quedan en óptimos locales pobres.

---

## 8. Estado actual y resultado preliminar

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

**Pendiente.** Soporte: `cooccurrence` (insumo de afinidad), `merchants`,
`plotting`, harness de experimentos. Optimización: implementaciones de
`AffinityBuilder`, `objective`, los `.solve` (`abc`, `merchant`, `swaps`,
`clustering`, `anchors`) y las `ClusteringStrategy`. Todo enchufa sobre los
contratos existentes sin reescritura.

---

## 9. Limitaciones y trabajo futuro

- **Slotting estático.** Se ignoran las relocations (6.452 en los datos); modelar
  la dinámica de stock es una extensión natural pero fuera del alcance actual.
- **Distancia a nivel bay.** No se modela el viaje intra-bay; razonable dado el
  dato, pero acota la fidelidad del costo.
- **Ruteo de orden fijo.** El costo de ruta usa snake, no el recorrido óptimo;
  separar ruteo de slotting es intencional pero conservador.
- **Calibración de $\lambda$ y de la métrica de afinidad.** Son hiperparámetros a
  estudiar empíricamente (sensibilidad sobre test).
- **Generalización temporal.** Un único corte train/test; convendría validación
  con múltiples cortes / ventanas móviles.

---

## 10. Referencias

- Koopmans, T. C., & Beckmann, M. (1957). *Assignment problems and the location of
  economic activities.* Econometrica.
- Bartholdi, J. J., & Hackman, S. T. (2014). *Warehouse & Distribution Science*
  (Rel. 0.96). Georgia Institute of Technology.
- Viveros, P., et al. (2021). *Slotting Optimization Model for a Warehouse with
  Divisible First-Level Accommodation Locations.* Applied Sciences, 11(3), 936.
```
