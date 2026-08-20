# Estado del arte

Revision de la literatura relevante para este trabajo. No pretende ser exhaustiva: recoge
solo lo que condiciona alguna decision de modelado, de metodo o de evaluacion del
proyecto. Los numeros citados estan verificados contra la fuente.

---

## 1. Donde se ubica el problema

El problema de asignar productos a ubicaciones aparece en la literatura como **Storage
Location Assignment Problem (SLAP)**. Dentro de esa familia, la variante que me interesa
es la que usa la co-demanda entre productos, y se la llama **correlated storage assignment
problem (CSLAP)** o *affinity-based slotting*.

La terminologia no esta unificada, y las dos revisiones sistematicas del area lo senalan
como un problema en si mismo: conviven "storage allocation", "slotting", "space
allocation", "product allocation" e "item allocation" para lo mismo (Rojas Reyes et al.,
2019; Islam & Uddin, 2023). Uso SLAP para la familia y slotting para la operacion.

Rojas Reyes et al. (2019) clasifican 71 trabajos entre 2005 y 2017 e Islam & Uddin (2023)
clasifican 60 trabajos de CSLAP entre 1985 y 2022. De ambas revisiones tomo tres cosas:
la mayoria de los modelos son programas enteros NP-hard; los metodos de solucion se
agrupan en heuristicas, metaheuristicas y mineria de datos; y los metodos exactos, aunque
son los mas usados en la literatura, solo se aplican sobre instancias chicas.

## 2. La formulacion como QAP, y hasta donde llega

La forma natural de escribir el problema combina un termino lineal (ubicar los productos
frecuentes cerca del punto de despacho) con uno cuadratico (penalizar que dos productos
afines queden lejos). Eso es la forma de Koopmans-Beckmann del **Quadratic Assignment
Problem**.

Li, Moghaddam & Nof (2015) son el antecedente mas directo de mi funcion objetivo: plantean
explicitamente un QAP que combina afinidad entre productos con la clasificacion ABC, y lo
resuelven con un algoritmo genetico voraz. Su score de afinidad se arma a partir del lift y
del support count. Reportan mejoras de 7,14% a 104,48% en tiempo de picking.

El limite computacional esta bien establecido. Loiola et al. (2007), en el survey canonico
del QAP, son explicitos: *"instances of size n > 30 cannot be solved in reasonable time"*.
Con 27.000 productos y 30.000 ubicaciones, resolver el QAP global de forma exacta esta
fuera de discusion. Del mismo survey tomo la referencia para reportar calidad: QAPLIB como
biblioteca estandar de instancias, y la cota de Gilmore-Lawler como la cota inferior mas
tradicional. Ambas son utiles solo en escalas chicas, asi que en mi caso el gap contra el
optimo solo puede medirse sobre subinstancias.

## 3. Como se resuelve en la practica: el esquema de dos fases

Islam & Uddin (2023) identifican el patron dominante: *"The CSLAP is generally solved
through a two-phase construction heuristic algorithm. The first phase is to cluster SKUs
according to their correlation, and the second phase is to assign these correlated SKUs
near each other."*

Mi metodo bi-nivel es exactamente ese esquema, con dos diferencias: la primera fase la
planteo como un problema de transporte lineal que se resuelve exacto, y el agrupamiento no
sale de la afinidad sino de un criterio operativo (el vendor).

Mirzaei et al. (2021) critican precisamente la secuencialidad de ese esquema y proponen una
version integrada que alterna entre agrupar y asignar. Reportan que la version integrada
supera a la secuencial en un 13% promedio. Es una advertencia directa sobre mi diseno:
descomponer tiene un costo, y ese costo no esta cuantificado en mi caso.

## 4. Cuando la afinidad paga y cuando no

Esta es la parte que mas me sirve, porque mis experimentos dan que la afinidad no aporta
sobre un baseline por rotacion, y la literatura ya tiene identificadas las condiciones bajo
las cuales eso ocurre. Ninguna de las cuatro fuentes lo presenta como resultado principal,
pero las cuatro lo delimitan.

