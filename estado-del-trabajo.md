# Estado del trabajo — panorama completo

Documento de situacion para la reunion de direccion. Cubre: que se hizo, por que se
hizo, que hipotesis se siguieron, que dijeron los experimentos, que se descarto y que
queda por hacer.

Documentos relacionados: [propuesta de tesis.md](propuesta%20de%20tesis.md) (propuesta
formal), [Resumen y punto de partida.md](Resumen%20y%20punto%20de%20partida.md) (estado
del arte), [docs/](docs/README.md) (documentacion tecnica: formulacion, pipeline,
bloques, decisiones de diseno).

---

## 1. Resumen ejecutivo

El trabajo modela el slotting (asignacion producto -> ubicacion) de un deposito como un
**QAP de Koopmans-Beckmann** con un termino lineal (demanda x distancia al dock) y uno
cuadratico (afinidad x distancia entre productos), ponderados por un parametro lambda.
Se construyo un pipeline completo y modular, con separacion estricta train/test, y se
implementaron y compararon seis estrategias de resolucion.

**El resultado principal es un resultado negativo, y es solido:**

1. Concentrar por demanda cerca del dock reduce la distancia por batch un **50,2%**
   frente al slotting vigente (52.398 -> 26.079 pulgadas por batch). Esto lo logra el
   baseline mas simple, `demand_greedy`, en 0,02 segundos.
2. **Ninguna estrategia que use afinidad supera a ese baseline.** La busqueda local con
   afinidad empeora (26.964). El metodo bi-nivel por vendor empeora un 10% (28.6k-29k).
   La mejor variante bi-nivel (agrupando por clase de demanda) empata (26.010, -0,3%
   respecto del baseline, dentro del ruido).
3. La hipotesis mas probable para explicar esto: **la senal de afinidad de este dataset
   es practicamente ruido**, por dos razones estructurales del dato (seccion 6.4). No es
   una falla del metodo ni de la implementacion.

Esto no invalida el trabajo, pero cambia lo que la tesis puede afirmar. La seccion 9
propone como reencauzarlo.

---

## 2. El problema y como se modelo

### 2.1 Por que

En un centro de distribucion el costo dominante del armado de pedidos es el
desplazamiento del operario. El slotting determina esos recorridos. La practica habitual
asigna ubicaciones por hueco libre o por rotacion individual, ignorando que los productos
no se piden aislados: hay pares que aparecen juntos de forma recurrente y, si quedan
lejos, generan recorridos redundantes.

### 2.2 El modelo

Con `f_i` = demanda del producto i, `c_l` = costo de acceso de la ubicacion l (distancia
al dock), `a_ij` = afinidad entre productos, `d_lk` = distancia entre ubicaciones, y
`x_il` = 1 si el producto i va a la ubicacion l:

```
min  lambda * SUM_i SUM_l  f_i * c_l * x_il
   + (1-lambda) * SUM_i SUM_j SUM_l SUM_k  a_ij * d_lk * x_il * x_jk

s.a. cada producto en exactamente una ubicacion
     cada ubicacion con a lo sumo un producto
```

Es la forma de Koopmans-Beckmann del QAP, NP-hard. A esta escala (27.000 productos,
30.000 ubicaciones) tendria 8,1e8 variables binarias y la afinidad densa 7,3e8 entradas:
no se resuelve exacto.

### 2.3 Las decisiones de modelado que lo hacen tratable

- **Afinidad dispersa**: se guarda en CSR y se trunca a los k vinculos mas fuertes por
  producto (top-k). Pasa de O(n^2) a O(nk) entradas.
- **Evaluacion incremental**: la busqueda local no recomputa el costo total ante un
  intercambio, solo su variacion. Con afinidad top-k el delta es O(k) en vez de O(n).
  Este es el argumento que vuelve viable la busqueda local sobre decenas de miles de
  productos.
- **Descomposicion bi-nivel**: en vez de un QAP de 27.000 productos, agrupar productos y
  partir en (1) repartir ubicaciones entre grupos y (2) ubicar productos dentro de cada
  zona.

Las tres estan implementadas y documentadas en [docs/formulacion.md](docs/formulacion.md)
y [docs/diseno-optimizacion.md](docs/diseno-optimizacion.md).

---

## 3. Los datos

Dataset **sintetico** de un deposito de zona unica, 30 dias de actividad (enero 2025),
cinco tablas parquet.

