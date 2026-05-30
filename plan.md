
# Plan de acción de la tesis

## Punto de partida

Ya se cuenta con una primera etapa de comprensión de datos:

- carga de archivos,
- explicación de convenciones,
- EDA básico por archivo,
- comprensión de layout, stock, picking y replenishment.

A partir de ahora, el objetivo es transformar esos datos en una instancia útil para estudiar el problema de slotting.

La tesis apunta a modelar y optimizar la asignación de productos en un warehouse usando patrones históricos de demanda, distancias físicas y afinidad entre productos. El problema se relaciona con Storage Location Assignment Problem, en particular con affinity-based slotting o correlated storage assignment.

---

# Paso 1 — Definir el alcance computacional inicial

**Etiqueta:** `scope`, `methodology`, `decision`

## Objetivo

Definir qué versión del problema se va a atacar primero, para evitar empezar directamente con un modelo demasiado grande o intratable.

## Decisiones iniciales

- Trabajar inicialmente con SKUs, no con unidades individuales.
- Usar `batch_id` como unidad de coocurrencia.
- Usar `bay_id` como unidad principal de distancia física.
- Aproximar la distancia entre dos locations usando la distancia entre sus bays.
- Separar datos en train/test temporal.
- Empezar con baselines simples antes de heurísticas complejas.

## Salida esperada

Una celda o documento corto con decisiones metodológicas:

```text
- Unit of demand: SKU
- Unit of co-occurrence: batch_id
- Spatial unit: bay_id
- Evaluation: temporal test set
- Initial objective: reduce estimated picking distance
````

---

# Paso 2 — Crear split temporal train/test

**Etiqueta:** `data`, `evaluation`, `no-leakage`

## Objetivo

Separar los datos históricos en un período para construir demanda/afinidad y otro para evaluar soluciones.

## Tareas

* Ordenar `picking_events` por `timestamp`.
* Elegir una regla de corte temporal.
* Construir `picking_train`.
* Construir `picking_test`.
* Verificar cantidad de eventos, SKUs y batches en cada partición.



## Salida esperada

Archivos procesados:

```text
data/processed/picking_train.parquet
data/processed/picking_test.parquet
```

---

# Paso 3 — Construir demanda por SKU

**Etiqueta:** `demand`, `features`, `sku-level`

## Objetivo

Construir una tabla que mida la importancia operativa individual de cada SKU.

## Tareas

A partir de `picking_train`, calcular por SKU:

* cantidad de líneas de pick,
* unidades totales pickeadas,
* cantidad de batches donde aparece,
* merchant asociado,
* primera aparición,
* última aparición.

## Tabla esperada

```text
sku_demand
```

Columnas sugeridas:

```text
sku
merchant_account_id
pick_lines
total_units
unique_batches
first_pick_date
last_pick_date
```

## Decisión inicial

Usar `pick_lines` como métrica principal de demanda, porque cada línea representa una acción operativa de picking.

## Salida esperada

```text
data/processed/sku_demand.parquet
```

## Prioridad

Alta.

---

# Paso 4 — Construir costos de acceso por ubicación

**Etiqueta:** `layout`, `distances`, `location-cost`

## Objetivo

Asignar a cada ubicación física un costo de acceso desde el dock.

## Tareas

* Usar `initial_stock` para obtener locations y bays.
* Usar `distances` para obtener distancia de cada `bay_id` al `DOCK`.
* Construir una tabla a nivel location.
* Convertir pulgadas a metros para interpretación.

## Tabla esperada

```text
location_costs
```

Columnas sugeridas:

```text
location_id
location_name
bay_id
distance_to_dock_in
distance_to_dock_m
```

## Salida esperada

```text
data/processed/location_costs.parquet
```

## Prioridad

Alta.

---

# Paso 5 — Reconstruir el slotting actual

**Etiqueta:** `baseline`, `current-state`, `slotting`

## Objetivo

Construir la asignación actual SKU → ubicación, que funcionará como baseline real del dataset.

## Tareas

* Tomar SKUs no nulos desde `initial_stock`.
* Asociar cada SKU con su `location_id`, `location_name` y `bay_id`.
* Agregar demanda desde `sku_demand`.
* Agregar distancia al dock desde `location_costs`.

## Tabla esperada

```text
current_slotting
```

Columnas sugeridas:

```text
sku
merchant_account_id
location_id
location_name
bay_id
pick_lines
total_units
distance_to_dock_m
```

## Salida esperada

```text
data/processed/current_slotting.parquet
```

## Prioridad

Alta.

---

# Paso 6 — Construir coocurrencia entre SKUs

**Etiqueta:** `affinity`, `cooccurrence`, `batch-level`

## Objetivo

Medir qué productos aparecen juntos en los mismos batches.

## Tareas

* Agrupar `picking_train` por `batch_id`.
* Obtener conjunto de SKUs por batch.
* Construir pares de SKUs dentro de cada batch.
* Contar cuántas veces aparece cada par.

## Tabla esperada

```text
sku_pair_cooccurrence
```

Columnas sugeridas:

```text
sku_i
sku_j
cooccurrence_count
```

## Salida esperada

```text
data/processed/sku_pair_cooccurrence.parquet
```

## Prioridad

Alta.

---

# Paso 7 — Construir métricas de afinidad

**Etiqueta:** `affinity`, `metrics`, `graph`

## Objetivo

Transformar la coocurrencia bruta en medidas de afinidad más informativas.

## Métricas candidatas

* coocurrencia bruta,
* Jaccard,
* cosine similarity,
* lift,
* confidence.

## Tareas

* Calcular demanda o presencia por SKU en batches.
* Calcular una o más métricas de afinidad.
* Comparar distribuciones de scores.
* Revisar top pares por cada métrica.
* Decidir una métrica inicial para los primeros experimentos.

## Tabla esperada

```text
sku_affinity
```

Columnas sugeridas:

```text
sku_i
sku_j
cooccurrence_count
affinity_score
affinity_metric
```

## Salida esperada

```text
data/processed/sku_affinity.parquet
```

## Prioridad

Alta.

---

# Paso 8 — Construir afinidad dispersa top-k

**Etiqueta:** `affinity`, `sparsity`, `scalability`

## Objetivo

Reducir la cantidad de relaciones SKU-SKU para que el problema sea tratable.

## Tareas

* Para cada SKU, conservar solo sus `k` vecinos más afines.
* Probar valores como `k = 5`, `10`, `20`.
* Filtrar pares con soporte demasiado bajo.
* Medir cuántos edges quedan.
* Medir cuántos SKUs quedan conectados.

## Tabla esperada

```text
sku_affinity_topk
```

Columnas sugeridas:

```text
sku_i
sku_j
affinity_score
cooccurrence_count
rank_i
```

## Salida esperada

```text
data/processed/sku_affinity_topk.parquet
```

## Prioridad

Alta.

---

# Paso 9 — Analizar estructura por merchant

**Etiqueta:** `merchant`, `dimension-reduction`, `business-structure`

## Objetivo

Evaluar si el merchant/vendor sirve como estructura natural para reducir el problema.

## Tareas

* Calcular demanda total por merchant.
* Calcular cantidad de SKUs por merchant.
* Calcular coocurrencias intra-merchant.
* Calcular coocurrencias inter-merchant.
* Medir qué proporción de la afinidad ocurre dentro del mismo merchant.

## Preguntas a responder

```text
¿Los productos de un mismo merchant aparecen juntos con frecuencia?
¿Tiene sentido resolver primero por merchant?
¿El merchant debería ser una restricción, un agrupador o solo un baseline?
```

## Salida esperada

Tablas y gráficos simples:

```text
merchant_demand
merchant_affinity_summary
```

## Prioridad

Media-alta.

---

# Paso 10 — Definir métrica de evaluación

**Etiqueta:** `evaluation`, `objective`, `simulation`

## Objetivo

Definir cómo se va a medir si una asignación de productos es mejor que otra.

## Métricas posibles

De menor a mayor fidelidad:

```text
1. distancia al dock ponderada por demanda
2. distancia promedio entre SKUs del mismo batch
3. distancia estimada por batch usando orden de picking
4. recorrido completo dock → picks → dock
```

## Recomendación

Implementar primero una métrica simple para avanzar rápido:

```text
weighted_access_cost = demanda_sku × distancia_al_dock
```

Pero la evaluación importante debería acercarse a batches reales:

```text
costo de pickear los batches de test bajo una asignación dada
```

## Salida esperada

Función:

```python
evaluate_solution(solution, picking_test)
```

Con salida:

```text
total_distance
mean_batch_distance
median_batch_distance
p95_batch_distance
```

## Prioridad

Alta.

---

# Paso 11 — Evaluar slotting actual

**Etiqueta:** `baseline`, `current-slotting`, `evaluation`

## Objetivo

Medir el costo de la configuración actual del warehouse.

## Tareas

* Usar `current_slotting`.
* Evaluar sobre `picking_test`.
* Guardar métricas.
* Usar este resultado como benchmark principal.

## Salida esperada

Resultado tipo:

```text
strategy = current_slotting
total_distance = ...
mean_batch_distance = ...
p95_batch_distance = ...
```

## Prioridad

Alta.

---

# Paso 12 — Implementar baseline ABC/frecuencia

**Etiqueta:** `baseline`, `abc`, `frequency`

## Objetivo

Construir un baseline simple e interpretable: productos más demandados en ubicaciones más baratas.

## Tareas

* Ordenar SKUs por demanda descendente.
* Ordenar ubicaciones por distancia al dock ascendente.
* Asignar en ese orden.
* Evaluar sobre test.
* Comparar contra slotting actual.

## Salida esperada

Tabla de comparación:

```text
current_slotting
ABC_frequency
```

## Prioridad

Alta.

---

# Paso 13 — Implementar baseline por merchant

**Etiqueta:** `baseline`, `merchant`, `abc`

## Objetivo

Evaluar si respetar estructura por merchant mejora la asignación.

## Tareas

* Ordenar merchants por demanda total.
* Asignar merchants a zonas o ubicaciones cercanas.
* Dentro de cada merchant, ordenar SKUs por demanda.
* Evaluar sobre test.

## Salida esperada

Comparación:

```text
current_slotting
ABC_frequency
merchant_ABC
```

## Prioridad

Media.

---

# Paso 14 — Formular el problema completo

**Etiqueta:** `optimization`, `formulation`, `qap`

## Objetivo

Escribir la formulación matemática conceptual del problema.

## Componentes

Conjuntos:

```text
I = SKUs
L = ubicaciones
```

Parámetros:

```text
d_i   = demanda del SKU i
c_l   = costo de acceso de ubicación l
a_ij  = afinidad entre SKU i y SKU j
D_lm  = distancia entre ubicaciones l y m
```

Variables:

```text
x_il = 1 si SKU i se asigna a ubicación l
```

Objetivo conceptual:

```text
minimizar costo lineal de acceso
+
minimizar costo cuadrático de afinidad/distancia
```

## Tareas

* Escribir formulación en LaTeX.
* Explicar restricciones de asignación.
* Explicar por qué aparece una estructura tipo QAP.
* Explicar por qué no se resuelve de forma exacta a gran escala.

## Prioridad

Media-alta.

---

# Paso 15 — Implementar heurística por swaps

**Etiqueta:** `heuristic`, `local-search`, `affinity`

## Objetivo

Mejorar una solución inicial intercambiando ubicaciones de SKUs.

## Punto de partida

Usar como solución inicial:

```text
ABC_frequency
```

o:

```text
merchant_ABC
```

## Tareas

* Definir función objetivo con demanda y afinidad.
* Elegir pares candidatos a swap.
* Calcular delta de costo.
* Aceptar swaps que mejoran.
* Iterar hasta límite de tiempo o convergencia.
* Evaluar sobre test.

## Salida esperada

Estrategia:

```text
affinity_swap_local_search
```

Comparada contra:

```text
current_slotting
ABC_frequency
merchant_ABC
```

## Prioridad

Media-alta.

---

# Paso 16 — Probar clustering por afinidad

**Etiqueta:** `heuristic`, `clustering`, `affinity`

## Objetivo

Agrupar productos afines y ubicar grupos en zonas cercanas.

## Tareas

* Construir grafo SKU-SKU con afinidad top-k.
* Obtener clusters.
* Calcular demanda total por cluster.
* Asignar clusters a zonas o regiones del warehouse.
* Asignar SKUs dentro de cada cluster.
* Evaluar sobre test.

## Salida esperada

Estrategia:

```text
cluster_two_stage
```

## Prioridad

Media.

---

# Paso 17 — Probar productos ancla

**Etiqueta:** `heuristic`, `anchors`, `affinity`

## Objetivo

Ubicar primero productos importantes y luego ubicar cerca sus productos relacionados.

## Tareas

* Definir `anchor_score`.
* Seleccionar productos ancla.
* Asignarlos a ubicaciones convenientes.
* Asignar vecinos afines alrededor.
* Resolver conflictos de asignación.
* Evaluar sobre test.

## Score posible

```text
anchor_score = alpha * demand_score + beta * affinity_degree_score
```

## Salida esperada

Estrategia:

```text
anchor_based_slotting
```

## Prioridad

Media-baja.

---

# Paso 18 — Diseñar experimentos

**Etiqueta:** `experiments`, `comparison`, `results`

## Objetivo

Comparar estrategias de forma ordenada y reproducible.

## Experimentos mínimos

```text
1. current_slotting vs ABC_frequency
2. ABC_frequency vs merchant_ABC
3. ABC_frequency vs affinity_swap_local_search
4. sensibilidad al valor de k en afinidad top-k
5. comparación de métricas de afinidad
6. clustering vs local search
```

## Métricas

```text
total_distance
relative_improvement
mean_batch_distance
median_batch_distance
p95_batch_distance
runtime_seconds
```

## Salida esperada

```text
reports/tables/experiment_results.csv
reports/figures/
```

## Prioridad

Media-alta.

---

# Paso 19 — Ordenar escritura de resultados

**Etiqueta:** `writing`, `thesis`, `reporting`

## Objetivo

Conectar resultados computacionales con capítulos de tesis.

## Capítulos esperados

```text
1. Introducción y problema
2. Datos y contexto operativo
3. Construcción de demanda y afinidad
4. Formulación del problema
5. Baselines y heurísticas
6. Evaluación experimental
7. Conclusiones
```

## Tareas

* Guardar tablas finales.
* Guardar figuras finales.
* Documentar decisiones metodológicas.
* Escribir limitaciones.
* Escribir trabajo futuro.

## Prioridad

Media.

---

# Orden inmediato recomendado

Como el EDA ya está hecho, el orden práctico desde ahora sería:

```text
1. Crear split temporal train/test
2. Construir sku_demand
3. Construir location_costs
4. Reconstruir current_slotting
5. Construir coocurrencia SKU-SKU
6. Calcular métricas de afinidad
7. Construir afinidad top-k
8. Definir métrica de evaluación
9. Evaluar slotting actual
10. Implementar ABC_frequency
11. Comparar current vs ABC
12. Analizar merchant como agrupador
13. Implementar merchant_ABC
14. Formular problema completo
15. Implementar local search por swaps
```

# Idea guía

El proyecto debería avanzar así:

```text
EDA
→ inputs de optimización
→ baselines
→ afinidad
→ evaluación
→ heurísticas
→ experimentos
→ escritura
```

La prioridad ahora no es probar muchas heurísticas, sino construir correctamente:

```text
demanda
afinidad
distancias
evaluación
baselines
```

Sin esos componentes, cualquier método más sofisticado queda sin una base clara de comparación.

```

Esto ya está más cerca de un **plan de acción operativo** que de una lista formal de épicas.
```
