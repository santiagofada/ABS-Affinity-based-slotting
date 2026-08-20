# Pendiente: pasar la evaluacion de estatica a simulacion dinamica

Diagnostico previo a implementar. **Todavia no se toco codigo.** El documento registra el
estado actual, que permiten los datos, las decisiones de diseno que hay que tomar, el
impacto sobre el paquete, y por donde empezar.

Motivo: hoy el test es una evaluacion estatica y no considera los eventos de
reabastecimiento. Deberia ser una simulacion: train decide la asignacion inicial, y test
transcurre como el mundo real, con el deposito cambiando de estado.

Nota de alcance: este documento **no** trata el problema de la senal de afinidad. Son dos
cuestiones ortogonales; la de afinidad es un tema de los datos y se aborda por separado.

---

## 1. Que hace hoy el evaluador

En [evaluator.py:922-935](../src/abs_affinity_based_slotting/evaluation/evaluator.py#L922-L935):

```python
costs = [self._batch_cost(group[sku_col].unique(), assignment)
         for _, group in picking_test.groupby(batch_col, sort=False)]
```

Tres consecuencias:

- **El tiempo no existe.** Agrupa por batch y no ordena por timestamp (`sort=False`). Los
  400 batches de test se evaluan como conjunto, no como secuencia. El batch del dia 31 ve
  el mismo layout que el del dia 25.
- **La asignacion es inmutable durante todo el test.** Es el mismo objeto en las 400
  iteraciones.
- **Solo entra la geometria.** `units`, `quantity` y `replenishment_events` no participan
  de ningun calculo del paquete. Verificado: `units` aparece solo en la validacion de
  esquema, y `replenishment_events` solo en el loader.

Ademas hay un impedimento estructural: **`Assignment` no tiene operacion de mover.** Tiene
`swap(sku_a, sku_b)`, que intercambia dos SKUs ya ubicados. Una reubicacion es otra cosa:
sacar un SKU de su ubicacion, dejarla vacia, y ponerlo en un hueco libre. Hoy no se puede
expresar. `Assignment` tampoco conoce las ubicaciones vacias — su docstring dice
"Empty locations are not stored".

---

## 2. Que dan los datos

Del readme del dataset, la dinamica esta completamente especificada:

- Los replens son **reactivos**: se insertan justo antes de un pick que dejaria el stock
  negativo.
- **Recarga in situ** si el stock es mayor que 0 pero insuficiente: se rellena a capacidad
  en la misma ubicacion, `source_location_id == target_location_id`.
- **Reubicacion** si el stock es exactamente 0: con probabilidad 0,9 el SKU se muda a una
  **ubicacion vacia al azar** y se llena ahi; la vieja queda libre. Con probabilidad 0,1
  cae de nuevo a recarga in situ.

Faltante importante: **el dataset no modela area de reserva.** `source_location_id` es la
ubicacion anterior del propio SKU, no un pulmon de donde salen las unidades. El recorrido
del repositor **no es derivable del dato**: habria que suponerlo (por ejemplo dock hacia
destino y vuelta). Es un supuesto a declarar, no un hecho medible.

---

## 3. El nucleo: separar lo exogeno de lo endogeno

Para cada cosa que ocurre en el test, la pregunta es si depende del slotting.

| Que pasa | Depende del slotting |
|---|---|
| Que SKUs se piden y cuando | **No.** La demanda es exogena. |
| Cuanto stock queda de cada SKU en cada momento | **No.** Es stock inicial + repuesto - pickeado. |
| Cuando se dispara un replen | **No.** Depende solo del stock llegando a 0. |
| Que el replen sea recarga in situ o reubicacion | **No.** Depende de si el stock llego exactamente a 0, mas un dado. |
| Cuanto camina el picker en cada batch | **Si.** |
| **A que ubicacion va el SKU cuando se reubica** | **Si. Es la unica decision endogena.** |

Casi toda la dinamica es exogena al slotting. Lo unico endogeno es donde aterriza un SKU
reubicado. De ahi sale el diseno mas limpio:

> **Reproducir los eventos de reposicion tal cual estan en el dato** — momento, cantidad,
> y si son in situ o reubicacion — y **re-decidir unicamente el destino** de las
> reubicaciones segun la politica que se quiera estudiar.

Ventajas: no hay que inferir capacidades, ni reimplementar la politica del generador, ni
arriesgarse a que la simulacion diverja del dataset. Se toma del dato todo lo exogeno y se
decide solo lo que compete al metodo. Es fiel por construccion.

---

## 4. Decisiones de diseno pendientes

### D1. Politica de reubicacion (la decision central)

| Politica | Que modela | Que mide el experimento |
|---|---|---|
| **(a) Hueco vacio al azar** (replica lo que hace el dataset) | Deposito sin plan de slotting: el WMS pone donde hay lugar | **Cuanto se degrada** un slotting optimizado cuando la operacion no lo respeta |
| **(b) Volver a su lugar asignado** si esta libre; si no, el hueco libre mas cercano | WMS que conoce el plan y lo mantiene | Slotting **mas** politica de reposicion, evaluados juntos |
| **(c) Ubicacion dedicada**: el SKU nunca se mueve, siempre se recarga en su casa | Almacenamiento dedicado clasico | Nada nuevo: **la evaluacion estatica actual ya es correcta bajo este supuesto** |

Bajo (c) el evaluador de hoy no esta mal, esta **incompleto en su justificacion**: le falta
declarar el supuesto de almacenamiento dedicado.

**Recomendacion: implementar (a) y (b), y reportar ambas.** La comparacion entre las dos es
en si misma un resultado — cuantifica cuanto vale que la operacion respete el plan de
slotting. Hoy no existe ese numero.

### D2. El recorrido del repositor, ¿entra en el costo?

Si entra, el objetivo pasa a tener dos terminos de costo y hay que ponderarlos. Y como el
dataset no tiene area de reserva, hay que inventar de donde sale la mercaderia.

**Recomendacion: no por ahora.** Reportarlo aparte como metrica secundaria (numero de
reubicaciones, y distancia bajo el supuesto dock-destino-dock), fuera del objetivo. Meterlo
adentro suma arbitrariedad sin necesidad.

### D3. Estado inicial del test

Hoy `current` es la foto del dia 0 evaluada contra batches de los dias 25 a 31: esta
desactualizada. Con simulacion se resuelve solo — se reproducen los replens de train para
llegar al **estado real al momento del corte**, y de ahi arranca el test. El baseline
`current` pasa a ser el layout que efectivamente estaba en pie.

Pregunta derivada: el metodo optimizado, ¿arranca el test desde una re-slotting completa en
el corte? Eso implica mover 27.000 SKUs, con un costo que hoy nadie cuenta.
**Recomendacion: dejarlo fuera del costo pero declararlo**, que es la convencion en la
literatura de slotting estatico.

### D4. ¿Se re-estiman demanda y afinidad durante el test?

No. Se estiman una vez con train. Si no, deja de ser evaluacion out-of-sample.

---

## 5. Impacto sobre el codigo

El cambio es **aditivo y contenido en el lado de la evaluacion**. Nada de lo que produce
soluciones se toca.

**No cambia:**

- `methods/` — los metodos siguen produciendo una asignacion inicial. Intacto.
- `slotting/objective.py` — el objetivo es el surrogate de train. Intacto.
- `demand/`, `warehouse/`, `clustering/` — intactos.

**Cambia o se agrega:**

1. **`Assignment` necesita `move(sku, nueva_ubicacion)`**, ademas de `swap`, y necesita
   saber que ubicaciones estan libres. Hoy no puede expresar una reubicacion.
2. **Separar dos conceptos que hoy estan mezclados.** `Assignment` cumple dos roles a la
   vez: "la solucion que propone un metodo" y "el estado del deposito en el instante t".
   Conviene separarlos — la asignacion es la propuesta, el estado es lo que evoluciona. Si
   no, se confunde lo que se decidio con lo que paso.
3. **Subpaquete `simulation/`**, siguiendo la convencion de un subpaquete por concepto, con
   la politica de reubicacion como componente intercambiable y su propio registry, igual
   que afinidad, filtro, clustering y metodo. Encaja natural en la arquitectura existente.
4. **`evaluation/evaluator.py`**: pasar de "agrupar por batch" a "recorrer eventos en orden
   temporal". Es el cambio mas invasivo, pero `_batch_cost` (el calculo de la ruta de un
   batch) se reusa tal cual.
