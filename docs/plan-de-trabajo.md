# Plan de trabajo

Que esta hecho, que falta, en que orden y en que plazos. Los plazos asumen **1 hora por
dia** de dedicacion, unas 30 horas por mes.

---

## 1. El problema, en una linea

En un deposito lo que mas cuesta al armar un pedido es el operario caminando. Donde se
ubica cada producto determina esos recorridos. El trabajo propone un metodo que decide esas
ubicaciones combinando dos criterios: poner cerca de la salida lo que mas se pide, y poner
cerca entre si lo que se pide junto.

## 2. Que esta hecho

- **Pipeline completo** (unas 2.900 lineas): lectura y validacion de datos, separacion en
  un periodo para aprender y otro posterior para medir, calculo de frecuencia de pedido y
  de co-demanda entre productos, geometria del deposito, y el problema armado como un
  objeto unico y validado.
- **Seis metodos** de resolucion, todos intercambiables por nombre: asignacion vigente,
  asignacion por frecuencia, solucion exacta del caso sin afinidad, busqueda por
  intercambios, metodo en dos etapas, y resolvedor exacto para instancias chicas.
- **Tres formas de medir la afinidad** (co-ocurrencia, Jaccard, coseno), **tres filtros**
  para quedarse con los vinculos fuertes, y **dos criterios de agrupamiento** (proveedor,
  rotacion).
- **Evaluador** que simula el recorrido de cada pedido del periodo de prueba y reporta la
  distancia caminada.
- **Resultado preliminar:** ubicar los productos mas pedidos cerca de la salida reduce la
  distancia por pedido un 50% frente a la asignacion vigente. Ninguna variante que use
  afinidad mejora ese numero con los datos actuales.
- **Documentacion:** formulacion matematica, flujo de datos, catalogo de componentes,
  decisiones de diseno con sus alternativas descartadas, y revision de la literatura.

## 3. El obstaculo con los datos

Los datos no traen identificador de orden. La co-demanda se mide entonces sobre lotes de
unos 76 productos, que son muchas ordenes mezcladas, y la senal se diluye. Ademas, con
lotes de ese tamano el operario recorre casi todo el deposito de todas formas, asi que
acercar dos productos entre si casi no ahorra distancia.

Mientras el termino de afinidad no pese, cualquier metodo que lo optimice va a empatar con
el metodo simple: no se estaria midiendo el metodo sino el ruido. El pedido esta hecho, y
con el identificador de orden se resuelve tambien el segundo problema **sin pedir nada
mas**, porque los lotes se pueden armar por cuenta propia del tamano que se quiera. Como
agrupar ordenes en lotes es una decision del deposito, estudiar como interactua con la
decision de ubicacion es parte del aporte.

**Ninguna etapa de este plan queda bloqueada esperando los datos.** El trabajo de metodos y
de simulacion avanza igual; lo que cambia al recibirlos es la calidad de la evaluacion, no
lo que hay que construir.

---

## 4. Etapas

### E0 — Escritura · transversal ·

No es una etapa final: acompana a todas las demas. Cada capitulo se escribe cuando su
material esta disponible. Es aproximadamente la tercera parte del esfuerzo total.

### E1 — Metodos · 100 h · **el aporte central**

Todo lo de abajo es una extension concreta de codigo que ya existe, no un desarrollo desde
cero.

