# Ideas para considerar la afinidad y mejorar la asignacion

> **Aviso (27 de octubre de 2026).** Todas las cifras de este documento se midieron con el plan
> aplicado de una vez al deposito en el corte, sin costo. Desde esa fecha el regimen de simulacion
> es otro: el deposito arranca como esta y el plan entra por las mudanzas
> ([sistema.md, seccion 7](sistema.md#7-la-simulacion)). Con ese regimen, las cifras de abajo son
> el techo de cada idea y no lo que se obtiene; los resultados vigentes estan en
> `notebooks/data2/correct_base/`.

Octubre de 2026. Ideas, no experimentos, en dos partes. La **parte A** busca saltos: cambios de
politica y de herramienta (colas por zona, RL, algoritmos geneticos, heuristicas evolucionadas
con un LLM) que pueden cambiar el resultado en decenas de puntos. La **parte B** reune mejoras
sobre lo que ya existe: medir mejor, el costo exacto del recorrido en S, mantener el plan y el
test de afinidad. Cada idea dice que es, por que deberia funcionar (en la cuenta y en un deposito
real), que necesita y que puede salir mal. Las cifras salen de los notebooks 03, 04 y 05, de
calculos de solo lectura sobre `data/v2` hechos para este documento (marcados "calculo propio"),
o de papers con su nivel de verificacion; las referencias de las dos partes estan juntas al final.

## Parte A. Ideas que pueden cambiar el panorama

### A.0 Resumen

La pregunta de esta parte es donde puede haber un salto, no un par de puntos. Dos mediciones
nuevas sobre los datos (calculo propio, en el scratchpad; hay que pasarlas a un notebook 06)
muestran que la palanca grande no esta en el plan estatico, sino en dos decisiones que el
deposito toma todo el tiempo: **cuando sale un batch** y **a donde va un SKU que se muda**.

1. **Colas por zona.** Si cada orden espera en la cola de su par de pasillos y el batch sale
   cuando la cola junta 25, la caminata baja 60% en `medium` y 74% en `big` contra FIFO, con
   alrededor de una hora de espera media. Es entre 11 y 14 puntos mejor que el re-batching por
   ventana con la misma espera, y es una regla de tres lineas.
2. **La afinidad pasa a valer mucho.** Con esa misma regla de liberacion, el plan por merchant le
   gana al greedy por demanda 17 puntos en `medium` y 25 en `big`. Con FIFO la diferencia es 2%.
   La afinidad de la orden es lo que hace que cada orden quepa en una zona.
3. **Las mudanzas son un re-slotting gratis.** En `medium` hay 191 por dia, y el 66% cae sobre el
   10% de SKUs mas pedidos, que hacen el 64% de las lineas. Decidir bien su destino reordena lo
   importante del deposito en semanas, sin trabajo extra.

Sobre esas dos decisiones tienen sentido las herramientas que pediste: RL, algoritmos geneticos y
busqueda de heuristicas con un LLM. La literatura es clara en que **no** aportan un salto por si
solas: contra una buena regla, RL gana entre 3 y 5 puntos y los geneticos entre 1 y 6. Por eso el
orden propuesto es primero la estructura (colas por zona y zonas bien disenadas) y despues el
aprendizaje para afinarla.

### A.1 Dos mediciones que cambian donde esta la palanca

**Colas por zona.** Una zona es un grupo de pasillos contiguos contando desde el dock: de a 1, de
a 2 (pares) o de a 4. Cada orden entra a la cola de la zona de su pasillo mas lejano, y cuando una
cola junta 25 ordenes sale un batch que entra solo a esa zona. En la variante **con plazo**,
cuando la orden mas vieja de una cola cumple el plazo, el batch sale igual y se completa hasta 25
con las ordenes mas viejas de otras colas, eligiendo en cada paso la que menos agrega a la
caminata.

Supuestos: es el plan estatico (reposicion `home`) sobre las ordenes de test y el recorrido en S
estricto. Las ordenes llegan parejas, como en el notebook 04 (25 por slot; un slot dura 32
minutos en `medium` y 14,4 en `big`). El batch sale apenas se forma, sin esperar turno, porque los
pickers alcanzan: en `medium` hay 20 y en promedio trabaja menos de uno a la vez. Para comparar
igual, la espera del re-batching por ventana se calcula con la misma regla: un pool de $25W$
ordenes sale cuando llega la ultima, asi que la espera media es $(25W+1)/50$ slots. Es menor que la
del notebook 04, que ademas suelta los batches de a uno por slot.

Caminata contra FIFO con `demand_greedy`, plan `merchant_aisle_fill`:

| dataset | politica | caminata | espera media | espera p95 |
|---|---|---:|---:|---:|
| `medium` | re-batching, ventana 2 | -31,6% | 33 min | |
| `medium` | re-batching, ventana 4 | -45,9% | 65 min | |
| `medium` | re-batching, ventana 8 | -57,3% | 129 min | |
| `medium` | colas por zona de 4 pasillos | -43,9% | 31 min | 64 min |
| `medium` | colas por par de pasillos | **-60,2%** | 61 min | 136 min |
| `medium` | colas por par, plazo de 128 min con relleno | -52,8% | 57 min | 116 min |
| `medium` | colas por pasillo | -67,7% | 122 min | 246 min |
| `big` | re-batching, ventana 4 | -51,4% | 29 min | |
| `big` | re-batching, ventana 8 | -62,6% | 58 min | |
| `big` | colas por zona de 4 pasillos | -62,2% | 28 min | 62 min |
| `big` | colas por zona de 4, plazo de 58 min con relleno | -53,8% | 26 min | 52 min |
| `big` | colas por par de pasillos | **-73,9%** | 55 min | 111 min |

Los valores del re-batching salen del notebook 05; los de las colas, del calculo propio. Las dos
cuentas usan la misma funcion de costo, y el FIFO del calculo propio (17.278 pulgadas por batch)
coincide con el de la simulacion (17.298).

**Por que funciona.** Un pool corta las ordenes en bloques arbitrarios. En un pool de 100 ordenes,
cuantas caen en un par de pasillos es aproximadamente $\text{Bin}(100, 1/4)$, y solo el 9% de las
veces son exactamente 25. Lo que sobra o falta termina mezclado en batches que cruzan pares. Una
cola por zona no tiene bordes: cada zona junta exactamente 25 ordenes y su batch camina
$2\,d_0(\text{pasillo mas lejano de la zona}) + 2L$. En S, un par cuesta lo mismo que su pasillo
mas lejano (parte B, seccion 2.1), por eso el par es un buen punto medio: con zonas de un solo
pasillo la caminata baja algo mas (de 7.010 a 5.684 pulgadas por batch en `medium`), pero la espera
se duplica.

Hay un detalle que importa: solo el 2% de las ordenes toca dos pares, pero como cada batch junta 25,
el 32% de los batches de pares termina entrando a otro par. Los batches puros caminan 5.762
pulgadas y el promedio de todos es 7.002. Tratar aparte esas ordenes es la primera mejora obvia
(A.3).

**Que pone el slotting.** La misma regla con el plan `demand_greedy` da -43,0% en `medium` y
-49,2% en `big`, contra -60,2% y -73,9% con el plan por merchant. La diferencia es cuantas zonas
toca cada orden: 1,02 pares por orden con el plan por merchant y 1,85 con el greedy. Las colas por
zona son la politica de batching que mas cobra la afinidad de la orden.

**Las mudanzas.** El generador repone una cantidad que casi no crece con la demanda (correlacion
0,11), asi que los SKUs populares se agotan y se mudan mucho mas seguido:

| | `medium` | `big` |
|---|---:|---:|
| mudanzas por dia | 191 | 423 |
| lineas del 10% de SKUs mas pedidos | 64% | 70% |
| mudanzas del 10% de SKUs mas pedidos | 66% | 73% |
| dias entre mudanzas de ese 10% (mediana) | 10 | 18 |

Esto explica por que la reposicion aleatoria borra toda la ganancia: reubica al azar justo a los
SKUs que hacen dos tercios de las lineas, y lo hace en pocas semanas. Visto al reves, el destino de
la mudanza es un canal de re-slotting que no cuesta trabajo extra, porque el SKU se mueve de todos
modos.

### A.2 Disenar las zonas para las colas: otro problema de optimizacion

**Que es.** Con colas por zona, el costo de una orden lo fija la zona a la que pertenece. Sea
$R(z)$ la caminata de un batch de la zona $z$, $Q = 25$, $\Lambda_z$ las ordenes por hora que caen
en ella y $C_z$ su cantidad de ubicaciones. Si cada merchant (o cada grupo de SKUs) va a una sola
zona,
$$\text{caminata por hora} \approx \sum_z \frac{\Lambda_z}{Q}\, R(z), \qquad
\text{espera media en } z \approx \frac{Q - 1}{2\,\Lambda_z}.$$
Las decisiones son el ancho de cada zona y que merchants van a cada una. Las restricciones son la
capacidad (los SKUs de la zona caben en $C_z$) y la espera (cada zona tiene que recibir al menos
$\Lambda_{\min} = (Q-1)/(2\,T)$ ordenes por hora para que su espera media no pase de $T$). Las
ordenes que cruzan zonas son la penalidad: entran a la cola de su zona mas lejana y ensanchan ese
batch.

**Por que.** Es la "otra medida de caminata" que buscabamos: ya no se minimiza la distancia de cada
pick ni los pares de SKUs separados, sino que cada orden quepa en una zona barata y que cada zona
reciba suficiente flujo. La afinidad entra como una particion: con datos reales, es particionar el
hipergrafo de ordenes (parte B, idea 1) con dos balances, de capacidad y de flujo. Hay una tension
que el problema resuelve: una zona angosta camina menos por batch, pero junta 25 ordenes mas
despacio.

**En un deposito real.** La demanda tiene picos en el dia. Una regla natural es cambiar el ancho de
las zonas segun la hora: pares en el pico y zonas de 4 o mas a la noche, para que la espera no se
dispare. Cada picker hace ordenes completas dentro de una zona, sin traspasos ni consolidacion,
asi que no cambia el proceso de empaque.

**Donde entra un algoritmo genetico.** La caminata y la espera se miden simulando las colas, que
tarda segundos, y el resultado no es suave en las decisiones (anchos discretos, merchants
indivisibles). Ademas hay varios objetivos: caminata, espera media, espera p95 y mudanzas. Un
NSGA-II da el **frente de Pareto** caminata contra espera, que es lo que decide un gerente, en vez
de un numero suelto. Con un BRKGA (Goncalves y Resende, 2011) cada individuo es una clave por
merchant, y el decodificador ordena los merchants por clave y los corta en zonas segun la
capacidad, reusando `merchant_aisle_fill`; en `medium` son 50 claves. Hay antecedentes:
Lesch et al. (2023) usan NSGA-II para el almacenamiento con cuatro objetivos, y Cano et al. (2022)
un genetico multiobjetivo para batching que equilibra caminata y tardanza. No encontre BRKGA
aplicado a slotting (la revision de Londe et al., 2025, no tiene ninguno).

**Riesgos.** En estos datos los merchants son casi iguales, asi que el frente va a quedar cerca del
diseno simple (pares fijos); el genetico paga con merchants heterogeneos. Contra una heuristica
constructiva fuerte los geneticos ganan poco: Koch y Waescher (2016) reportan 3,75% en batching, y
el memetico de Andre, Schlag y Schulz (2018) 3,4% en particion de hipergrafos, con horas de computo.
El valor esta en el frente, no en el porcentaje.

### A.3 Liberar batches con aprendizaje: RL o programacion dinamica

**Que es.** Decidir en cada momento si sale un batch, de que zona y con que relleno, mirando el
estado de todas las colas. La regla de A.1 (sale a las 25, o al vencer el plazo con relleno) es la
linea de base. Entre "sin plazo" (-60,2%, p95 de 136 minutos) y "plazo de 128 minutos" (-52,8%, p95
de 116) hay un frente que una politica que anticipa puede mover. Por ejemplo, puede esperar si a
una cola le faltan dos ordenes y llegan en minutos, rellenar con la cola vecina que menos ensancha,
o soltar dos colas parciales juntas en un batch de zona doble. El caso mas claro son las ordenes
que cruzan pares: hoy ensanchan el 32% de los batches, y una politica que las junte entre si o las
use solo de relleno puede acercar la caminata media de 7.002 a las 5.762 pulgadas de los batches
puros, es decir, de -60% a cerca de -67% contra FIFO, si el costo de despacharlas aparte es chico.

**Formulacion.** Es un proceso de decision de Markov con un estado chico: para cada zona, el largo
de la cola y la edad de la orden mas vieja, mas la hora. Las acciones son no hacer nada o soltar la
zona $z$, con un relleno fijado por regla. La recompensa es menos la caminata del batch menos un
costo por minuto de espera, o una restriccion sobre el p95 con multiplicador. Con 4 zonas en
`medium` y 8 en `big`, el estado es lo bastante chico para programacion dinamica aproximada o
busqueda directa de politicas; RL profundo se justifica recien si el estado incluye tasas que
cambian en el dia o prioridades por orden.

**Que dice la literatura.** Bukchin, Khmelnitsky y Yakuel (2012) plantean como MDP exacto la
decision de esperar o soltar [S]. Cals et al. (2021) y Beeks et al. (2022) entrenan PPO para
batching online: bajan las ordenes tardias (por ejemplo, 1,68% contra 3,17% de la mejor
heuristica) con 4 a 8% menos costo de picking, pero no optimizan caminata. Mahmoudinazlou et al.
(2025) muestran el riesgo: su agente cumple mas ordenes a tiempo caminando 4 a 5 veces mas. Lorenz,
Otto y Gendreau (2025) muestran que re-optimizar en cada llegada es casi optimo [A]. Ninguno usa
colas por zona.

**Que pediria para creerlo.** Que la politica aprendida mueva el frente caminata contra p95 de la
regla con plazo, fuera de muestra, y con un perfil de llegadas con picos (los datos actuales llegan
parejos; ver A.8).

### A.4 Ubicacion de mudanzas aprendida: RL, rollout y auto-organizacion

**Que es.** Elegir el destino de cada mudanza con una politica que mire hacia adelante. Bajo S solo
importa el pasillo, asi que la accion es elegir entre 8 pasillos (16 en `big`), y dentro del
pasillo cualquier hueco. Hay tres versiones, de menor a mayor ambicion:

1. **Regla de zona.** El SKU se muda a un hueco de la zona de su merchant y, si no hay, a la zona
   vecina. Es la base, y deberia acercarse a `home`.
2. **Rollout.** Para cada pasillo candidato, simular unas horas hacia adelante con la regla de zona
   y elegir el de menor caminata esperada, usando la formula cerrada de la parte B (seccion 2.2) o
   la de las colas como evaluador rapido. Lo que agrega sobre la regla es anticipar la escasez de
   huecos: ocupar el ultimo hueco libre de una zona caliente puede dejar afuera manana a un SKU mas
   pedido. Es el mismo problema que el bin packing online, donde la decision es irrevocable y la
   capacidad limitada.
3. **Auto-organizacion, sin plan.** El SKU va al pasillo donde estan los SKUs con los que salio en
   sus ultimas ordenes, si hay hueco, y si no al mas cercano al dock. No hace falta optimizar nada
   ni re-optimizar cuando cambia la demanda, porque el deposito se reordena solo con las mudanzas
   que ocurren de todos modos. Es la idea de las listas auto-organizadas (mover al frente lo que se
   usa) aplicada al deposito. Carlo y Giraldo (2012) proponen depositos "perpetuamente organizados"
   que reubican solo durante movimientos que ya ocurren, y Yuan, Graves y Cezik (2019), en un
   sistema semi-automatico, reasignan la ubicacion en cada visita y bajan 8 a 10% el viaje contra el
   azar [A].

**Por que.** Ya se vio que el destino de la mudanza decide si la ganancia se conserva (parte B,
idea 3), y que el canal es enorme y apunta a los SKUs que importan (A.1). La pregunta de la version
3 es empirica y concreta: partiendo del slotting vigente, con solo el canal de mudanzas, cuantas
semanas tarda en bajar el numero de pasillos por orden de 2,94 hacia 1,04. Si el 20% mas pedido se
muda en la mediana cada 20 dias, la respuesta deberia estar en semanas, no en meses.

**Que dice la literatura.** No hay RL para ubicar en depositos manuales con pasillos. En sistemas
robotizados (RMFS), Rimele et al. (2021) ganan 3 a 5 puntos sobre una buena regla greedy, pero
cuando ambos usan rollout la diferencia baja a 1,5 puntos; en su version que elige el hueco exacto,
la busqueda en arbol (MCTS) le gana a la red que la imita. Teck et al. (2025) reportan hasta 5,4%
sobre la mejor regla de la literatura [A]. La leccion es que, teniendo un simulador, buscar hacia
adelante rinde mas que aprender una politica sin modelo, y nosotros tenemos el simulador y una
formula cerrada.

**En un deposito real.** ShipHero ya ofrece "guided put-away": la decision ocurre en un momento en
que un operario mueve el SKU de todos modos. Una regla auto-organizada se adapta sola a merchants
que crecen o se van (parte B, idea 7). Hay que citar a Kofler et al. (2014), "Affinity based
slotting in warehouses with dynamic order patterns", cuyo titulo es casi el de la tesis y que
plantea el problema multiperiodo con una regla de afinidad.

**Transferencia.** Una politica que decide con atributos por pasillo y por SKU, y no con el
deposito entero como entrada, se puede entrenar en `small` y `medium` y probar en `big`. Los tres
datasets comparten la logica y cambian la escala, asi que son un banco de prueba natural. El unico
resultado verificado de "entrenar chico, usar grande" es el de Begnardi et al. (2024), en una
grilla con demanda uniforme, no en pasillos.

### A.5 Heuristicas escritas por un LLM y evolucionadas

**Que es.** En vez de disenar a mano la regla de ubicacion, la de liberacion o el decodificador de
zonas, se deja que un LLM proponga variantes del codigo de una funcion corta (por ejemplo,
`puntaje(sku, pasillo, estado)`), se evalua cada variante con el simulador sobre las semanas de
train y se conservan las mejores para la siguiente ronda. Es el esquema de FunSearch
(Romera-Paredes et al., 2024) y de Evolution of Heuristics (EoH; Liu et al., 2024).

**Por que.** El antecedente mas cercano es justamente el bin packing online, pariente directo de
ubicar mudanzas en huecos libres. Sobre instancias Weibull de 5.000 items, FunSearch encontro una
regla que usa 0,68% de bins de mas sobre la cota inferior, contra 3,98% de best-fit; EoH llego a
1,18% de promedio con unas 2.000 consultas, contra 4,13% de best-fit. AlphaEvolve (Novikov et al.,
2025, sin revision por pares) evoluciono la regla de asignacion de tareas de los centros de datos
de Google contra un simulador y recupera 0,7% del computo de toda la flota. No encontre ningun
trabajo que aplique esto a slotting, ubicacion o batching: es un nicho abierto.

**En un deposito real.** El resultado es una funcion de pocas lineas, legible y auditable, que se
puede poner en un WMS y explicar en la tesis, a diferencia de una red neuronal. El costo es de
computo y de llamadas al LLM, no de operacion.

**Riesgos.** Las reglas evolucionadas generalizan mal fuera de su distribucion de entrenamiento
(Sim, Renau y Hart, 2025) [A], y lineas de base simples compiten bien con estos sistemas (Gideoni,
Risi y Gal, 2026, preprint) [A]. Ademas, el generador es simple y una regla evolucionada puede
explotar sus artefactos, como la cantidad de reposicion casi fija. La defensa es evolucionar en
`small` y `medium`, y aceptar una regla solo si mejora en `big` y en `medium-alpha-1.3`, que no vio.

### A.6 Almacenamiento disperso: copias para que las ordenes no crucen zonas

**Que es.** Guardar un mismo SKU en varias ubicaciones de zonas distintas, para que cada orden
encuentre todo lo que pide dentro de una sola zona. Es lo que hacen los depositos de e-commerce con
estanterias mixtas (Weidinger y Boysen, 2018; Boysen, de Koster y Weidinger, 2019).

**Por que.** Las colas por zona funcionan mientras las ordenes no crucen zonas. En un 3PL real, un
merchant grande ocupa varios pasillos y sus ordenes los cruzan; copiar sus SKUs mas pedidos en cada
una de sus zonas vuelve puras esas ordenes. Gamez Alban et al. (2024) bajan la distancia hasta 36%
contra un disperso aleatorio y 56% contra el almacenamiento por volumen [A]; Schiffer et al. (2022)
muestran que en estanterias mixtas todas las palancas juntas ganan hasta 31% y el batching dinamico
hasta 9,2%.

**En los datos.** No hace falta: un merchant tiene unos 138 SKUs en `medium` y 249 en `big`,
contra 960 y 1.728 ubicaciones por pasillo, asi que cada merchant cabe en un pasillo y las ordenes
tocan 1,02 pares. Es una idea para datos reales con merchants grandes.

**Costos.** Cada copia es un hueco menos y mas reposiciones. Bock y Boysen (2025) muestran que
guardar durante los recorridos de picking gana entre 11,8 y 42% contra equipos separados [A], lo
que se conecta con la ubicacion de mudanzas de A.4. No encontre una cifra verificada del costo
extra de reposicion del almacenamiento disperso.

### A.7 Lo que no haria, y por que

- **RL para el plan estatico.** Un plan que se calcula una vez no es una decision secuencial. Para
  eso, la busqueda local con la formula cerrada o un genetico hacen lo mismo con menos datos y menos
  computo.
- **Resolver el QAP entero con una red neuronal.** Los solvers neuronales publicados con revision
  llegan a unos 100 elementos y quedan lejos de la busqueda tabu en QAPLIB (Tan y Mu, 2024: 26,8%
  de gap promedio); solo un preprint de 2026 dice igualarla en 500 elementos, combinandose con una
  busqueda por instancia. Nuestras instancias tienen entre 7.000 y 25.000 SKUs, y ademas el QAP no
  es el costo correcto bajo S (parte B, seccion 2).
- **Embeddings de SKUs aprendidos de las ordenes (prod2vec y similares).** No encontre ningun
  trabajo revisado que los use para slotting, y en estos datos solo recuperarian el merchant. Con
  datos reales pueden servir como atributos para la politica de A.4.
- **Computacion cuantica.** Un QUBO del QAP tiene un numero de variables del orden del cuadrado de
  la cantidad de SKUs; a esta escala no hay hardware que lo resuelva.

### A.8 Orden sugerido y que pedirle a ShipHero

| paso | que | por que primero | herramienta |
|---|---|---|---|
| 1 | Notebook 06: colas por zona con el simulador, las mudanzas y fuera de muestra | es la mayor ganancia medida y es barata | simulacion |
| 2 | Disenar zonas para las colas (A.2) | sin zonas puras las colas no rinden | NSGA-II o BRKGA |
| 3 | Ubicacion de mudanzas: regla de zona, despues rollout y auto-organizacion (A.4) | sin ella la ganancia se pierde | rollout, despues RL |
| 4 | Liberacion con aprendizaje (A.3) | mueve el frente una vez que existe | programacion dinamica, despues RL |
| 5 | Evolucion de heuristicas con LLM (A.5) | sobre las reglas de 3 y 4, cuando esten fijas | FunSearch o EoH |

Lo que hay que pedirle a ShipHero para estas ideas, ademas de lo de la parte B:
1. La hora real de llegada de cada orden y su perfil por hora del dia. Los datos solo traen el
   orden de llegada, y la espera de las colas depende de los picos.
2. Los horarios de corte y los compromisos de despacho, que fijan el plazo maximo de espera.
3. Si un picker puede trabajar con batches de una zona fija y si el WMS permite liberar batches
   continuamente en vez de por olas.

**Para la tesis.** Con FIFO, el plan por merchant gana 2% al greedy; con colas por zona gana 17
puntos en `medium` y 25 en `big`. Que la afinidad de la orden valga poco o mucho depende de como se
arman los batches, y esa es una conclusion que la literatura de slotting por afinidad no plantea.

## Parte B. Mejoras sobre lo que hay

### Resumen de la parte B

1. **El costo del recorrido en S tiene una forma exacta y simple.** Con el dock a la izquierda,
   un batch camina $2\,d_0(\text{pasillo mas lejano}) + 2L\lceil m/2 \rceil$, con $m$ los pasillos
   que visita. Hay dos palancas: hasta donde llega y cuantos pares de pasillos recorre.
2. **Con eso, el costo esperado con FIFO se calcula sin simular**, y predice la simulacion con
   un error de 0,3% o menos. Sirve como objetivo de optimizacion.
3. **La afinidad que paga es la de la orden, y el batching la atenua o la recupera.** Con FIFO,
   la afinidad de merchant pasa de un lift de 41 en la orden a 2,6 en el batch. Con re-batching,
   el piso del costo depende de cuantos pasillos toca cada orden.
4. **Medir la afinidad contra un modelo nulo correcto** antes de usarla, para no optimizar
   popularidad disfrazada.
5. **Mantener el plan** con reposicion guiada: sin eso la ganancia desaparece.
6. **Medir mejor**: ventanas realistas, tiempo ademas de distancia y evaluacion fuera de
   muestra. Va primero porque decide cuanto vale todo lo demas.

### 1. De donde partimos

- Con recorrido en S estricto, la caminata de un batch depende solo de que pasillos visita
  (manual, seccion 4.1).
- En los datos no hay afinidad entre SKUs mas alla de la popularidad. La unica estructura
  conjunta es el merchant: una orden nunca mezcla merchants (notebook 01; notebook 04, hecho 1).
- Un batch FIFO junta 25 ordenes de 19,8 merchants distintos en promedio (calculo propio).
- Pasillos por orden, $s$, con cada plan en `medium`: vigente 2,94; `demand_greedy` 2,40;
  `aisle_fill` 1,94; `merchant_aisle_fill` 1,04 (notebooks 04 y 05).
- Con FIFO el mejor plan es `aisle_fill` (-5,0% contra el greedy en `medium`); con
  re-batching y ventana 4, `merchant_aisle_fill` (-45,9%) (notebook 05).
- Ninguna variante de `swap_search` supera a `merchant_aisle_fill` (notebook 05).
- Con reposicion aleatoria los planes pierden casi toda la ganancia: en `medium` con ventana 4
  quedan todos entre -1,4% y +1,1% del greedy FIFO (notebook 05).

### 2. Un marco: que hace caminar a un batch y que afinidad paga

#### 2.1 El costo exacto del recorrido en S

Sea $S$ el conjunto de pasillos que visita un batch, $m = |S|$, $L$ el largo de un pasillo,
$\Delta$ la separacion entre pasillos y $d_0(a)$ la distancia del dock al frente del pasillo
$a$. Con el dock a la izquierda de todos los pasillos, $d_0(a_1) + (x_{a_m} - x_{a_1}) =
d_0(a_m)$, y la formula del manual (seccion 4.1) se reduce a
$$R_S(S) = 2\, d_0(\max S) + 2L \left\lceil \tfrac{m}{2} \right\rceil .$$
El costo tiene dos partes: **hasta donde llega** el batch (el pasillo mas lejano) y **cuantos
pares de pasillos recorre**. En `medium` ($L = 1.776$, $\Delta = 192$ pulgadas, pasillos
numerados desde 1): $R_S(\{3\}) = 5.248$; $R_S(\{1, 3, 5\}) = R_S(\{1, 3, 4, 5\}) = 9.568$;
$R_S(\{1, 2\}) = 4.864$, igual que visitar solo el pasillo 2. Visitar un pasillo extra que no
cambia el mas lejano y vuelve par la cantidad no cuesta nada.

Esto depende del S estricto: si con una cantidad impar el picker entrara al ultimo pasillo solo
hasta el pick mas lejano (una variante comun), el termino de paridad seria menor. Conviene
confirmarlo con ShipHero.

#### 2.2 Con FIFO

Sea $q_a$ la probabilidad de que una orden necesite el pasillo $a$ y $u_a$ la de que necesite
algun pasillo de numero $\ge a$. Si las $Q = 25$ ordenes de un batch son independientes:
$$E[m] = \sum_a \left(1 - (1 - q_a)^Q\right), \qquad
E[d_0(\max)] = d_0(1) + \Delta \sum_{a \ge 2} \left(1 - (1 - u_a)^Q\right),$$
$$E[R_S] = 2\,E[d_0(\max)] + L\,\bigl(E[m] + P(m \text{ impar})\bigr).$$

**Validacion** (calculo propio, `medium`, $q_a$ y $u_a$ medidos sobre las ordenes de test,
$P(m \text{ impar})$ por Monte Carlo):

| plan | pasillos, formula | pasillos, simulacion | $R_S$, formula | $R_S$, simulacion |
|---|---:|---:|---:|---:|
| `demand_greedy` | 7,63 | 7,63 | 17.588 | 17.624 |
| `aisle_fill` | 6,96 | 6,97 | 16.721 | 16.748 |
| `merchant_aisle_fill` | 7,30 | 7,28 | 17.334 | 17.278 |

Que dice la formula:
- El termino $E[m]$ es concavo en cada $q_a$: para los mismos pasillos por orden, conviene que
  los $q_a$ sean muy desparejos. Con $Q = 25$, un pasillo con $q_a \ge 0{,}15$ se visita en el 98%
  de los batches. Por eso con FIFO gana concentrar la demanda (`aisle_fill`).
- El termino $u_a$ es una union a nivel orden: paga que las ordenes no lleguen lejos. Ahi la
  afinidad de la orden cuenta tambien con FIFO, aunque solo por el alcance lateral, que pesa
  $\Delta$ por pasillo, mucho menos que $L$.

#### 2.3 Con re-batching

En un pool de $25W$ ordenes, sea $N_a$ la cantidad que necesita el pasillo $a$ y $N_{\ge a}$ la
que necesita algun pasillo $\ge a$. Cada batch tiene a lo sumo 25 ordenes, asi que al menos
$\lceil N_a/25 \rceil$ batches entran al pasillo $a$ y al menos $\lceil N_{\ge a}/25 \rceil$
llegan hasta $a$ o mas lejos. Como $2\lceil m/2 \rceil \ge m$, la caminata total del pool cumple
$$\sum_k R_S(k) \;\ge\; 2\Bigl[W d_0(1) + \Delta \sum_{a \ge 2} \lceil N_{\ge a}/25 \rceil\Bigr]
+ L \sum_a \lceil N_a / 25 \rceil .$$
El piso depende de cuantas ordenes necesitan cada pasillo y cuantas llegan lejos: de los
**pasillos por orden** y de que las ordenes frecuentes se queden **cerca del dock**. Dividiendo
por $W$, los pasillos por batch son al menos $s$.

Con ventana 4 los planes quedan en el orden de su $s$: pasillos por batch 3,55
(`merchant_aisle_fill`, $s$ = 1,04), 4,85 (`aisle_fill`, 1,94), 5,73 (`demand_greedy`, 2,40),
6,86 (vigente, 2,94) (notebooks 04 y 05). El piso no se alcanza: los valores observados son de 2
a 3,4 veces $s$. La cota sirve para medir cuanto le falta al algoritmo de re-batching en cada
pool.

#### 2.4 Cuanto atenua el batching la afinidad

Sea $r_i$ la probabilidad de que una orden pida el SKU $i$ y $p_m \approx 0{,}02$ la fraccion de
ordenes de su merchant. En los datos las ordenes tienen de 2 a 5 SKUs sin repetir (uniforme), y
eso da, para dos SKUs del mismo merchant elegidos independientemente dentro de el,
$r_{ij} \approx 0{,}82\, r_i r_j / p_m$ (el factor es $E[k(k-1)]/E[k]^2 = 10/12{,}25$). El lift
a nivel orden es entonces $0{,}82/p_m \approx 41$. A nivel batch FIFO, con $Q$ ordenes
independientes,
$$\text{lift del batch} \approx \frac{Q\, r_{ij} + Q(Q-1)\, r_i r_j}{Q^2\, r_i r_j}
= \frac{41 + 24}{25} \approx 2{,}6 .$$
La senal del merchant se atenua unas 16 veces pero no desaparece. Mantel, Schuur y Heragu (2007)
plantean, sin testearlo, que "el batching extenso extingue el efecto de un slotting inteligente";
con FIFO es en gran parte cierto, y con re-batching los datos dicen lo contrario (-46%).

### 3. Ideas

#### Idea 1. Optimizar el costo exacto del S, a nivel orden

**Que es.** Asignar SKUs a pasillos para minimizar el costo de la seccion 2: con FIFO, la formula
cerrada de 2.2; con re-batching, los terminos del piso de 2.3 ($N_a$ y $N_{\ge a}$), es decir,
pocas ordenes por pasillo, pocos pasillos por orden y las ordenes frecuentes cerca del dock. Se
resuelve con busqueda local: mover un SKU de pasillo cambia solo las ordenes que lo contienen,
asi que el cambio en $q_a$, $u_a$ o $N_a$ se calcula rapido.

**Por que.** Es el objetivo que de verdad paga el picker en S, no una aproximacion por pares. El
termino cuadratico del QAP con $D$ = `aisle` cuenta pares de SKUs en pasillos distintos; el
costo real depende de la union de pasillos, que crece de otra manera: por ejemplo, 6 SKUs de un
batch repartidos 3 y 3 en dos pasillos tienen los mismos pares en el mismo pasillo que repartidos
4, 1 y 1 en tres pasillos, pero el segundo caso entra a un pasillo mas.

La parte de "pasillos por orden" es el *SKU partition problem* de Kress, Boysen y Pesch (2017):
particionar SKUs en grupos de tamano fijo minimizando los grupos que toca cada orden. Ellos lo
estudian para carruseles y estanterias moviles con picking orden por orden; que sea el piso del
re-batching en S es una observacion de este trabajo. Es particionar un hipergrafo (las ordenes
son hiperaristas) con la metrica de conectividad, para la que hay herramientas maduras como
KaHyPar (Schlag et al., 2022). Egas y Masel (2010) midieron pasillos visitados con un
clustering de SKUs por pasillo y obtuvieron 13 a 17% menos pasillos que asignar por demanda
(segun sus tablas; el abstract dice 20 a 30%).

Dos consecuencias de la forma exacta del costo:
- **La unidad natural de zona es un par de pasillos**, porque dos pasillos cuestan lo mismo que
  el mas lejano de ellos. Las zonas conviene armarlas como pares desde el dock: (1, 2), (3, 4),
  y asi.
- **Los merchants chicos se empaquetan por merchant**, no por popularidad: ordenar una zona
  compartida por popularidad sube los pasillos por orden.

**En un deposito real.** En un 3PL cada orden es de un cliente: zonificar por cliente es la
afinidad de primer orden, y ademas facilita conteos, devoluciones y la facturacion del espacio.
Si hay afinidad dentro del cliente (kits, talles, repuestos), este objetivo la aprovecha sin
cambiar nada.

**Como medirla.** Contra `merchant_aisle_fill` en la grilla del notebook 05, con ventanas de 1 a
4, fuera de muestra.

**Riesgos.** Con estos datos la parte de pasillos por orden deberia empatar con
`merchant_aisle_fill`, porque los merchants ya son las componentes del hipergrafo; donde puede
ganar es en el alcance (que merchants van cerca del dock) y en la paridad. Con FIFO, la formula
cerrada puede mejorar a `aisle_fill`, que ordena por demanda sin mirar ni la paridad ni las
ordenes.

#### Idea 2. Medir la afinidad contra un modelo nulo correcto

**Que es.** Antes de usar un par en $A$, verificar que co-ocurre mas de lo que produciria el azar
dados la popularidad de cada SKU, su merchant y el tamano de las ordenes. El modelo nulo es una
**permutacion que preserva los tamanos de orden y las frecuencias de cada SKU** (swap
randomization; Gionis et al., 2007), la misma que ya se uso para mostrar que los datos no tienen
afinidad. Con ella se obtiene un p-valor por par; se controla la tasa de falsos descubrimientos
(Benjamini y Hochberg, 1995) y, para pares con pocos datos, se usa un estimador contraido como
el Gamma-Poisson de DuMouchel (1999). Solo los pares que sobreviven entran a $A$.

**Por que.** Jaccard, coseno y conteo crecen con la popularidad aunque no haya afinidad: bajo
independencia, el coseno vale $\sqrt{s_i s_j}/N$. Un test hipergeometrico por par no alcanza,
porque ignora que las ordenes tienen tamano fijo y sin repeticion: en estos datos el esperado
real es 0,82 del que calcula, y el test queda conservador. Brin, Motwani y Silverstein (1997)
muestran una regla con 80% de confianza que es en realidad una correlacion negativa, y Webb
(2007) que buscar patrones sin controlar el error encuentra muchos falsos en datos aleatorios.

**En un deposito real.** La afinidad real (complementos, kits, variantes) existe pero esta
mezclada con la popularidad. Calcular el esperado dentro de cada merchant es clave en un 3PL,
porque dos SKUs del mismo cliente co-ocurren por estructura.

**Valor.** Para la tesis, alto: es la precondicion que la literatura no exige
([estado del arte](estado-del-arte.md), seccion 5). Con los datos actuales no cambia la
asignacion. Con conjuntos con afinidad plantada de ShipHero, decide si `swap_search` optimiza
senal o ruido.

#### Idea 3. Mantener el plan: reposicion guiada, movimientos y huecos por zona

**Que es.** Tres reglas operativas:
1. **Reposicion en la zona del plan.** Cuando un SKU agotado necesita ubicacion nueva, elegir un
   hueco libre en su zona, lo mas cerca posible de su lugar, en vez de uno al azar.
2. **Un presupuesto chico de movimientos por dia** para devolver a su zona los SKUs que quedaron
   afuera, elegidos por ganancia por movimiento.
3. **Huecos libres repartidos por zona**, en proporcion a las mudanzas que recibe cada una.

**Por que.** Con reposicion aleatoria (la de los datos) los planes pierden casi toda la
ganancia: en `medium` con ventana 4 quedan entre -1,4% y +1,1% del greedy FIFO, y el 37-38% de
los SKUs termina fuera de su ubicacion del plan. Con la ubicacion del plan reservada (`home`)
la ganancia se conserva; con `objective_greedy`, que ya esta en el codigo, se pierde parte:
`merchant_aisle_fill` con ventana 4 da -38,5% en vez de -45,9% en `medium`, y -36,2% en vez de
-51,4% en `big` (notebook 05). La ganancia realista esta entre esos dos extremos. Kofler et al.
(2011) muestran que pocas tareas diarias de "healing" alcanzan en meses un nivel competitivo con
reordenar todo, y en una tabla de los mismos autores 20, 60 y 1.400 traslados bajan la
distancia 11%, 23% y 64% (rendimientos decrecientes) [S].

**En un deposito real.** ShipHero vende "guided put-away" (diapositivas FaMAF 2025). Elegir bien
el destino de una mudanza que ocurre de todos modos no agrega trabajo; los movimientos extra se
hacen en turnos de baja demanda.

**Costos y riesgos.** `home` es almacenamiento dedicado: en un deposito real la reposicion no es
instantanea como en el generador, y mientras el SKU esta agotado su hueco queda reservado y
vacio. Si una zona se llena, hace falta una regla de desborde a la zona vecina. Bartholdi y
Hackman (2008) muestran que asignar espacio proporcional a la raiz de la demanda minimiza las
reposiciones: si los SKUs mas pedidos se agotan menos, se mudan menos.

#### Idea 4. Optimizar el plan con el batcher adentro

**Que es.** En vez de optimizar el plan con una afinidad fija, evaluar cada cambio candidato del
plan por su efecto sobre la caminata despues de re-batchear. Por ejemplo, una busqueda local
sobre la asignacion de merchants a zonas (50 merchants en `medium`) donde cada candidato se
evalua corriendo `AisleCoverBatching` sobre las ordenes de train.

**Por que.** El plan y el batching dependen uno del otro: la afinidad que importa es la de los
batches que se van a armar, y esos batches dependen del plan. Recalcular la afinidad sobre los
batches resultantes y volver a ubicar seria circular (los batches ya reflejan las zonas del
plan); meter el batcher en la evaluacion no. Es viable porque re-batchear todo el periodo de test
de `medium` tarda unos 3 segundos (notebook 05). Kubler, Glock y Bauernhansl (2020) resuelven
juntos asignacion dinamica, batching y ruteo en picker-to-parts manual, y Van Gils et al. (2018)
encuentran interacciones significativas entre almacenamiento, batching y ruteo en un caso real.

**En un deposito real.** ShipHero ya hace smart batching. Un slotting que no tiene en cuenta el
batching que va a correr optimiza para un deposito que no existe. Las diapositivas dicen "hasta
25 ordenes" por batch: permitir batches mas chicos es una extension natural del batcher.

**Riesgos.** Sobreajustar a las ordenes de train; evaluar siempre fuera de muestra.

#### Idea 5. Afinidad dentro del pasillo: paradas, busqueda y altura

**Que es.** Con S estricto la posicion dentro del pasillo no cambia la distancia, pero si el
tiempo: cada parada tiene un costo fijo (frenar, buscar, alcanzar). Dentro de la zona de un
merchant, poner en la misma bay los SKUs que aparecen en la misma orden reduce paradas; poner los
mas pedidos a una altura comoda reduce el tiempo por linea.

**Por que.** En la reparticion clasica (Tompkins et al., citado por de Koster et al., 2007) el
viaje es el 50% del tiempo de picking, la busqueda el 20% y la extraccion el 15%. Larco et al.
(2017) estiman con datos de WMS que un pick en el nivel bajo tarda 1,2 s mas que en el medio,
sobre un ciclo de 25 s por linea, y que cada unidad adicional suma casi 1 s. Batt y Gallino
(2019) estiman 0,21 s por pie de distancia y un efecto de la densidad del bin.

**Lo que dicen los datos.** El generador de ShipHero modela el tiempo de un batch como unos 14,8 s
por linea mas la caminata a 1,4 m/s, sin costo por parada: una regresion de la duracion de cada
batch de `medium` sobre lineas, paradas y distancia da 0,04 s por parada y $R^2$ 0,98 (calculo
propio). Con ese modelo caminar es el 28% del tiempo, y bajar 46% la distancia baja el tiempo
alrededor de 13%. Es el modelo del generador, no el de un deposito real, donde la literatura
pone el viaje cerca del 50%.

**Que necesita.** Timestamps reales de un WMS para estimar un modelo como el de Larco o Batt:
tiempo entre picks segun distancia, misma bay, nivel, cantidad y picker.

**Riesgos.** La evidencia sobre la altura es mixta: Loske, Koreis y Klumpp (2022), con 1,57
millones de picks, encontraron la golden zone 2,55% mas lenta que el nivel del piso.

#### Idea 6. Area de pick rapido con duplicados, elegida por ordenes completas

**Que es.** Tener copias de los SKUs mas pedidos de cada merchant en un par de pasillos junto al
dock. Las ordenes que se completan enteras ahi se re-batchean entre si, y sus batches entran solo
a esa zona; las demas se recogen en la zona de su merchant.

**Por que.** En `medium`, los 768 SKUs mas pedidos en train completarian el 25% de las ordenes de
test y estarian en el 66% de las lineas; con 1.536, el 43% de las ordenes (calculo propio). Un
batch que entra solo a los pasillos 1 y 2 camina 4.864 pulgadas, contra unas 9.500 de la media
de `merchant_aisle_fill` con ventana 4. Es el problema forward-reserve (Hackman y Rosenblatt,
1990). La afinidad entra en el criterio: conviene elegir los SKUs que completan ordenes, no solo
los mas populares. Sin afinidad en los datos dan casi lo mismo (24% contra 25% de ordenes
completas); con afinidad real, completar ordenes deberia ganar. Debold (2025) duplica SKUs entre
zonas con datos de HelloFresh y reporta hasta 19,5% sobre los benchmarks [S]; Gamez Alban et al. (2024),
con almacenamiento disperso que acerca los SKUs de una misma orden, reportan hasta 36% menos
distancia que un disperso aleatorio.

**Costos y riesgos.** No hay lugar libre al frente: con `merchant_aisle_fill` los 768 huecos de
`medium` quedan en el ultimo pasillo, y armar el area rapida corre las zonas hacia el fondo, lo
que sube el alcance de esas zonas. Sacar un cuarto de las ordenes de las zonas tambien empeora el
llenado de sus batches. Y las copias cuestan reposiciones internas desde la reserva, que los datos
no modelan. Hay que medirlo; puede no compensar.

#### Idea 7. Deriva de merchants: zonas que cambian de tamano

**Que es.** Una regla para redimensionar las zonas cuando un merchant crece, entra o se va:
holgura por zona, una revision periodica, y el costo de mudar un cliente de zona en la cuenta.

**Por que.** En un 3PL los clientes cambian mucho mas que los productos de un retailer, y una zona
dimensionada por el flujo de hoy desborda manana. Jamili, van den Berg y de Koster (2025) muestran
que a los clientes de baja demanda les conviene compartir espacio y a los de alta demanda tenerlo
dedicado: zonas propias para los grandes y zonas compartidas, agrupadas por merchant, para los
chicos. Kofler et al. (2011) dan la forma de corregir de a poco en vez de reordenar todo.

**En los datos.** Los 50 merchants de `medium` piden casi lo mismo (entre 1,9 y 2,1% de las
ordenes cada uno), y los datos son estacionarios: el problema no aparece. Hay que preguntarle a
ShipHero como es la realidad.

#### Idea 8. Congestion

**Que es.** Si muchos batches entran a la vez a la misma zona, los pickers se bloquean. Se puede
penalizar la varianza de picks por pasillo, poner un tope de batches simultaneos por zona y
secuenciar la liberacion de batches.

**Por que.** Hong, Johnson y Peters (2012) recuperan entre 5 y 15% del tiempo total armando y
secuenciando batches para reducir el bloqueo, y Hong et al. (2010) muestran que lo que mas
bloquea es la variabilidad de picks por pasillo.

**En los datos.** En `medium` un batch dura 28,6 minutos y sale uno cada 32: casi nunca hay dos a
la vez. En `big` dura 37 minutos y sale uno cada 14,4: unos 2,6 a la vez. El simulador procesa
los batches de a uno y no puede mostrar congestion. Es una pregunta para la operacion real antes
que un experimento.

#### Idea 9. Medir mejor (primera prioridad)

- **Ventanas realistas.** Las conclusiones tienen que sostenerse con ventanas de 1 a 4, donde la
  espera media llega como mucho a 113 minutos en `medium`, no con 32 (1.007 minutos).
- **Fuera de muestra y con varios cortes.** Optimizar con un periodo y medir en otro, repitiendo
  con cortes rodantes. La distancia entre el oraculo y lo aprendido en el notebook 03 (-36%
  contra -9% en `big`) muestra cuanto se puede sobreajustar.
- **Tiempo ademas de distancia**, con un modelo de tiempo explicito (idea 5).
- **Cota inferior por pool** (seccion 2.3), para saber cuanto le falta al batcher.
- **El valor de la afinidad.** Con conjuntos de ShipHero con afinidad plantada a distintas
  intensidades, medir cada idea en funcion de la intensidad. No inyectar afinidad propia.

### 4. Prioridades

| idea | que gana con estos datos | esfuerzo | depende de |
|---|---|---|---|
| 9. medir mejor | numeros defendibles | medio | nada |
| 1. costo exacto del S | algunos puntos con FIFO; con re-batching, sobre todo alcance y paridad | medio | nada |
| 3. mantener el plan | entre la perdida de `objective_greedy` y `home` (6 a 15 puntos) | bajo | reglas de desborde |
| 2. afinidad contra el azar | nada en la asignacion; alto valor para la tesis | bajo | nada |
| 4. batcher adentro | a medir | medio | idea 1 |
| 7. deriva de merchants | nada con datos estacionarios | medio | datos reales |
| 5. dentro del pasillo | el generador no lo modela | alto | timestamps reales |
| 6. pick rapido | a medir; puede no compensar | alto | modelo de reserva |
| 8. congestion | nada en los datos actuales | alto | simulador con tiempo |

### 5. Que pedirle a ShipHero

1. Conjuntos con afinidad plantada a distintas intensidades (el parametro del generador).
2. Si es posible, datos reales: timestamps de picks, demanda por merchant y su variacion en el
   tiempo, kits o bundles.
3. Como recorre el picker el ultimo pasillo cuando la cantidad es impar, y si usa los pasillos
   transversales.
4. Cuanto puede esperar una orden antes de entrar a un batch, y si los batches pueden tener menos
   de 25 ordenes.
5. Cuantos pickers trabajan a la vez por zona y si hay congestion.
6. Si el guided put-away se usa, con que regla elige el destino y cuanto tarda una reposicion.

## Referencias

Nivel de verificacion: [V] cotejado con el texto o un indice bibliografico; [A] solo abstract;
[S] fuente secundaria o no verificado en esta revision.

- Andre, R., Schlag, S. y Schulz, C. (2018). Memetic multilevel hypergraph partitioning. GECCO
  2018, 347-354. DOI 10.1145/3205455.3205475 [V]
- Bartholdi, J. J. y Hackman, S. T. (2008). Allocating space in a forward pick area of a
  distribution center for small parts. IIE Transactions 40:1046-1053.
  DOI 10.1080/07408170802167662 [V]
- Batt, R. J. y Gallino, S. (2019). Finding a needle in a haystack: the effects of searching and
  learning on pick-worker performance. Management Science, 2624-2645.
  DOI 10.1287/mnsc.2018.3059 [V]
- Beeks, M., Refaei Afshar, R., Zhang, Y., Dijkman, R., van Dorst, C. y de Looijer, S. (2022).
  Deep reinforcement learning for a multi-objective online order batching problem. ICAPS
  32(1):435-443. DOI 10.1609/icaps.v32i1.19829 [V]
- Begnardi, L., Baier, H., van Jaarsveld, W. y Zhang, Y. (2024). Deep reinforcement learning for
  two-sided online bipartite matching in collaborative order picking. ACML 2023, PMLR
  222:121-136 [V]
- Benjamini, Y. y Hochberg, Y. (1995). Controlling the false discovery rate. JRSS-B
  57(1):289-300 [V]
- Bock, S. y Boysen, N. (2025). Stow & pick: optimizing combined stowing and picking tours in
  scattered storage warehouses. EJOR 324(3):1002-1016. DOI 10.1016/j.ejor.2025.02.037 [A]
- Boysen, N., de Koster, R. y Weidinger, F. (2019). Warehousing in the e-commerce era: a survey.
  EJOR 277(2):396-411. DOI 10.1016/j.ejor.2018.08.023 [A]
- Brin, S., Motwani, R. y Silverstein, C. (1997). Beyond market baskets: generalizing
  association rules to correlations. SIGMOD, 265-276 [V]
- Bukchin, Y., Khmelnitsky, E. y Yakuel, P. (2012). Optimizing a dynamic order-picking process.
  EJOR 219:335-346 [S]
- Cals, B., Zhang, Y., Dijkman, R. y van Dorst, C. (2021). Solving the online batching problem
  using deep reinforcement learning. Computers & Industrial Engineering 156:107221.
  DOI 10.1016/j.cie.2021.107221 [V, preprint]
- Cano, J. A., Cortes, P., Campo, E. A. y Correa-Espinal, A. A. (2022). Multi-objective grouping
  genetic algorithm for the joint order batching, batch assignment, and sequencing problem.
  International Journal of Management Science and Engineering Management 17(3):188-204.
  DOI 10.1080/17509653.2021.1991852 [A]
- Carlo, H. J. y Giraldo, G. E. (2012). Toward perpetually organized unit-load warehouses.
  Computers & Industrial Engineering 63(4):1003-1012. DOI 10.1016/j.cie.2012.06.012 [A]
- de Koster, R., Le-Duc, T. y Roodbergen, K. J. (2007). Design and control of warehouse order
  picking: a literature review. EJOR 182(2):481-501. DOI 10.1016/j.ejor.2006.07.009 [V]
- Debold (2025). A storage assignment approach considering SKU repetitions in sequential zone
  picking. Computers & Industrial Engineering 210, 111482 [S]
- DuMouchel, W. (1999). Bayesian data mining in large frequency tables. The American
  Statistician. DOI 10.1080/00031305.1999.10474456 [V]
- Egas, C. y Masel, D. (2010). Determining warehouse storage location assignments using
  clustering analysis. 11th IMHRC Proceedings [V]
- Gamez Alban, H. M., Cornelissens, T. y Sorensen, K. (2024). A new policy for scattered storage
  assignment to minimize picking travel distances. EJOR 315(3):1006-1020.
  DOI 10.1016/j.ejor.2024.01.013 [V]
- Gideoni, Y., Risi, S. y Gal, Y. (2026). Simple baselines are competitive with code evolution.
  arXiv 2602.16805, preprint [A]
- Gionis, A., Mannila, H., Mielikainen, T. y Tsaparas, P. (2007). Assessing data mining results
  via swap randomization. ACM Transactions on Knowledge Discovery from Data 1(3) [S]
- Goncalves, J. F. y Resende, M. G. C. (2011). Biased random-key genetic algorithms for
  combinatorial optimization. Journal of Heuristics 17(5):487-525.
  DOI 10.1007/s10732-010-9143-1 [S]
- Hackman, S. T. y Rosenblatt, M. J. (1990). Allocating items to an automated storage and
  retrieval system. IIE Transactions 22(1):7-14 [V]
- Hong, S. et al. (2010). Picker blocking en sistemas de picking por batches. Progress in
  Material Handling Research (IMHRC 2010), digitalcommons.georgiasouthern.edu/pmhr_2010/27 [V]
- Hong, S., Johnson, A. L. y Peters, B. A. (2012). Batch picking in narrow-aisle order picking
  systems with consideration for picker blocking. EJOR 221(3):557-570 [V]
- Jamili, N., van den Berg, P. L. y de Koster, R. (2025). IISE Transactions 57(3):336-350.
  DOI 10.1080/24725854.2024.2322097 [V; titulo no relevado]
- Koch, S. y Waescher, G. (2016). A grouping genetic algorithm for the order batching problem in
  distribution warehouses. Journal of Business Economics 86(1):131-153.
  DOI 10.1007/s11573-015-0789-x [V, working paper]
- Kofler, M. et al. (2011). Re-warehousing vs. healing: strategies for warehouse storage
  location assignment. IEEE LINDI, 77-82. DOI 10.1109/LINDI.2011.6031124 [V]
- Kofler, M., Beham, A., Wagner, S. y Affenzeller, M. (2014). Affinity based slotting in
  warehouses with dynamic order patterns. En Advanced Methods and Applications in Computational
  Intelligence, Springer, 123-143. DOI 10.1007/978-3-319-01436-4_7 [A]
- Kress, D., Boysen, N. y Pesch, E. (2017). Which items should be stored together? A basic
  partition problem to assign storage space in group-based storage systems. IISE Transactions
  49(1):13-30. DOI 10.1080/0740817X.2016.1213469 [V]
- Kubler, P., Glock, C. H. y Bauernhansl, T. (2020). A new iterative method for solving the
  joint dynamic storage location assignment, order batching and picker routing problem in
  manual picker-to-parts warehouses. Computers & Industrial Engineering 147:106645 [A]
- Larco, J. A., de Koster, R., Roodbergen, K. J. y Dul, J. (2017). Managing warehouse
  efficiency and worker discomfort through enhanced storage assignment decisions. IJPR
  55(21):6407-6422 [V]
- Lesch, V. et al. (2023). Optimizing storage assignment, order picking, and their interaction in
  mezzanine warehouses. Applied Intelligence 53(15):18605-18629.
  DOI 10.1007/s10489-022-04443-x [V]
- Liu, F. et al. (2024). Evolution of heuristics: towards efficient automatic algorithm design
  using large language model. ICML 2024, PMLR 235:32201-32223 [V]
- Londe, M. A., Pessoa, L. S., Andrade, C. E. y Resende, M. G. C. (2025). Biased random-key
  genetic algorithms: a review. EJOR 321(1):1-22. DOI 10.1016/j.ejor.2024.03.030 [V]
- Lorenz, Otto y Gendreau (2025). Picking operations in warehouses with dynamically arriving
  orders: how good is reoptimization? Networks 86:157-173. DOI 10.1002/net.22281 [A]
- Loske, D., Koreis, J. y Klumpp, M. (2022). IFAC-PapersOnLine 55(10):508-513 [A]
- Mahmoudinazlou, S., Sobhanan, A., Charkhgard, H., Eshragh, A. y Dunn, G. (2025). Deep
  reinforcement learning for dynamic order picking in warehouse operations. Computers &
  Operations Research 182:107112. DOI 10.1016/j.cor.2025.107112 [V, preprint]
- Mantel, R. J., Schuur, P. C. y Heragu, S. S. (2007). Order oriented slotting: a new assignment
  strategy for warehouses. EJIE 1(3):301-316 [A]
- Novikov, A. et al. (2025). AlphaEvolve: a coding agent for scientific and algorithmic
  discovery. arXiv 2506.13131, sin revision por pares [V]
- Rimele, A., Grangier, P., Gamache, M., Gendreau, M. y Rousseau, L.-M. (2021). E-commerce
  warehousing: learning a storage policy. arXiv 2101.08828 [V]
- Rimele, A., Grangier, P., Gamache, M., Gendreau, M. y Rousseau, L.-M. (2021). Supervised
  learning and tree search for real-time storage allocation in robotic mobile fulfillment
  systems. arXiv 2106.02450 [V]
- Romera-Paredes, B. et al. (2024). Mathematical discoveries from program search with large
  language models. Nature 625:468-475. DOI 10.1038/s41586-023-06924-6 [V]
- Schiffer, M., Boysen, N., Klein, P. S., Laporte, G. y Pavone, M. (2022). Optimal picking
  policies in e-commerce warehouses. Management Science 68(10):7497-7517.
  DOI 10.1287/mnsc.2021.4275 [V]
- Schlag, S. et al. (2022). High-quality hypergraph partitioning. ACM Journal of Experimental
  Algorithmics [A]
- Sim, K., Renau, Q. y Hart, E. (2025). Beyond the hype: benchmarking LLM-evolved heuristics for
  bin packing. EvoApplications 2025, LNCS, 386-402. DOI 10.1007/978-3-031-90065-5_24 [A]
- Tan, Z. y Mu, Y. (2024). Learning solution-aware transformers for efficiently solving quadratic
  assignment problem. ICML 2024, PMLR 235:47627-47648 [V]
- Teck, Pham, Rousseau y Vansteenwegen (2025). Deep reinforcement learning for the real-time
  inventory rack storage assignment and replenishment problem. EJOR 327(2):606-622.
  DOI 10.1016/j.ejor.2025.05.008 [A]
- Van Gils, T. et al. (2018). International Journal of Production Economics 197:243-261 [A]
- Webb, G. I. (2007). Discovering significant patterns. Machine Learning 68(1):1-33 [V]
- Weidinger, F. y Boysen, N. (2018). Scattered storage: how to distribute stock keeping units all
  around a mixed-shelves warehouse. Transportation Science 52(6):1412-1427.
  DOI 10.1287/trsc.2017.0779 [A]
- Yuan, R., Graves, S. C. y Cezik, T. (2019). Velocity-based storage assignment in semi-automated
  storage systems. Production and Operations Management 28(2):354-373.
  DOI 10.1111/poms.12925 [A]
