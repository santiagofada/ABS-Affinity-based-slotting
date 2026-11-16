# Contexto para escribir el capitulo 3, "El deposito y sus datos"

Este archivo es para la sesion que va a escribir el capitulo 3 de la tesis. Junta solo lo que hace
falta para ese capitulo: donde esta el esqueleto, de donde salen los numeros, que cambio desde que se
armo el esqueleto y como escribe Santiago. Los resultados de los metodos no van en este capitulo.

## 1. La tesis en pocas lineas

Tesis de Licenciatura en Matematica Aplicada (FAMAF, UNC) de Santiago Fada sobre *slotting*: decidir en
que ubicacion del deposito va cada producto (SKU) para que los operarios caminen menos al armar los
pedidos. Dos directores: Juan Bautista Cabral (FAMAF), que lee en Overleaf, y Mariano Ferrero (ShipHero),
que provee los datos y lee el PDF.

Capitulos: 1 introduccion (escrita salvo el parrafo que organiza los capitulos), 2 antecedentes (escrito y revisado por Juan), **3 el deposito y sus
datos (el que sigue)**, despues vienen la optimizacion, los resultados y las conclusiones.

## 2. Donde esta todo

| que | donde |
|---|---|
| esqueleto del capitulo | `escritos/05_deposito/deposito.tex`: ocho secciones, cada una con un `\completar{...}` que dice que va |
| numeros y datos de figuras | `escritos/05_deposito/datos/`: `resumen.json` (todos los numeros), `tamanos.csv`, `corte.csv`, `extracto.csv` (seis lineas reales) y `*.dat` para pgfplots (`plano`, `picks_bay`, `batch`, `nunca_mudadas`, `pareto`, `lift`) |
| de donde salen | `notebooks/data2/06_datos_medium.ipynb`, con una seccion por seccion del capitulo; escribe en `datos/` |
| terminos ya definidos | capitulo 2, `escritos/04_antecedentes/antecedentes.tex` (ver seccion 6 de este archivo) |
| notacion | `docs/modelo.md`; el capitulo 2 ya la usa |
| como funciona el simulador | `docs/manual.pdf` (capitulos de datos y de simulacion) |

## 3. Lo que cambio desde que se armo el esqueleto

El esqueleto y `datos/` son del 20 y 21 de octubre, con el corte viejo: **80% de los batches para
aprender y 20% para medir (36 dias de test)**. Desde el 27 de octubre el corte es **60/40: 108 dias de
train y 72 de test**. El cambio vino con la forma de simular: la simulacion parte del deposito real en
el corte y el plan entra de a poco, cada vez que un SKU se agota y se repone, asi que hacia falta un test
mas largo para ver esa transicion.

Afecta la seccion `sec:corte`: su `\completar` dice "ultimo 20 por ciento" y `corte.csv` tiene los
numeros viejos. Los nuevos (calculados para este resumen con la misma definicion del notebook; falta
regenerar `datos/` con `test_size=0.4`):

| | medium | medium-alpha-1.3 | big |
|---|---:|---:|---:|
| corte | 2026-04-19 14:24 | 2026-04-19 14:24 | 2026-04-19 14:24 |
| batches train / test | 4.887 / 3.258 | 4.887 / 3.258 | 10.860 / 7.240 |
| ordenes train / test | 122.175 / 81.450 | 122.175 / 81.450 | 271.500 / 181.000 |
| lineas train / test | 427.180 / 284.957 | 427.041 / 284.819 | 949.441 / 633.569 |
| dias train / test | 108 / 72 | 108 / 72 | 108 / 72 |
| reposiciones de test pasadas a train | 0 | 0 | 6 |
| lineas de train despues del corte | 0 | 0 | 92 |

Reglas del corte (`split_picking_events` y `split_replenishments`): los batches se ordenan por la hora
de su primera linea y el ultimo 40% va a test, asi que nunca se parte un batch ni una orden. Las
reposiciones se cortan por hora; si una ubicacion de train quedaria con stock negativo (las mudanzas se
registran despues del movimiento fisico), su primera reposicion de test pasa a train, hasta que todo
cierra. Las "lineas de train despues del corte" son lineas de batches que empezaron antes del corte y
terminaron despues.