| Concepto | Valor |
|---|---|
| Lineas de picking | 174.597 |
| Batches (viajes de picking) | 2.000 (~87 lineas, ~76 SKUs distintos cada uno) |
| Ubicaciones exactas | 30.000 (1.000 bays x 5 estantes x 6 bins) |
| Productos ubicados (SKUs) | 27.000 (10% de huecos vacios) |
| Bays | 1.000 (25 pasillos x 40 bays) + dock |
| Merchants (vendors) | 10, balanceados (~2.700 SKUs cada uno) |
| Reposiciones | 14.647 (56% in situ, 44% reubicacion) |
| Pickers | 20, carga uniforme |

Distancias: camino minimo (Dijkstra) sobre el grafo de pasillos, en pulgadas.

Del EDA (notebook `00_EDA`): la ocupacion es uniforme por pasillo, bay, estante y vendor;
la actividad de picking es uniforme por pasillo y por numero de bay; los pickers y los
merchants estan balanceados. **El dataset no tiene estructura espacial ni de demanda
preexistente que sesgue el analisis** — lo cual es bueno para la limpieza del
experimento, pero tambien significa que hay poco que explotar mas alla de la distancia al
dock.

### Split train/test

Corte **temporal y a nivel de batch**: cada batch entero va a una particion segun su
timestamp, y el 20% mas reciente es test. Resultado: 1.600 batches de train (139.632
lineas, 15.554 SKUs vistos) y 400 de test (34.965 lineas). El corte a nivel de batch
evita fuga: el batch es a la vez la unidad de co-ocurrencia y la unidad de evaluacion.

Consecuencia: de los 27.000 productos del universo, **11.446 nunca se piden en train** y
entran con demanda 0.

---

## 4. Metodologia de evaluacion

Es la parte metodologicamente mas cuidada del trabajo y conviene defenderla explicitamente.

**Se distinguen dos medidas distintas, deliberadamente:**

| | Objetivo (`slotting_cost`) | Evaluador (`RouteMetrics`) |
|---|---|---|
| Proposito | guiar la busqueda de los metodos | reportar el resultado |
| Datos | demanda y afinidad de **train** | recorridos simulados sobre **test** |
| Naturaleza | funcion analitica eficiente | simulacion de los recorridos |

Los metodos **optimizan el objetivo**; el desempeno **se mide con el evaluador**.
Optimizar y medir con la misma funcion daria una estimacion sesgada. Que una baja del
objetivo no se traduzca en una baja de la distancia real es esperable, y esa brecha es
justamente uno de los objetos de estudio (y, como se vera, el fenomeno central que
aparecio).

**Como mide el evaluador**: para cada batch de test toma los SKUs pedidos, mira donde los
ubica la asignacion propuesta, ordena las bays en orden serpenteante (pasillo, numero de
bay) y suma dock -> bays -> dock. El orden de visita se **recalcula** segun la asignacion,
no se usa el orden historico. Picks en la misma bay no suman distancia. Antes de medir
verifica un invariante de cobertura: todo SKU de test debe estar ubicado, si falta alguno
lanza error en vez de saltearlo.

El evaluador es **independiente del metodo** que produjo la asignacion.

**Benchmark de referencia**: el slotting vigente (`current`, leido del stock inicial)
sobre los 400 batches de test recorre **52.398 pulgadas por batch** en promedio
(aprox. 1.331 m), mediana 52.540, p95 57.233. Total 20,96 millones de pulgadas.

---

## 5. Que se construyo

Paquete `src/abs_affinity_based_slotting/`, ~2.900 lineas, organizado en capas con
dependencias unidireccionales. Cada familia de componentes se resuelve por nombre desde
un *registry*, de modo que cambiar de estrategia es cambiar un string.

```
data/        lectura de los 5 parquets, validacion de esquemas, split temporal por batch
demand/      demanda f; co-ocurrencia n_ij y soporte s_i; builders de afinidad; filtros
warehouse/   universo de productos, distancias entre bays, costo de acceso c
slotting/    SlottingInstance (inmutable, validada), Assignment (swap O(1)), objetivo
clustering/  agrupamiento de productos (merchant, demand_class)
methods/     los resolvedores
evaluation/  costo de ruta, metricas agregadas, evaluador sobre test
```

**Componentes intercambiables ya implementados:**

- Afinidad: `cooccurrence` (n_ij crudo), `jaccard` (n_ij / union), `cosine`
  (n_ij / sqrt(s_i s_j)). Lift, confianza dirigida y PMI quedaron documentados como
  candidatos con sus advertencias, sin implementar.