**El tamano de orden y el batching.** Mantel, Schuur & Heragu (2007) afirman que
*"extensive batching extinguishes the effect of a clever slotting strategy"* y agregan que
la zonificacion produce el mismo efecto. Conviene aclarar que esto aparece en la
introduccion como justificacion para asumir picking de una orden por vez: no lo testean.
Lo que si miden es consistente con la idea. En su Tabla 1, al pasar de ordenes de a lo sumo
2 items a ordenes de a lo sumo 10, la distancia relativa al optimo del heuristico
inteligente sube de 0,21% a 2,74%, mientras que la del asignador aleatorio baja de 15,24%
a 7,89%. La ventaja de ser inteligente se reduce a un tercio.

**El ruteo.** Xu & Ren (2020) trabajan sobre picker-to-parts con ruteo por traversal, que
es mi caso, y describen el mecanismo con precision: *"SKUs to be picked are almost
distributed in all picking aisles, and pickers need to transverse all aisles when the
average order size is larger; in this case, DSLA cannot reduce the number of aisles that
the picker needs to transverse."* Con orden promedio 20, el ahorro de distancia cae a 5,0%
(y el de tiempo a 0,08%, diluido por el tiempo de picking), frente a 10,48% con ordenes
chicas. Mi tamano de lote es de unos 76 productos distintos: casi cuatro veces el maximo
que ellos estudian.

**El sesgo de la curva de demanda.** Mirzaei et al. (2021) muestran que cuanto mas sesgada
es la curva ABC, menos aporta la afinidad, porque las politicas basadas en rotacion
aprovechan mejor esa concentracion. Con una curva 20/80 su politica integrada queda 6,5%
por debajo de la clasificacion ABC pura. Su Observacion 5 es directa: *"When the product
affinity is very low, the ICA policy has no clear benefits. In this case ABC is the best
policy."*

**La intensidad de la correlacion.** Zhang (2016) es la comparacion mas cercana a la mia:
picker-to-parts, deposito de un solo bloque, y baseline de full-turnover storage, que es
esencialmente mi `demand_greedy`. Su mejor estrategia correlacionada reduce la distancia
media por picking un **2,08%**. Y hay un detalle del diseno experimental que importa mucho:
sus ordenes se generan muestreando productos solo por probabilidad de picking, sin ninguna
estructura de correlacion plantada. Es decir, la afinidad que su metodo explota es
artefacto de popularidad, y con eso el techo es 2%. Su conclusion lo dice sin rodeos:
*"the picking frequency plays the most important role in the storage location
assignment."*

Del mismo trabajo tomo un segundo dato que reproduje sin saberlo: el almacenamiento por
clases ABC queda **10,28% peor** que full-turnover, porque dentro de cada clase almacena al
azar y rompe el ordenamiento fino por rotacion. Mi metodo bi-nivel por vendor queda 10,3%
peor que el greedy por demanda, por el mismo motivo.

**Una advertencia importante sobre la direccion del efecto.** Mirzaei et al. (2021)
trabajan sobre sistemas parts-to-picker (AS/R y robots moviles), donde el costo es cuantos
contenedores hay que traer y no cuanto se camina. Ahi el efecto del tamano de orden va al
reves: sus ahorros **crecen** con el tamano de orden. Cierran el paper senalando que el
efecto del batching sobre la afinidad queda abierto: *"Additional analysis may examine the
effect of batching or sequencing orders, which can increase the affinity in the orders
and, consequently, the effectiveness of the ICA policy."* Es decir, la literatura se
contradice sobre el signo de este efecto, y el tipo de sistema es lo que discrimina. Mi
trabajo es picker-to-parts, y debo declararlo explicitamente antes de generalizar nada.

## 5. Como se mide la afinidad