Los numeros del perfil de actividad casi no cambian con 60% de train (en `medium`): el 20% mas pedido
explica el 76,3% de las lineas (antes 76,3%), 319 SKU explican el 50% (antes 318), 1.729 el 80% (antes
1.733), y por merchant el 80% de los picks lo hacen entre el 22,9% y el 29,0% de sus SKU (antes 23,5% a
29,0%). En `medium-alpha-1.3`: 227 SKU el 50% y el 20% mas pedido el 81,8%.

## 4. Hechos por seccion

Numeros de `medium` salvo que se diga otro deposito; fuente `resumen.json` salvo que se diga otra.

**Apertura y ShipHero (`sec:shiphero`).** Los datos no son un registro de operacion: los genero un
simulador de ShipHero, la empresa de Mariano. Lo que se sabe de como opera ShipHero esta en
`docs/lecturas-2026-10.md`, que resume las diapositivas de la charla de Mariano en FaMAF (mayo de 2025):
*smart batching* de hasta 25 ordenes con una orden por tote, *wave picking* y ruteo en S. Cada merchant
es un cliente que guarda sus productos en el deposito. Hay tres depositos (`small`, `medium`, `big`) y una variante
(`medium-alpha-1.3`, igual a `medium` con la demanda mas concentrada), seis meses cada uno (enero a junio
de 2026). Tamanos en `tamanos.csv`: pasillos 4 / 8 / 16, ubicaciones 1.920 / 7.680 / 27.648, SKU 1.728 /
6.912 / 24.883, merchants 4 / 50 / 100, ordenes 27.150 / 203.625 / 452.500, batches por dia 6 / 45 / 100.
Hubo una version anterior de los datos (v1) sin el numero de orden; la actual (v2) lo trae.

**El espacio (`sec:espacio`).** `medium`: 8 pasillos de 1.680 pulgadas (42,7 m), 16 bays por lado, 30
ubicaciones por bay, 2 pasillos transversales (en y = 756 y 1.356), dock en (0, -200); la ubicacion mas
lejana esta a 3.488 pulgadas del dock (88,6 m). Las distancias del proyecto estan en pulgadas. Figura del
plano: `plano.dat`.

**Productos, merchants y la asignacion inicial (`sec:productos`).** 6.912 SKU en 7.680 ubicaciones, una
SKU por ubicacion, 768 vacias (10%). Stock inicial de 4 a 122 unidades por ubicacion. Cada merchant tiene
entre 107 y 157 SKU y hace entre el 1,9% y el 2,1% de las ordenes. La asignacion inicial no tiene que ver
con la demanda: correlacion de Spearman entre picks y distancia al dock -0,012, cada pasillo recibe entre
el 11,9% y el 14,3% de los picks, coeficiente de variacion de picks por bay 0,51 (figura: `picks_bay.dat`).
Dato nuevo que lo confirma (notebook `correct_base/05_convergencia`, seccion 3): con la asignacion
inicial una orden toca en promedio 2,94 de los 8 pasillos, lo mismo que con un plan sorteado al azar
(2,93); en `big`, 3,22 contra 3,19 a 3,22.

**Ordenes y batches (`sec:ordenes`).** Cada orden tiene de 2 a 5 lineas, con la misma frecuencia (25%
cada una), y es de un solo merchant. Un batch son 25 ordenes consecutivas; sale uno cada 32 minutos en
`medium` (desvio 0,15 min; en `big` uno cada 14,4). Un batch tiene entre 63 y 106 SKU distintos (mediana
83) de entre 13 y 25 merchants (mediana 20), y dura entre 21 y 38 minutos (mediana 28,5); los tiempos
son sinteticos, unos 15 segundos por linea. El recorrido es en S estricto, confirmado por Mariano: el
operario recorre entero cada pasillo que tiene algo del batch, asi que la caminata depende solo de que
pasillos visita. Figura de un batch real: `batch.dat` (`BATCH-006520`: 89 lineas, 84 SKU, 76 bays, los 8
pasillos). Dato nuevo (notebook 05, seccion 3): con la asignacion inicial y los batches de los datos, el
100% de los batches de `medium` entra a los 8 pasillos y todos caminan lo mismo (17.824 pulgadas,
453 m); en `big`, el 94% entra a los 16.