- Filtros: `top_k` (union), `mutual_top_k` (interseccion, mas estricto), `threshold`.
  Todos devuelven matriz simetrica, condicion que la instancia valida al construirse
  porque el delta incremental depende de ella.
- Clustering: `merchant` (10 grupos), `demand_class` (A/B/C por demanda acumulada).
- Metodos: `current` (baseline), `demand_greedy`, `linear_assignment` (hungaro, exacto
  para lambda=1), `swap_search` (busqueda local), `bilevel` (dos etapas), `exact_qap`
  (solver exacto sobre el QAP completo).

**Diseno del metodo bi-nivel** (el aporte central pretendido):

- *Problema 1* — repartir ubicaciones entre grupos. Se modela como problema de
  transporte lineal: `min SUM demanda[c] * costo[l] * y[l,c]`, con cada grupo recibiendo
  exactamente tantas ubicaciones como productos tiene. La matriz de restricciones es
  totalmente unimodular, asi que la relajacion continua ya da optimo entero. Se resuelve
  con solver.
- *Problema 2* — dentro de cada zona, resolver el QAP del grupo. Los grupos son
  independientes entre si, asi que se puede paralelizar y elegir el resolvedor segun el
  tamano (exacto si entra, swaps si no).

---

## 6. Hipotesis seguidas y que dijo cada experimento

### 6.1 Tabla completa de resultados (test, 400 batches, pulgadas por batch)

| Variante | media | p95 | vs `current` | vs `demand_greedy` |
|---|---:|---:|---:|---:|
| `current` (slotting vigente) | 52.398 | 57.233 | — | +100,9% |
| **`demand_greedy`** (lambda=1) | **26.079** | 31.320 | **-50,2%** | — |
| `linear_assignment` (exacto lambda=1, hungaro) | 26.265 | 31.438 | -49,9% | +0,7% |
| `swap_search` global, lambda=0,5 | 26.964 | 32.759 | -48,5% | +3,4% |
| bi-nivel `demand_class` + zona `demand_greedy` | 26.010 | 31.529 | -50,4% | -0,3% |
| bi-nivel `merchant` + zona `demand_greedy` | 28.663 | 35.470 | -45,3% | +9,9% |
| bi-nivel `merchant` + zona `linear` (lambda=1) | 28.778 | 35.058 | -45,1% | +10,3% |
| bi-nivel `merchant` + zona swaps lambda=0,7 | 28.681 | 35.465 | -45,3% | +10,0% |
| bi-nivel `merchant` + zona swaps lambda=0,5 | 28.759 | 35.543 | -45,1% | +10,3% |
| bi-nivel `merchant` + zona swaps lambda=0,3 | 29.007 | 35.780 | -44,6% | +11,2% |

Barridos de una dimension por vez sobre la base (merchant, jaccard, top_k(10), zona swaps
lambda=0,5, zonas compactas por orden de recorrido):

| Barrido | Variantes | media |
|---|---|---:|
| Metrica de afinidad | jaccard / cosine / cooccurrence | 28.759 / 29.028 / 29.559 |
| Filtro | top_k / mutual_top_k | 28.759 / 28.631 |
| Agrupamiento | merchant / demand_class | 28.663 / 26.010 |

Todos los numeros provienen de los notebooks `02_GreedyvsCurrent`, `03_join_blocks`,
`05_zonas` y `07_sensibilidad`, con salidas guardadas.

### 6.2 Hipotesis 1 — "ubicar por demanda cerca del dock ya mejora mucho". CONFIRMADA

`demand_greedy` (ordenar productos por demanda descendente y ubicaciones por costo
ascendente, y emparejar) baja la distancia media por batch de 52.398 a 26.079: **-50,2%**,
en 0,02 segundos. Es un resultado fuerte y facil de defender.

Ademas, `linear_assignment` resuelve **exacto** el caso lambda=1 (algoritmo hungaro) y da
26.265, es decir **peor en rutas** que el greedy, tardando 2.338 segundos (39 minutos)
contra 0,02. Interpretacion: el greedy es esencialmente optimo para el objetivo lineal, y
la diferencia entre ambos esta por debajo del ruido de la simulacion de rutas. Es una
validacion cruzada util: confirma que la formulacion del termino lineal esta bien y que
no hay nada que ganar refinando esa parte.