Todas las metricas usadas en el area se construyen sobre los mismos ingredientes: la
co-ocurrencia entre dos productos, el soporte individual de cada uno y el total de ordenes.
El indice de Jaccard es la eleccion mas frecuente, pero es una convencion, no una
derivacion: Amirhosseini y Sharp llegaron a definir seis medidas distintas de correlacion
(citados en Zhang, 2016).

Li, Moghaddam & Nof (2015) usan lift combinado con support count, y advierten sobre el
comportamiento del lift con soportes bajos, que es exactamente el regimen de la cola larga
de mi catalogo.

Dos limitaciones del estado del arte me resultan relevantes:

- **Todo es por pares.** Islam & Uddin (2023) lo marcan como hueco abierto: *"Several
  studies looked only at the relationship between two items. As a result, correlations
  between three or more items can be considered."* La via tecnica para eso son los itemsets
  frecuentes; Han et al. (2004) presentan FP-growth, que los extrae sin generacion de
  candidatos y resulta un orden de magnitud mas rapido que Apriori. Es la herramienta
  disponible si quisiera pasar de pares a tripletes.
- **Nadie contrasta la afinidad contra un modelo nulo.** En toda la literatura revisada la
  co-ocurrencia se calcula y se usa; no encontre ningun trabajo que verifique si el nivel
  observado excede lo que produciria el azar dados los soportes y los tamanos de canasta.

La afinidad tampoco tiene por que venir del historico de ordenes. Brynzer & Johansson
(1996) la derivan de la estructura del producto (la lista de materiales), y reportan una
reduccion de mas del 75% en la informacion que recibe el operario. Es una fuente de senal
que mi dataset no tiene, y explica por que en entornos de manufactura la co-demanda es
mucho mas nitida que en e-commerce.

## 6. Como genera datos la literatura

Como casi ningun trabajo tiene datos reales con estructura de correlacion conocida, la
practica habitual es generarla. Dos metodos concretos, ambos simples:

- Xu & Ren (2020): al generar una orden, despues de cada producto generan otro
  correlacionado segun un parametro de fuerza de correlacion, que barren entre 2% y 10% de
  productos correlacionados.
- Mirzaei et al. (2021): manipulan la probabilidad de pedir un producto correlacionado, y
  publican en su Tabla 3 la distribucion de scores de afinidad resultante para cinco
  niveles, de cero a muy alta. Sirve como calibracion.

Islam & Uddin (2023) marcan como debilidad general del area que *"very few researchers in
this sector go beyond creating a new solution and testing out their findings in a real-life
scenario or on actual data."*

## 7. Baselines, ruteo y evaluacion

- **Baselines.** Los tres que aparecen sistematicamente son almacenamiento aleatorio, por
  rotacion (full-turnover o COI) y por clases ABC. Mi `current` (el slotting vigente) y mi
  `demand_greedy` cubren el segundo y tercero de forma natural.
- **Ruteo.** Islam & Uddin (2023) confirman que el S-shape es la politica dominante en los
  estudios de CSLAP por su simplicidad. Mi orden serpenteante pertenece a esa familia, lo
  que hace comparables mis resultados.
- **Calidad de las heuristicas.** Mantel et al. (2007) reportan que su heuristico basado en
  QAP queda 2,14% por encima del optimo en promedio sobre 550 instancias chicas, y su
  regla de oro mas simple un 5,73%. Son las magnitudes de gap que se consideran aceptables
  en el area. Conviene aclarar que sus experimentos numericos son sobre un modulo vertical
  de bandejas, donde el termino de rotacion esta anulado por construccion; los numeros
  sirven como referencia de calidad de heuristicos QAP, no como comparacion entre rotacion
  y afinidad.

## 8. La dimension dinamica

El slotting estatico es el alcance clasico, pero los dos trabajos que incorporan el tiempo
llegan a conclusiones que me obligan a tomarlo en serio.

Xu & Ren (2020) reubican productos entre olas de picking y cuentan explicitamente el costo
de sacar y volver a colocar cada producto dentro del tiempo total del operario. Es el
modelo de costo que necesito si paso de evaluacion estatica a simulacion.