**Reposiciones y mudanzas (`sec:reposiciones`).** 76.966 reposiciones en seis meses (428 por dia); el
44,9% son mudanzas, 192 por dia. La regla del generador: cuando llega stock y el SKU se habia agotado,
con probabilidad 0,9 se muda a una ubicacion libre al azar; si no, se repone donde estaba (es la
reposicion `random` del simulador). La cantidad que trae cada reposicion casi no crece con lo que se
pide el SKU (Spearman 0,19 entre la cantidad por evento y las lineas del SKU), asi que lo mas pedido se
agota y se muda mas: el 10% de SKU mas pedido hace el 64,3% de las lineas y el
65,9% de las mudanzas. Dato nuevo (notebook 05, seccion 4): por quintil de demanda, de menos a mas
pedido, cada SKU se repone en train 0,54, 1,13, 1,79, 3,6 y 25,8 veces. La reposicion llega en mediana
75 segundos antes del pick que la necesita. SKU que todavia no se mudaron nunca: 75,7% al 1 de febrero, 50,8% al
1 de abril y 31,8% al 30 de junio (figura: `nunca_mudadas.dat`).

**Que se usa para aprender y que para medir (`sec:corte`).** Ver la seccion 3 de este archivo.

**El perfil de actividad (`sec:perfil-deposito`).** Volumen plano (mediana de 27.539 lineas por semana
completa), ranking estable (los 50 SKU mas pedidos son los mismos en meses consecutivos; Spearman entre
meses de 0,76 a 0,77), lineas por orden uniformes por construccion. Concentracion: ver la seccion 3 de
este archivo (con 60% de train). Figura de Pareto: `pareto.dat`. El capitulo 2 ya presenta el perfil de
actividad en general (`sec:perfil`, `fig:perfil`); aca va el de estos datos.

**Lo que se pide junto (`sec:coocurrencia`).** Se compara la co-ocurrencia por orden de cada par de SKU
con la de una permutacion que conserva el tamano de las ordenes y la frecuencia de cada SKU dentro de su
merchant. Con pares que coinciden al menos 20 veces (6.179 pares), el lift va de 0,79 (percentil 5) a
1,34 (percentil 99), y con la permutacion de 0,78 a 1,33: la misma banda. Con al menos 5 coincidencias,
0,55 a 1,75 contra 0,55 a 1,78. Conclusion: no hay afinidad entre SKU mas alla de que una orden es de un
solo merchant. Figura: `lift.dat` (observado contra esperado). El lift ya esta definido en el capitulo 2
(`sec:afinidad`).

## 5. Lo que no va en este capitulo

Los resultados de los metodos (cuanto camina cada plan, el plan ganador, el techo, la comparacion con el
greedy y con un plan aleatorio) van en el capitulo de resultados. En este capitulo solo entran como
descripcion de los datos los dos hechos marcados como "dato nuevo", que muestran como es el deposito tal
como viene.

## 6. Como escribe Santiago

Lo que sigue lo fue pidiendo Santiago en la sesion que escribio los capitulos 1 y 2 (agosto a octubre).

**Como trabajar con el.**
- Una sola cosa a la vez: parrafo por parrafo, nunca una reescritura global ni todos los puntos juntos.
- Antes de tocar el texto, proponer el cambio literal, "cambio X por Y", con el por que, y esperar su
  aprobacion. El da el si en cada cambio; solo los que el marca como directos se hacen sin preguntar.
- No tomar sus sugerencias al pie de la letra: cuando da una frase de ejemplo, es la idea, no el texto
  a pegar.
- Cuando trabaja sobre comentarios del PDF, decir en que pagina se esta trabajando.
- Las marcas (`\completar`, `\corregir`, comentarios de Juan) no se sacan borrandolas: se resuelven.
- Si algo lo escribio Claude y hay que verificarlo, dejar `\completar{chequear ...}` (sin nombrar a
  Claude).