### 6.3 Hipotesis 2 — "agregar afinidad mejora sobre el baseline por demanda". NO CONFIRMADA

Tres experimentos independientes lo dicen:

1. **Busqueda local global con afinidad** (`swap_search`, lambda=0,5, semilla
   `demand_greedy`): 26.964 contra 26.079 de su propia semilla. Es decir, el metodo
   **baja el objetivo** `C = lambda*L + (1-lambda)*Q` y **sube la distancia real**. Es el
   caso de manual de la brecha objetivo-evaluador: el termino cuadratico paga por acercar
   pares afines, pero para lograrlo tiene que alejar productos de alta demanda del dock, y
   eso cuesta mas de lo que ahorra.

2. **Peso creciente de la afinidad dentro de la zona**: con el Problema 1 fijo y compacto,
   pasar de zona sin afinidad (lambda=1, 28.778) a zona con afinidad da 28.681
   (lambda=0,7), 28.759 (lambda=0,5), 29.007 (lambda=0,3). La diferencia entre ignorar la
   afinidad y usarla con lambda=0,7 es del **0,3%**, y a partir de ahi darle mas peso
   **empeora monotonamente**. La afinidad intra-vendor no aporta.

3. **Eleccion de la metrica de afinidad**: jaccard (28.759), cosine (29.028), conteo crudo
   (29.559). El orden es el esperado teoricamente (normalizar ayuda), pero el rango total
   es 2,8% y todas quedan un 10% por encima del baseline sin afinidad. Elegir mejor la
   metrica no cambia la conclusion.

### 6.4 Por que la afinidad no aporta: dos explicaciones estructurales del dato

Esta es la parte que mas conviene discutir en la reunion, porque decide como sigue el
trabajo.

**(a) El batch no es la unidad de co-demanda; es la unidad de recorrido.**

La co-ocurrencia se calcula a nivel batch porque es la unica granularidad disponible:
`picking_events` **no tiene columna de orden**, solo `batch_id`. Pero un batch tiene ~76
SKUs distintos, resultado de mezclar muchas ordenes. La afinidad real (productos que se
piden juntos *en una orden*) queda diluida en el ruido de la agregacion por batch.

Hay un detalle del dataset que ofrece una salida: el readme dice que **todas las lineas de
una orden comparten merchant**. Entonces agrupar por `(batch_id, merchant_account_id)` da
pseudo-ordenes de ~7-8 SKUs en vez de batches de 76, y deberia recuperar mucha mas senal.
Esto **no se probo** y es la primera cosa que yo haria (ver seccion 9).

**(b) La co-ocurrencia observada es compatible con muestreo independiente.**

Del EDA de afinidad (notebook `01`): sobre train hay 15.554 SKUs con soporte medio 7,8
batches y **mediana 2**; se observan 4.322.498 pares co-ocurrentes. Bajo independencia, el
numero esperado de pares con al menos una co-ocurrencia es aproximadamente
`(SUM s_i)^2 / (2N) = 122.080^2 / 3.200 ~= 4,7 millones`. Observado 4,32 millones, es
decir **ligeramente por debajo de lo que produciria el puro azar**.

Sintoma coherente: los 20 pares con mayor Jaccard tienen todos score **exactamente 1,0**,
que es lo que pasa cuando dos SKUs de soporte 1 coinciden en el unico batch en que
aparecen. Eso es ruido, no afinidad, y es justo lo que el filtro `top_k` conserva.

*Advertencia de rigor*: este calculo es una estimacion de servilleta a partir de las
salidas ya publicadas, no un test. Confirmarlo requiere un test de permutacion (barajar
los SKUs entre batches conservando soportes y tamanos, y comparar la distribucion de
`n_ij`). Es barato y esta en la lista de pendientes.

**(c) Complemento geometrico.** Aunque hubiera afinidad, con ~76 bays distintas por batch
sobre 1.000 el recorrido serpenteante recorre casi todo el deposito igual; el costo lo
domina la travesia de pasillos, no la distancia entre pares de productos. El margen que la
afinidad puede capturar es estructuralmente chico en este layout y con estos tamanos de
batch.

### 6.5 Hipotesis 3 — "agrupar por vendor reduce la dimension sin costo". NO CONFIRMADA

Era el plan explicito heredado del punto de partida: los productos de un mismo vendor
comparten zona, se reduce la dimension y se respeta una estructura operativa natural.