5. **`evaluation/metrics.py`**: agregar metricas de degradacion — distancia por batch a lo
   largo del tiempo y no solo el promedio, numero de reubicaciones, y fraccion de SKUs que
   ya no estan donde el metodo los puso.
6. **El invariante de cobertura sigue valiendo** y sigue siendo verificable.

Estimacion: no es trivial, pero alrededor del 80% del paquete queda igual.

---

## 6. Prediccion testeable, y por que esto vale la pena

Solo **2.522 SKUs** de 27.000 tuvieron replen. Son los de alta rotacion, exactamente los
que el greedy ubica pegados al dock. Cuando se quedan sin stock, la politica del dataset
los manda a **un hueco vacio al azar**, o sea lejos.

Es decir: **el layout optimizado se degrada mas rapido justo donde mas valia.** Con unas
215 reubicaciones por dia y 6 dias de test, son aproximadamente 1.290 reubicaciones,
concentradas en la cabeza de la distribucion de demanda.

Esa es la razon mas fuerte para hacer el cambio: no es solo mas honesto, es que
probablemente aparezca un fenomeno real y reportable. Y conecta con algo que la propuesta
de tesis ya planteaba y que hoy no se captura — el dinamismo, y la pregunta de cada cuanto
hay que re-slotear.

Lo que este cambio **no** hace: mejorar el rigor de la evaluacion no cambia el resultado
sobre la afinidad. Son problemas ortogonales.

---

## 7. Primer paso propuesto

Antes de escribir nada del simulador, **un solo experimento diagnostico en notebook**, que
no requiere ningun cambio de arquitectura:

> Reproducir los eventos de reposicion desde el dia 0 hasta el corte train/test, sobre el
> layout vigente, y evaluar `current` con el mapa SKU-ubicacion **real al momento del
> corte** en lugar de la foto del dia 0.

Contesta dos cosas de una: cuanto se movio el deposito en 25 dias, y si el baseline estaba
mal calibrado. Es barato y no compromete ninguna decision de diseno.

Con ese numero sobre la mesa se decide D1 con evidencia en vez de a priori.