- Le sirve que un subagente valide una propuesta antes de mostrarla, o escribir con uno que redacta y
  otro que revisa contra estas preferencias.
- Figuras: generarlas primero en un PDF aparte, mirarlas despues de generarlas (detalles, colores,
  lineas que no cierran), y recien con su si insertarlas, leyendo el contexto para que el texto quede
  cohesivo.

**Estilo.**
- Prosa que se lea de corrido, como un hilo, con conectores. No arrancar parrafos con "frase corta.
  otra frase", no encadenar oraciones cortas, no usar dos puntos en la prosa. Tampoco un recorrido tipo
  checklist de lo que viene.
- Lenguaje simple y el suyo: nada de palabras complejas innecesarias. Referencia de estilo: la tesis de
  Felipe en `Extras/Tesisna_feets`, reconocida por su escritura.
- Claro y completo, pero sin verbosidad ni redundancia; si algo ya se dijo (por ejemplo, numeros de una
  tabla), no repetirlo.
- Rigor antes que una frase linda: nada de afirmaciones universales donde hay supuestos, tendencias
  presentadas como causas, conclusiones extrapoladas entre depositos distintos ni numeros que aparezcan
  de la nada. Lo que es una estimacion se presenta como tal.
- Bajar a tierra con un ejemplo numerico concreto cuando una idea es abstracta; explicar bien cada
  medida (nombre, formula, que mide), en lista si son varias.
- "Este trabajo...", no "Esta tesis se ubica..."; evitar frases fuertes como "esta en posicion de
  atacar". No decir "el libro" ni citar siempre el mismo (Bartholdi y Hackman).
- Introducciones de capitulo con un hilo que plantee algunas preguntas, no solo un resumen.
- Cuando se plantea un problema, siempre objetivo y restricciones, no la funcion sola. Nunca notacion con
  pi para permutaciones. No traducir *NP-hard*.
- Notacion: la del codigo y de `docs/modelo.md` ($i, j$ SKU; $l, k$ ubicaciones; $f_i$ picks; $c_l$
  costo de acceso; $d_{lk}$ distancia; $x_{il}$ asignacion; $a_{ij}$ afinidad).
- Cursiva solo en el termino en ingles (`\emph{pallet}`, `\emph{warehouse}`, `\emph{dock}`), no en la
  frase entera. Sin negritas en el cuerpo (lo pidio Juan). Terminos tecnicos con el glosario (`\gls`).
- Figuras y tablas: toda figura se referencia en el texto; captions cortos y genericos, que se entiendan
  si la figura se mueve a otra tesis, sin interpretacion del caso; en las tablas, numeros alineados a la
  derecha y texto a la izquierda; algo de color esta bien (como en el manual), pero sin llenar de cajas
  de colores. El capitulo 2 no tiene datos reales: este capitulo es el primero que los muestra.
- Los terminos se definen antes de usarse. El capitulo 2 ya define, con estos labels: operaciones y
  costos (`sec:operaciones`, `tab:costos-etapas`), geometrias (`fig:geometrias`), order picking y ruteo
  en S (`sec:picking`, `fig:ruteo-serpentina`), perfil de actividad (`sec:perfil`), dedicado o compartido
  y reglas de asignacion (`sec:slotting`), afinidad y lift (`sec:afinidad`), formulacion
  (`sec:formulacion`, `eq:qap`). Referenciarlos con `\ref` en lugar de volver a definir.
- Los `.tex` llevan tildes. Pendiente general: una oracion por linea, para que los merges con Overleaf
  no choquen.

**Macros.** `\completar{...}` lo pendiente (rojo); `\citeme{...}` una cita que falta; `\corregir[nota]{...}`
una correccion propuesta (verde); `\jbc{...}` comentarios de Juan; `\rev{...}` texto revisado (azul).

## 7. Flujo de trabajo

- `escritos/` es un subtree del proyecto de Overleaf. Antes de escribir, `make traer`; al terminar,
  `make mandar`. `make tesis` compila y copia el PDF a `docs/tesis.pdf`, que no se commitea (lo hace un
  GitHub Action).
- Nunca `git pull --rebase` en este repo.
- No commitear ni pushear sin que Santiago lo pida.
