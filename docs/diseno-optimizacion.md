# Alternativas de diseño del método de optimización

El QAP global es intratable a escala real (ver [formulacion.md](formulacion.md)).
La estrategia es resolver un **problema similar y tratable** mediante descomposición
y truncado. Este documento enumera las alternativas en cada punto de decisión, sus
ventajas y desventajas, y marca la opción elegida o recomendada. Sirve tanto para
guiar la implementación como para justificar las decisiones en la tesis.

Estado de cada decisión: **[elegido]**, **[recomendado]** (a confirmar) o
**[abierto]** (variable experimental a barrer).

---

## 1. Cómo achicar el problema

Cómo construir el "problema similar" que sí se puede optimizar.

| Alternativa | Idea | Ventaja | Desventaja | Estado |
|---|---|---|---|---|
| **Descomposición bi-nivel** | agrupar productos y partir en ubicar-zonas + ubicar-dentro | subproblemas chicos, paralelizables, optimizables exacto | la calidad depende del clustering; ignora parte de la estructura global | **[elegido]** |
| **Truncado (top-k)** | conservar solo los vínculos de afinidad fuertes | reduce el término cuadrático; se combina con lo anterior | descarta afinidad débil (suele ser ruido) | **[elegido]** (complementa) |
| Relajación del QAP global | resolver una relajación (LP, etc.) del QAP completo | una sola formulación | sigue siendo enorme; la relajación puede ser floja | descartada |

La combinación elegida: **bi-nivel + truncado top-k**.

---

## 2. Problema 1 — repartir ubicaciones entre clusters

Asignar a cada cluster un conjunto de `size[c]` ubicaciones. Tres formas de
modelarlo:

| Alternativa | Modelo | Ventaja | Desventaja | Estado |
|---|---|---|---|---|
| **A. Transporte lineal** | `min Σ demanda[c]·costo[ℓ]·y[ℓ,c]` con `Σ_ℓ y[ℓ,c]=size[c]`, `Σ_c y[ℓ,c]≤1` | **lineal y exacto** (totalmente unimodular); contigüidad por costo sale sola | usa demanda agregada como proxy; no mira afinidad inter-cluster | **[recomendado]** |
| B. Regiones fijas con capacidad | particionar el depósito en Z regiones; asignar clusters con `Σ size·x ≤ cap` | permite meter afinidad inter-región (QAP con capacidad) | hay que definir las regiones (Z, límites); más pesado | alternativa |
| C. Secuenciar clusters | decidir el orden de los clusters sobre la línea ordenada por costo | fiel a "zona contigua dimensionada al cluster" | **no es QAP de coeficientes fijos** (el costo de cada bloque depende del orden acumulado); modelo exacto incómodo | descartada |

**Por qué A.** Es el modelo más limpio: un problema de transporte que se resuelve
exacto y barato, cuyo óptimo da las ubicaciones más baratas al cluster de mayor
demanda. La afinidad no entra acá (se trata en el Problema 2). El precio es que la
afinidad inter-cluster no se optimiza (ver §5).

---

## 3. Cómo resolver el Problema 1 (lineal)

| Alternativa | Cómo | Ventaja | Desventaja | Estado |
|---|---|---|---|---|
| **Solver de transporte** | armar el problema lineal y resolverlo con el solver | inequívoco; coherente con "todo con solver"; **generaliza** si se agrega afinidad inter-cluster (pasa a QAP) | invocar un solver para algo con forma cerrada es overkill | **[elegido]** |
| Forma cerrada (orden por demanda) | asignar bloques por demanda descendente sobre costos ascendentes | instantáneo; es el óptimo del LP, no un sort heurístico | no generaliza si el modelo se complica | descartada |

Se eligió plantearlo como optimización aunque hoy su óptimo coincida con la forma
cerrada (validado: ambos dan el mismo costo). El motivo es la extensibilidad: sobre
ese mismo modelo se puede agregar la afinidad inter-cluster (§5), que lo convierte
en un QAP a nivel cluster.

---

## 4. Problema 2 — QAP por cluster (en paralelo)

Para cada cluster, sobre sus ubicaciones, resolver el QAP completo
(demanda×costo + afinidad×distancia). Los clusters son independientes entre sí.

| Alternativa | Cuándo | Ventaja | Desventaja | Estado |
|---|---|---|---|---|
| **Gurobi exacto** (`qap_gurobi`) | clusters chicos | óptimo probado; valida y fija la vara de calidad | no escala (un cluster merchant ~2.700 productos no entra) | **[elegido]** (chicos) |
| **Búsqueda por swaps** | clusters grandes | escala; la única heurística permitida | sin garantía de optimalidad | **[elegido]** (grandes) |
| scipy `quadratic_assignment` (FAQ) | — | sin licencia | otra heurística no sancionada; no es la búsqueda por swaps | descartada |

Regla: **por cluster, exacto si entra, swaps si no.** El umbral de tamaño es un
parámetro a calibrar.

---

## 5. Afinidad inter-cluster: descartarla o modelarla

| Alternativa | Idea | Ventaja | Desventaja | Estado |
|---|---|---|---|---|
| **Descartarla** | la afinidad solo cuenta dentro de cada cluster (Problema 2) | decomposición limpia; Problemas 1 y 2 simples | pierde el copicking entre clusters | **[elegido]** |
| Modelarla | QAP a nivel cluster en el Problema 1 (afinidad inter-cluster × distancia inter-zona) | captura copicking entre grupos | el Problema 1 deja de ser lineal; más complejo | alternativa |

Con afinidad inter-cluster descartada, **la responsabilidad de agrupar lo afín
recae en el clustering** (§6): si dos productos muy co-pedidos quedan en clusters
distintos, su proximidad no se optimiza.

---

## 6. Qué clustering define las zonas

El clustering determina qué productos comparten zona. El plan es agrupar por
**vendor** (`merchant`): es el criterio operativo del problema. `demand_class`
(tiers de rotación A/B/C) queda como alternativa.

| Clustering | Agrupa por | Nota |
|---|---|---|
| `merchant` | vendor | ~10 grupos balanceados; el agrupamiento dado |
| `demand_class` | tier de demanda (A/B/C) | 3 grupos; zonificación clásica de rotación |

La afinidad **no se explota eligiendo el clustering**, sino **dentro de cada zona**
de vendor (el QAP del Problema 2). Se evaluó un clustering por componentes conexas
de la afinidad, pero resultó degenerado (un componente gigante de ~15.500 + miles
de singletons), y la detección de comunidades quedó descartada: el agrupamiento es
por vendor, y la afinidad se resuelve en el nivel inferior.

---

## 7. Configuración elegida (resumen)

```
Achicar:     bi-nivel + truncado top-k
Problema 1:  transporte lineal -> exacto
               costo = posicion en recorrido (snake) -> zonas compactas
Problema 2:  QAP por cluster, en paralelo
               cluster chico  -> exacto (Gurobi)
               cluster grande -> busqueda por swaps
Afinidad inter-cluster: descartada (solo intra, via Problema 2)
Clustering:  vendor (merchant); demand_class como alternativa
```

Decisiones pendientes: el umbral chico/grande del Problema 2 (§4), y validar si la
afinidad intra-vendor (Problema 2 con búsqueda por swaps) mejora las rutas frente a
la colocación por demanda.