| | Tarea | h | |
|---|---|---:|---|
| 1.1 | **Corregir la vecindad de la busqueda por intercambios.** En `local_search.py` el candidato se toma como el ocupante de la ubicacion de un vecino afin, que por construccion es ese mismo vecino. La busqueda solo prueba intercambiar un producto con sus afines directos, y no con los ocupantes de las ubicaciones vecinas a ellos, que es lo que se queria | 12 | nucleo |
| 1.2 | **Agregar el movimiento a hueco libre.** Hay 3.000 ubicaciones vacias y ningun metodo las usa: la solucion solo sabe intercambiar dos productos ya ubicados, no mover uno a un hueco. Es un movimiento nuevo para la busqueda local | 10 | nucleo |
| 1.3 | **Agrupar por afinidad con deteccion de comunidades.** Hoy solo se agrupa por proveedor o por rotacion. El intento con componentes conexas colapsa en un grupo de 15.500 productos mas miles de aislados; deteccion de comunidades sobre el grafo de afinidad filtrado es la herramienta correcta | 15 | nucleo |
| 1.4 | **Usar la afinidad entre grupos en la primera etapa.** El codigo ya la calcula y la descarta. Incorporarla convierte la primera etapa en un problema de unos 10 grupos, resoluble exacto con el solver que ya esta integrado | 12 | nucleo |
| 1.5 | **Completar las metricas de afinidad**: lift y PMI normalizada, ya documentadas como candidatas en el codigo. PMI normalizada es la indicada para la cola larga del catalogo, donde lift es inestable | 6 | nucleo |
| 1.6 | **Politica para las ubicaciones sobrantes.** Hoy los 3.000 huecos libres quedan simplemente en las posiciones mas caras, sin criterio | 8 | nucleo |
| 1.7 | **Harness de experimentos**: un punto unico que recorra los metodos registrados, evalue y tabule. Hoy cada notebook rearma el pipeline a mano | 7 | nucleo |
| 1.8 | **Recocido simulado** sobre la vecindad de 1.1 y 1.2: aceptar movimientos que empeoran con cierta probabilidad. Es un agregado chico sobre la busqueda existente, no un metodo nuevo | 10 | opcional |
| 1.9 | **Version integrada del metodo en dos etapas**: alternar entre agrupar y asignar, en vez de agrupar una sola vez. La literatura reporta que integrar rinde alrededor de 13% mas que la version secuencial | 20 | opcional |

Nucleo 70 h, opcionales 30 h.

### E2 — Simulacion: arreglar la evaluacion · 40 h

Hoy se mide como si el deposito no cambiara. En la realidad si cambia: cuando un producto se
queda sin stock se repone, y a veces se lo muda de hueco. Los eventos de reposicion se leen
y no se usan. Diagnostico completo en `pending/simulacion-dinamica.md`.

| | Tarea | h |
|---|---|---:|
| 2.1 | Decidir que hace la simulacion cuando un producto se muda: a un hueco libre cualquiera, o de vuelta a su lugar asignado. Comparar las dos es en si un resultado | 4 |
| 2.2 | Separar dos cosas hoy mezcladas: la asignacion que propone el metodo y el estado del deposito que va cambiando. Reutiliza el movimiento de 1.2 | 10 |
| 2.3 | El simulador: recorrer los eventos en orden temporal, tomando del dato todo lo que no depende de la ubicacion y decidiendo solo el destino de las mudanzas | 18 |
| 2.4 | Metricas de degradacion: cuanto se deteriora una asignacion optimizada con el tiempo, y no solo el promedio | 8 |

Depende de 1.2 y necesita los metodos de E1 para tener algo que simular.

### E3 — Pendientes · 30 h

Cosas que quedaron en el tintero y conviene cerrar antes de la evaluacion final.

| | Tarea | h |
|---|---|---:|
| 3.1 | Recalcular la asignacion vigente al momento del corte, en vez de usar la foto del dia cero. Hoy se compara contra un layout que ya no estaba en pie durante el periodo de prueba | 8 |
| 3.2 | Ruteo en S estricto en vez del serpenteante simple, y verificar que las conclusiones no dependan de la politica de ruteo | 10 |
| 3.3 | Medir cuanto correlaciona bajar la funcion de costo con bajar la distancia real. En un experimento la funcion bajo y la distancia subio; conviene cuantificar esa brecha | 12 |

### E4 — Evaluacion sistematica · 60 h

| | Tarea | h |
|---|---|---:|
| 4.1 | Correr todos los metodos sobre todos los escenarios, incluyendo el barrido de tamano de lote una vez que haya identificador de orden | 18 |
| 4.2 | Sensibilidad a cada bloque: forma de medir la afinidad, filtro, agrupamiento, peso entre los dos criterios | 12 |
| 4.3 | Distancia al optimo exacto en instancias chicas, para poder decir que tan lejos esta la heuristica | 12 |
| 4.4 | Intervalos de confianza, para distinguir diferencias reales de ruido | 8 |
| 4.5 | Validacion con varios cortes temporales, no uno solo | 10 |

**Total sin escritura: 230 h. Con escritura: 420 h.**

