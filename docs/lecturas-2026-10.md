# Lecturas de octubre 2026 (material enviado por Mariano)

Origen: `data/Warehouse problems-20261012T123644Z-1-001.zip` (carpetas `Slotting_Storage allocation`,
`Picking (batching)/{papers,reviews}`, `indicador de esfuerzo`, `layout`) y `Picking in ShipHero.docx`,
que solo enlaza las diapositivas de la charla en FaMAF (mayo 2025) y un video. Las diapositivas dicen:
smart batching de hasta 25 ordenes con una orden por tote, wave picking de hasta 25 SKUs por tote sin
mezclar items, ruteo en S.

Lo que importa para la tesis esta en la seccion 1. Las secciones 2 y 3 son el resto del material,
resumido para tenerlo a mano.

## 1. Slotting con afinidad

### Kofler, Beham, Wagner, Affenzeller (2014). Affinity based slotting in warehouses with dynamic order patterns

- Extienden el SLAP a varios periodos (M-SLAP): costo total = picking + reacomodo + putaway, medido en
  cambios de pasillo, evaluado por simulacion. Lo que optimizan es un sustituto:
  `score = alpha * PF + beta * PA`, con `PF = sum_i orderRatio(i) * dist(loc(i), dock)` y
  `PA = sum_ij affinity(i,j) * dist(loc(i), loc(j))`. Con una ubicacion por SKU es nuestro
  `C = lam L + (1 - lam) Q`.
- Afinidad = fraccion de ordenes que contienen a ambos; popularidad = fraccion de ordenes que contienen
  al SKU. Fijan `beta = 1` y barren `alpha`; `alpha = 10` fue lo mejor. Reconocen que los terminos
  tienen escalas distintas.
- Algoritmos: COI (greedy por frecuencia), busqueda local first-improvement y recocido simulado con swaps,
  "sampling swap" (generar n swaps y aplicar el mejor), healing (50 swaps por periodo).
- Instancia real (12 pasillos, 5.832 pallets, 12.000 SKUs), una orden por picker, sin batching.
  Cambios de pasillo: random 9.878, afinidad sola 8.746, COI 218, PF 248, PF/PA 214. PF/PA contra COI en
  cinco periodos: -1,8%, -2,7%, +1,5%, -5,4%, -5,0%. El recocido sobre PF converge a COI.
- Lectura: con afinidad real y ordenes sueltas, la afinidad agrega 2 a 5% sobre el greedy por
  frecuencia. El greedy es el optimo del termino lineal; para ganarle hay que cambiar el objetivo, no el
  optimizador. Advierten que con ordenes grandes la afinidad puede no servir.

### Li, Moghaddam, Nof (2015). Dynamic storage assignment with product affinity and ABC classification

- Asignan productos nuevos a filas con capacidad; QAP con tres terminos: afinidad con lo ya ubicado en la
  fila, popularidad por clase de fila (indicador 100/50/20), afinidad entre nuevos en la misma fila.
  La "distancia" es un indicador de misma fila.
- `R_ij = L_ij * S_ij`, con `S_ij` soporte (ordenes con ambos) y `L_ij` el signo de `lift - 1`,
  `lift = P(i,j) / (P(i) P(j))`. Con lift 1 en todos los pares, `R = 0` y el metodo colapsa a ABC.
- GA con GRASP inicial y cruce que respeta capacidad. Instancias de 20 a 160 SKUs y 200 ordenes, tres
  de cuatro con correlacion inyectada. Ruteo en S saltando filas sin picks. Mejoras de 7% a 104% contra
  ABC con ubicacion aleatoria dentro de cada clase, medidas sobre una orden.
- Lectura: decidir a nivel pasillo con capacidad por pasillo es nuestro MIP de pasillos. Bajo
  independencia `a_ij` es proporcional a `f_i f_j`, y el termino de misma fila se vuelve
  `sum_a (masa de demanda del pasillo a)^2`: concentrar masa.

### Islam, Uddin (2023). Correlated storage assignment approach in warehouses: a systematic literature review

| Trabajo | Correlacion | Metodo | Ruteo | Mejora y baseline |
|---|---|---|---|---|
| Frazelle y Sharp 1989 | pares | heuristica 2 fases | n/d | "significativa" vs COI |
| Garfinkel 2005 | pedidos multi-zona | lagrangiano + cyclic exchange | zonas | 15% vs COI |
| Egas y Masel 2010 | clustering de SKUs | heuristica iterativa | pasillos visitados | 20 a 30% menos pasillos vs asignacion por demanda |
| Kovacs 2011 | estructura conocida | MIP class-based | return | 36 a 38% vs COI |
| Chuang et al. 2012 | support | CAPM 2 fases | z-type | 45% vs setup actual |
| Zhang 2016 | pares | CSAS | return | 2,08% vs full-turnover |
| Mirzaei et al. 2021 | afinidad + turnover | greedy + SA | parts-to-picker | 40% vs full-turnover |
| Trindade et al. 2022 | similitud + peso | heuristica 2 fases | S-shape | hasta 15% |

- Casi todo es pick-by-order; ninguno de los 60 trabajos describe batches de 25 ordenes. Bajo S solo
  Trindade 2022 da un numero. Los que particionan SKUs a pasillos o zonas: Egas y Masel 2010 (objetivo =
  pasillos visitados), Xiao y Zheng 2012, Kress, Boysen y Pesch 2017 (SKU partitioning), Mirzaei 2022.