El experimento dice que **cuesta caro**: todas las variantes bi-nivel por merchant quedan
entre 28,6k y 29,0k, un **10% peor** que `demand_greedy`. La razon es directa: hay 10
vendors balanceados de ~2.700 SKUs cada uno, y obligar a cada vendor a ocupar una zona
contigua impide poner los productos de alta rotacion de *todos* los vendors cerca del
dock. El agrupamiento por vendor pelea contra el unico efecto que si funciona.

En cambio agrupar por `demand_class` (A/B/C) da 26.010, apenas mejor que el baseline
(-0,3%), porque es justamente el agrupamiento que *no* pelea con la concentracion por
demanda: es la zonificacion clasica por rotacion. Pero la mejora esta dentro del ruido.

### 6.6 Hipotesis 4 — "las zonas deben ser compactas en el recorrido, no bandas por distancia al dock". CONFIRMADA (parcialmente)

En el notebook `05_zonas` se compararon dos formas de resolver el Problema 1: rankear
ubicaciones por distancia al dock (produce bandas concentricas) o por posicion en el
recorrido serpenteante (produce zonas contiguas). La dispersion media de cada zona a lo
largo del recorrido pasa de **10.402 a 2.202**: las zonas quedan casi 5 veces mas
compactas. Cualitativamente el efecto se ve en los graficos de zona sobre el plano.

Es un hallazgo correcto y bien fundamentado, pero su impacto en rutas quedo enmascarado
por el problema de fondo: compactar bien zonas de vendor sigue siendo peor que no zonificar
por vendor.

### 6.7 Hipotesis 5 — "el greedy esta lejos del optimo". NO CONFIRMADA

Ver 6.2: el optimo exacto del caso lambda=1 esta a 0,7% del greedy en rutas (y del lado
peor). Para el QAP completo la comparacion contra el optimo **todavia no se hizo**
(seccion 9).

---

## 7. Que se descarto y por que

| Alternativa | Motivo del descarte | Donde queda registrado |
|---|---|---|
| Resolver el QAP global exacto | 8,1e8 variables binarias; NP-hard | formulacion.md |
| Relajacion del QAP global (LP) | Sigue siendo enorme y la relajacion es floja | diseno-optimizacion.md §1 |
| Clustering por componentes conexas de la afinidad | **Degenerado**: da un componente gigante de ~15.500 SKUs mas miles de singletons, incluso con k=3. Componentes conexas mide conectividad transitiva, no comunidades densas | idea_clustering.txt, diseno-optimizacion.md §6 |
| Deteccion de comunidades (Louvain) | Se evaluo como plan A para "agrupar por afinidad"; se descarto al decidir que el agrupamiento seria por vendor y la afinidad se resolveria dentro de la zona | idea_clustering.txt, diseno-optimizacion.md §6 |
| Problema 1 como secuenciacion de clusters | No es un QAP de coeficientes fijos (el costo de cada bloque depende del orden acumulado); modelo exacto incomodo | diseno-optimizacion.md §2 opcion C |
| Problema 1 en forma cerrada (ordenar por demanda) | Da el mismo optimo (validado), pero no generaliza si se agrega afinidad inter-cluster; se prefirio plantearlo como optimizacion | diseno-optimizacion.md §3 |
| Afinidad inter-cluster en el Problema 1 | Convertiria el Problema 1 en un QAP; se descarto para mantener la descomposicion limpia. **Costo asumido**: si dos productos muy co-pedidos caen en clusters distintos, su proximidad no se optimiza | diseno-optimizacion.md §5 |
| `scipy.optimize.quadratic_assignment` (FAQ) | Otra heuristica no sancionada; no es la busqueda por swaps que se queria estudiar | diseno-optimizacion.md §4 |
| Slotting dinamico / reubicaciones | Fuera de alcance declarado; las 6.452 relocations del dataset se ignoran a proposito | GUIA.md §12 |
| Distancia intra-bay | Es como vienen los datos; dos productos en la misma bay quedan a distancia 0 | docs/README.md |
| Ruteo TSP optimo por batch | Se aproxima con serpenteante para no confundir la calidad del *ruteo* con la del *slotting* | docs/README.md |

Nota: el codigo esta limpio de todo esto. No hay ramas muertas ni implementaciones
abandonadas dentro del paquete; lo descartado quedo documentado, no comentado.

---

## 8. Limitaciones y riesgos abiertos

**De los datos**