---

## 5. De donde salen las 80 paginas

El peso esta en el capitulo de metodos y en el de resultados, que es donde va el trabajo
propio. La columna de la derecha aclara el estado real del material, para no sobreestimar.

| Capitulo | Pag. | Estado real |
|---|---:|---|
| 1. Introduccion y contexto | 7 | hay que escribirlo; la propuesta aporta el planteo, no el texto |
| 2. Estado del arte | 10 | hay una revision de unas 4 paginas que sirve de esqueleto y de bibliografia |
| 3. Formulacion del problema | 10 | hay una formulacion de unas 2 paginas; faltan derivaciones y analisis de escala |
| 4. Datos y metodologia de evaluacion | 10 | exploracion y evaluador hechos, texto inexistente. Depende de E2 |
| **5. Metodos propuestos** | **24** | **el capitulo mas largo. Seis metodos hechos, faltan las variantes de E1** |
| 6. Experimentos y resultados | 16 | primeros resultados; el resto depende de E4 |
| 7. Conclusiones y trabajo futuro | 5 | depende de todo |
| **Total** | **82** | |

Nada de lo documentado hoy es texto de tesis: son documentos tecnicos densos y cortos que
sirven de punto de partida, no de borrador. De ahi que la escritura pese la mitad del
esfuerzo.

---

## 6. Cronograma

420 horas a 1 hora por dia son unos **12 meses**. Cada columna es un periodo de dos meses,
unas 60 horas.

| Etapa | Ago 26 | Sep | Oct | Nov | Dic | En |
|---|:-:|:-:|:-:|:-:|:-:|:-:|
| E1 Metodos (nucleo) | X | X | | | | |
| E1 Metodos (opcionales) | | X | | | | |
| E2 Simulacion |X| X| X | | | |
| E3 Pendientes | | | | X | | |
| E4 Evaluacion sistematica | | | | | X | |
| E0 Escritura | cap. 3 | cap. 5 (1) | cap. 4 | cap. 5 (2) | cap. 6 | cap. 1, 2, 7 |

**Notas.**

- El orden de las etapas de codigo es una cadena: los metodos primero, porque son el aporte
  y porque la simulacion necesita algo que simular; despues la simulacion; despues los
  pendientes; la evaluacion sistematica al final, cuando ya no cambia lo que se evalua.
- La escritura arranca en el primer periodo y no para. El capitulo de metodos se escribe en
  dos tramos, siguiendo a E1.
- **A 2 horas por dia el plan cierra en unos 6 meses**, alrededor de marzo de 2027. Conviene
  definirlo con la direccion, porque mueve la fecha de entrega a la mitad.
- Si hay que recortar, en este orden: 1.9 (version integrada), 1.8 (recocido simulado),
  3.2 (ruteo en S), 4.5 (varias ventanas temporales).

---

## 7. Riesgos

| Riesgo | Que pasa | Como se maneja |
|---|---|---|
| No se puede exponer el identificador de orden | La afinidad sigue diluida y las mejoras de E1 no se ven en la evaluacion | Se reporta a nivel lote y se documenta la limitacion; el trabajo pasa a caracterizar bajo que condiciones el enfoque no rinde, que es un hueco identificado en la literatura |
| Aun con datos a nivel orden, ningun metodo supera al simple | Se debilita la hipotesis central | Es un resultado reportable, no un fracaso, siempre que este bien medido |
| El resolvedor exacto no escala ni en instancias chicas | No hay vara de calidad absoluta | Se reporta distancia relativa entre metodos y se cita el limite conocido de resolucion exacta |
| La escritura se atrasa respecto del codigo | Llegar al final con resultados y sin documento | El cronograma asigna un capitulo por periodo desde el inicio |
| La dedicacion real es menor a 1 h/dia | El calendario se estira | Se recorta por el orden indicado arriba |

## 8. Alcance

Los datos son simulados, aunque generados a partir de un deposito real. La tesis no afirma
validacion en produccion: mide sobre escenarios simulados con separacion estricta entre el
periodo de aprendizaje y el de evaluacion. La generalizacion se sostiene sobre el rango de
escenarios probados, y ampliarlo es el motivo del pedido de mas historia o de otros
depositos.