- Cuando la correlacion no ayuda: Hua y Zhou 2008 ("solo si existen clusters naturales"), Xin 2019 (con
  correlacion debil agrupan por clases primero), Zhang 2016 (2% apenas). Nadie compara contra un greedy
  por demanda bien hecho, salvo Egas y Masel.

### Waubert de Puiseau et al. (2022). Dynamic storage location assignment using deep reinforcement learning

- Pallets, tres zonas con costo 1/2/10, PPO con mascara asigna cada pallet que entra. Datos reales,
  12.100 operaciones de 500 articulos. Costo total: regla por cuantiles de estadia 35,99, PPO 37,78, ABC
  manual 40,34, random 45,43. PPO gana 6% al ABC y pierde contra una regla ajustada a los datos.
- Lectura: una regla de clases ajustada es un techo duro; lo que supera al ABC es informacion que el ABC
  no usa (estacionalidad, reingresos), no afinidad.

## 2. Batching y ruteo

- **Valle, Beasley, da Cunha (2017).** Batching y ruteo conjunto exacto por branch-and-cut. No dan
  formulas de S-shape: usan las heuristicas de Roodbergen y de Koster como caja negra. Brecha entre la
  mejor de cuatro heuristicas y el ruteo optimo: 2,4% en promedio, menor con pedidos grandes. La variante
  sin reversa (atravesar entero cada subpasillo, saltando los vacios) es 7,5% mas larga que el optimo.
  Util: el corte de pasillo (todo pedido con items a ambos lados de un corte paga el cruce) como
  desigualdad valida para el MIP de pasillos.
- **Yang, Zhao, Guo (2020).** Batching con SKUs en varias posiciones. La regla LSA3 (cubrir el lote con
  la menor cantidad de pasillos: tomar el pasillo con mas SKUs del lote y repetir) es la de mejor
  costo-beneficio; gana 45% a la seleccion aleatoria. No comparan sistemas de almacenamiento.
- **Deng et al. (2025).** Batching con correlacion bajo scattered storage, afinidad sintetica. Su
  similitud por pasillos compartidos (NBS) gana a la correlacion de productos cuando el slotting se
  conoce: -26% en instancias grandes. Validan que el sustituto de correlacion ordena los algoritmos
  igual que la ruta real.
- **Schleyer y Gue (2012).** Distribucion del tiempo de ciclo con batching de n lineas y S-shape bajo
  almacenamiento aleatorio. Pasillos entrados x: problema de ocupacion; con probabilidad `p_a` por
  pasillo, `E[pasillos] = sum_a [1 - (1 - p_a)^n]`. Es la formula del costo de slotting bajo S.
- **Suppini et al. (2024).** 1.260 configuraciones simuladas: la asignacion por rotacion es la variable
  que mas pesa en el tiempo de picking, y con demanda concentrada el batching pierde ventaja frente al
  picking por orden.
- **Zayat et al. (2026)** (robustez de items), **Lorenz, Otto, Gendreau (2024)** (reoptimizacion con
  ordenes dinamicas, ratio 1,05 con mas de 13 ordenes), **Coruzzolo et al. (2023)** (batching con fechas
  de carga, -57% de tiempo), **Ene y Ozturk (2012)** (slotting lineal por clases mas GA de batching, sin
  baseline): sin aporte directo al slotting. **Leung 2020**, **Ardjmand 2018**, **Won y Olafsson 2005**:
  irrelevantes.

## 3. Indicador de esfuerzo

- **Grosse, Glock, Neumann (2016).** Revision de 186 articulos: la literatura esta dominada por
  eficiencia; los cruces slotting-ergonomia son golden zone, peso como restriccion y el bi-objetivo de
  Battini 2016. Fuente para justificar un termino ergonomico, sin formulas.
- **Keshvarparast et al. (2025).** Indice postural REBA por nivel de estante (10, 7, 5, 8 de abajo hacia
  arriba) como cota en un MINLP de picking colaborativo; XGBoost extrae reglas: frecuentes cerca de la
  descarga y en niveles accesibles.
- **Torrealba-Gonzalez et al. (2026).** Ruteo que minimiza incomodidad acumulada (sube con cada pick
  segun peso, altura y embalaje, baja al caminar): -44% de incomodidad con +4% de tiempo.

## 4. Que se desprende para la tesis

1. Con afinidad real la afinidad vale 2 a 5% sobre el greedy (Kofler); con batches de 60 a 90 SKUs y
   datos independientes, menos. El termino cuadratico no es de donde va a salir la ganancia.
2. Bajo S el costo es pasillos entrados por batch (Yang, Schleyer y Gue, Li). Con lineas
   independientes su esperanza es `sum_a [1 - (1 - F_a)^N]` con `F_a` la masa de demanda del pasillo:
   una funcion concava de la masa, que se minimiza concentrando los populares en pocos pasillos.
   El greedy por distancia al dock hace lo contrario: reparte los populares por el frente de todos.
3. El metodo justificado por la literatura es asignar SKUs a pasillos (particionamiento con capacidad)
   con ese objetivo, evaluado por simulacion de los batches, y refinado con busqueda local por swaps.