1. **Dataset sintetico**. No hay datos reales de ShipHero incorporados todavia. Toda
   conclusion sobre la utilidad practica de la afinidad esta condicionada a que el
   generador haya producido co-demanda real, y la evidencia de la seccion 6.4 sugiere que
   no lo hizo.
2. **No hay `order_id`**. La unidad natural de co-demanda no es observable; solo el batch.
3. **Una sola ventana temporal**. Un unico corte train/test de 30 dias. No hay validacion
   con multiples ventanas ni analisis de estabilidad de la afinidad en el tiempo, pese a
   que el dinamismo de los patrones es parte de la motivacion de la propuesta.
4. **42% del universo sin demanda en train** (11.446 de 27.000 SKUs). Entran con f=0 y el
   greedy los manda al fondo del deposito. Es correcto, pero conviene reportarlo.

**De la implementacion (hallazgos de la revision de codigo)**

5. **La vecindad de la busqueda local es mas chica de lo documentado.** En
   [local_search.py:443-452](src/abs_affinity_based_slotting/methods/local_search.py#L443-L452)
   el candidato se calcula como `sku_at(location_of(k))`, que por construccion es siempre
   `k`. El docstring afirma que el movimiento captura casos donde `a_ij = 0`, pero tal como
   esta escrito los unicos intercambios propuestos son `(i, k)` con `a_ik > 0`. La vecindad
   real es mucho mas restringida que la disenada. Conviene arreglarlo antes de concluir
   nada sobre el poder de la busqueda local.
6. **`exact_qap` esta implementado pero nunca se corrio.** El solver exacto sobre el QAP
   completo existe en
   [exact.py](src/abs_affinity_based_slotting/methods/exact.py), pero ningun notebook lo
   usa. Es decir: **el gap de las heuristicas contra el optimo no esta medido**, que era
   justamente el rol que se le habia asignado en el diseno. Ademas, tal como esta armado el
   termino cuadratico (bucle sobre nnz x m x m) solo va a entrar en instancias muy chicas.
7. **La afinidad inter-cluster se calcula y se tira.** `aggregate_clusters` construye
   `G^T A G` y lo devuelve, pero `assign_locations_to_clusters` no lo usa. Esta bien
   documentado como extension planificada, pero hoy es codigo que no incide en el resultado.
8. **`GUIA.md` esta desactualizado.** Marca como pendientes cosas que ya se hicieron
   (afinidad, objetivo, heuristicas, swaps). Quedo superado por `docs/`. O se actualiza o
   se archiva; hoy es una fuente de confusion.

**Metodologicas**

9. **La brecha objetivo-evaluador no esta cuantificada.** Se sabe que existe y que en un
   caso invirtio el signo del resultado (6.3.1), pero no hay un estudio de correlacion
   entre `slotting_cost` y la distancia de ruta. Es un objeto de estudio interesante en si
   mismo y esta al alcance.
10. **No hay intervalos ni test de significancia.** Las diferencias del orden del 0,3%
    (bi-nivel demand_class vs greedy) se reportan como numeros puntuales. Con 400 batches
    se puede dar un intervalo por bootstrap sin costo.
11. **No hay harness de experimentos.** Cada notebook rearma el pipeline a mano. Funciona,
    pero no hay un lugar unico que recorra el `method_registry`, evalue y tabule.

---

## 9. Que queda por hacer

Ordenado por lo que mas cambia el resultado.

### Prioridad 1 — Decidir si hay senal de afinidad (1-2 semanas)

Sin esto, seguir optimizando la afinidad es optimizar ruido.

1. **Test de permutacion sobre la co-ocurrencia.** Barajar SKUs entre batches conservando
   soportes y tamanos de batch; comparar la distribucion de `n_ij` observada contra la
   nula. Si no se distinguen, esta cerrado el punto.
2. **Recomputar la afinidad a nivel `(batch, merchant)`** en vez de batch. Las ordenes son
   homogeneas por merchant, asi que esta agrupacion aproxima la orden (~7-8 SKUs en vez de
   76). Es un cambio de una linea en `build_cooccurrence` y puede cambiar todo el
   panorama.
3. **Filtrar por soporte minimo** antes de calcular Jaccard, para eliminar los pares de
   soporte 1 con score 1,0 que hoy contaminan el top-k.

### Prioridad 2 — Cerrar lo que ya esta empezado

4. **Arreglar la vecindad de `swap_search`** (punto 5 de la seccion 8) y re-correr el
   barrido de lambda.
5. **Medir el gap contra el optimo**: correr `exact_qap` sobre instancias chicas (una zona
   de pocos cientos de productos) y reportar cuanto pierden greedy, swaps y bi-nivel.
   Es lo que le da rigor a "usamos heuristicas porque el exacto no escala".
6. **Intervalos de confianza por bootstrap** sobre los 400 batches de test, para poder
   decir cuales diferencias son reales.
7. **Validacion con multiples ventanas temporales** (rolling origin), no un solo corte.

### Prioridad 3 — Extender el modelo

8. **Politica para las 3.000 ubicaciones sobrantes.** Hoy simplemente quedan las mas
   caras sin usar.
9. **Afinidad inter-cluster en el Problema 1** (lo convierte en QAP a nivel cluster, con
   10 grupos es trivial de resolver exacto). Es la extension natural del diseno y esta
   preparada en el codigo.
10. **Ruteo S-shape estricto** en vez de serpenteante simple, y verificar que las
    conclusiones no dependan de la politica de ruteo.
11. **Metaheuristicas** (simulated annealing, tabu, GA) solo si (1) da senal de afinidad y
    (2) la busqueda local arreglada se queda en optimos locales pobres. La literatura las
    usa mucho, pero por ahora no hay evidencia de que hagan falta.

### Prioridad 4 — Datos reales

12. **Incorporar datos de ShipHero.** Es lo que convierte el trabajo de "un metodo probado
    en sintetico" a "un metodo validado". Y es exactamente el hueco que el review
    sistematico de Islam & Uddin (2023) marca como el mas frecuente: *"very few researchers
    go beyond creating a new solution and testing out their findings in a real-life
    scenario or on actual data"*.

### Higiene

13. Actualizar o archivar `GUIA.md`. Consolidar los notebooks de experimentos.

---

## 10. Como se posiciona frente a la literatura leida

Se leyeron 7 trabajos (carpeta `papers/`).

| Trabajo | Que aporta | Como se uso |
|---|---|---|
| **Islam & Uddin (2023)**, *Correlated Storage Assignment: A Systematic Literature Review*, JIEM 16(2) | Revision sistematica de 60 trabajos de CSLAP (1985-2022). Clasifica soluciones en heuristicas, metaheuristicas y data mining. Confirma que casi todos los modelos son enteros NP-hard y que el esquema dominante es **de dos fases: agrupar SKUs por correlacion, luego asignar los grupos a zonas** | Es la referencia central. El metodo bi-nivel de este trabajo es exactamente ese esquema de dos fases. Tambien de aca sale la observacion de que S-shape es la politica de ruteo estandar en el area, lo que respalda la eleccion del serpenteante |
| **Reyes, Solano-Charris & Montoya-Torres (2019)**, *The SLAP: A literature review*, IJIEC 10 | Revision de 71 trabajos (2005-2017) del SLAP general. Taxonomia por metodo, objetivo y restricciones | Ubica el problema en la familia SLAP y justifica la terminologia. Marca como tendencia el uso de data mining para soporte de decision |
| **Li, Moghaddam & Nof (2015)**, *Dynamic storage assignment with product affinity and ABC*, IJAMT | El trabajo mas cercano. Combina afinidad y clasificacion ABC en un **QAP explicito**, con un score de relacion `Rij` construido a partir de lift y support count, resuelto con un GA voraz. Reporta 7,14% a 104,48% de mejora en tiempo de picking | Es el antecedente directo de la funcion objetivo de esta tesis (termino ABC/demanda + termino de afinidad). Diferencia importante: ellos **maximizan** el score de afinidad y usan la clasificacion ABC como indicador de fila; aca se **minimiza** distancia con ambos terminos en la misma escala fisica, lo que es mas defendible pero obliga a calibrar lambda |
| **Loiola et al. (2007)**, *A survey for the QAP*, EJOR 176 | Survey canonico del QAP: formulaciones, cotas inferiores, metodos exactos y metaheuristicas | Sustenta la caracterizacion del problema (Koopmans-Beckmann, NP-hard) y la justificacion de por que no se resuelve exacto a esta escala |
| **Han, Pei, Yin & Mao (2004)**, *Mining Frequent Patterns without Candidate Generation (FP-growth)*, DMKD 8 | Algoritmo FP-growth para itemsets frecuentes, un orden de magnitud mas rapido que Apriori | Es la via alternativa para construir la afinidad: en vez de co-ocurrencia por pares, itemsets frecuentes de tamano 3 o mas. **No se uso**. Es relevante porque el review de Islam & Uddin marca como hueco que "varios estudios solo miran la relacion entre dos items; se pueden considerar correlaciones entre tres o mas" |
| **Guan & Li (2018)**, *GA for Scattered Storage Assignment in Kiva MFS*, AJOR 8 | Almacenamiento disperso (un item en varias ubicaciones) basado en reglas de asociacion, modelo entero + GA | Contexto de sistemas parts-to-picker. El almacenamiento disperso esta explicitamente fuera de alcance aca (un SKU, una ubicacion) |
| **Brynzer & Johansson (1996)**, *Storage location assignment: Using the product structure*, IJPE 46-47 | Enfoque clasico: usar la estructura del producto (lista de materiales) en vez del historico para preestructurar el picking. Reporta -75% de informacion al picker | Antecedente historico. Muestra que la "afinidad" puede venir de la estructura del producto y no solo de la demanda, una fuente de senal que este dataset no tiene |

**Donde se posiciona esta tesis.** El aporte pretendido no es una metrica de afinidad
nueva ni un solver nuevo, sino **la comparacion honesta**: instancia unica, funcion de
costo explicita, evaluacion out-of-sample, y un banco de componentes intercambiables
(3 metricas de afinidad x 3 filtros x 2 agrupamientos x 6 metodos) que permite atribuir la
mejora a cada bloque de diseno por separado. Casi toda la literatura revisada reporta la
mejora de *su* metodo contra un baseline debil (random o ABC), sin separar el efecto de la
demanda del efecto de la afinidad. Este trabajo si lo separa, y por eso puede afirmar algo
que la literatura no suele decir: **en este escenario el 100% de la mejora viene del
termino de demanda y el termino de afinidad no aporta**.

Ese resultado negativo, bien fundamentado, es publicable y defendible. Pero conviene
confirmar antes que no es un artefacto del dataset (seccion 9, prioridad 1).

---

## 11. Preguntas para la reunion

1. **Sobre el dataset.** Si se confirma que la co-ocurrencia es indistinguible del azar,
   hay dos caminos: (a) conseguir datos reales de ShipHero con `order_id`, o (b) generar
   un dataset sintetico con afinidad **inyectada y controlada**, y estudiar a partir de que
   nivel de correlacion el metodo empieza a pagar. La opcion (b) es una tesis
   metodologicamente muy limpia (curva de "cuanta afinidad hace falta para que valga la
   pena") y no depende de terceros. ¿Cual prefieren?

2. **Sobre el alcance.** El resultado negativo actual es solido y esta bien construido.
   ¿Se reencuadra la tesis alrededor de el ("cuando conviene y cuando no conviene el
   slotting por afinidad"), o se insiste en obtener un resultado positivo?

3. **Sobre el agrupamiento por vendor.** Era el plan heredado y el experimento lo
   contradice claramente (10% peor). ¿Se mantiene como restriccion operativa dura (hay
   razones de negocio para que un vendor este junto?) o se abandona como criterio de
   zonificacion?

4. **Sobre el nivel de rigor esperado en el gap.** ¿Alcanza con mostrar el gap contra el
   optimo en instancias chicas, o se espera algun tipo de cota inferior para la instancia
   completa?

---

## Apendice — reproducibilidad

```bash
uv venv && uv pip install -e .
.venv/bin/python scripts/build_inputs.py     # genera data/processed/
```

Notebooks, en orden:

| Notebook | Contenido | Salidas guardadas |
|---|---|---|
| `00_EDA` | exploracion de las 5 tablas | si |
| `01_Affinity_Analysis` | co-ocurrencia, metricas, chequeo de circularidad | si |
| `02_GreedyvsCurrent` | current vs greedy vs hungaro | si |
| `03_join_blocks` | pipeline completo componible, busqueda local global | si |
| `04_metodos` | barrido baselines vs bi-nivel | **no** (celda sin ejecutar) |
| `05_zonas` | Problema 1: bandas por dock vs zonas compactas | parcial |
| `06_afinidad_intrazona` | aporte de la afinidad dentro de la zona de vendor | **no** |
| `07_sensibilidad` | barrido de una dimension por vez | si |

El solver exacto requiere licencia; las credenciales van en `.env`
(`SOLVER_LICENSE_*`), fuera del control de versiones.