Mirzaei et al. (2021) senalan, sin cuantificarlo, que *"to use the cluster-based policy,
the replenishment process should be adjusted accordingly, which might take additional time
and effort"*, y dejan la asignacion dinamica como trabajo futuro.

Mi evaluacion actual es estatica y no considera los eventos de reposicion, lo que sobrestima
la ganancia de cualquier estrategia optimizada, porque el layout se degrada en el tiempo.

## 9. Donde se ubica este trabajo

De la revision quedan tres huecos que mi trabajo esta en posicion de atacar:

1. **El umbral.** Las condiciones bajo las cuales la afinidad deja de pagar estan
   documentadas de a una (tamano de orden, ruteo, sesgo de la demanda, intensidad de la
   correlacion), pero nadie las barrio conjuntamente, y la literatura se contradice sobre
   el signo del efecto del batching segun el tipo de sistema. Mirzaei et al. (2021) lo
   dejan escrito como trabajo futuro.
2. **La escala.** Los experimentos publicados van de 12 productos (Mantel et al., 2007) a
   300-500 (Mirzaei et al., 2021) y 1.000 (Zhang, 2016), con ordenes de 1 a 20 productos.
   Mi instancia tiene 27.000 productos y lotes de unos 76, un orden de magnitud mas alla en
   ambos ejes.
3. **La validacion de la senal.** Ningun trabajo verifica si la co-ocurrencia observada
   excede la que produciria el azar. Es una precondicion barata y no la exige nadie.

---

## Referencias

- Brynzer, H. & Johansson, M.I. (1996). Storage location assignment: Using the product
  structure to reduce order picking times. *International Journal of Production Economics*,
  46-47, 595-603.
- Guan, M. & Li, Z. (2018). Genetic algorithm for scattered storage assignment in Kiva
  mobile fulfillment system. *American Journal of Operations Research*, 8, 474-485.
- Han, J., Pei, J., Yin, Y. & Mao, R. (2004). Mining frequent patterns without candidate
  generation: A frequent-pattern tree approach. *Data Mining and Knowledge Discovery*, 8,
  53-87.
- Islam, S.Md. & Uddin, K.Md. (2023). Correlated storage assignment approach in warehouses:
  A systematic literature review. *Journal of Industrial Engineering and Management*,
  16(2), 294-318.
- Koopmans, T.C. & Beckmann, M. (1957). Assignment problems and the location of economic
  activities. *Econometrica*, 25(1), 53-76.
- Li, J., Moghaddam, M. & Nof, S.Y. (2015). Dynamic storage assignment with product
  affinity and ABC classification: a case study. *International Journal of Advanced
  Manufacturing Technology*, 84, 2179-2194.
- Loiola, E.M., de Abreu, N.M.M., Boaventura-Netto, P.O., Hahn, P. & Querido, T. (2007). A
  survey for the quadratic assignment problem. *European Journal of Operational Research*,
  176(2), 657-690.
- Mantel, R.J., Schuur, P.C. & Heragu, S.S. (2007). Order oriented slotting: a new
  assignment strategy for warehouses. *European Journal of Industrial Engineering*, 1(3),
  301-316.
- Mirzaei, M., Zaerpour, N. & de Koster, R. (2021). The impact of integrated cluster-based
  storage allocation on parts-to-picker warehouse performance. *Transportation Research
  Part E*, 146, 102207.
- Rojas Reyes, J.J., Solano-Charris, E.L. & Montoya-Torres, J.R. (2019). The storage
  location assignment problem: A literature review. *International Journal of Industrial
  Engineering Computations*, 10, 199-224.
- Xu, X. & Ren, C. (2020). Research on dynamic storage location assignment of picker-to-
  parts picking systems under traversing routing method. *Complexity*, 2020, 1621828.
- Zhang, Y. (2016). Correlated storage assignment strategy to reduce travel distance in
  order picking. *IFAC-PapersOnLine*, 49(2), 30-35.
