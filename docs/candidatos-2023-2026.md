# Candidatos 2023-2026 para el estado del arte

Busqueda hecha el 2026-09-06 para la seccion 2.9 de la tesis. Metadatos verificados
contra Crossref, OpenAlex, Semantic Scholar, RePEc e IDEAS; lo que no pudo confirmarse
esta marcado como "no verificado". Ninguno esta todavia en `escritos/tesis.bib`: se
agregan solo los que Santiago decida usar.

## Tabla

| # | Autores, ano, titulo, revista, DOI | Sistema | Senal de afinidad | Metodo | Datos / baseline / mejora (segun abstract) | Batching / ruteo / tamano de orden |
|---|---|---|---|---|---|---|
| 1 | Islam & Uddin (2024). *An efficient correlation-based storage location assignment heuristic for multi-block multi-aisle warehouses*. Int. J. Industrial Engineering and Management 15(2):125-139. DOI 10.24867/ijiem-2024-2-352 | Picker-to-parts manual, multi-bloque multi-pasillo | Co-ocurrencia (no verificado en el texto) | Heuristica en dos fases: agrupar SKU por pasillo, luego asignar grupos con correlacion intra e inter grupo | Simulacion en varias configuraciones; comparacion con tecnicas establecidas; cifra no verificada | Ruteo y batching no verificados |
| 2 | Benaglia, Chen, Lu, Tsai, Hung (2024). *Improving the picking efficiency of a cold warehouse to avoid temperature abuse*. Int. J. Logistics Management 35(5):1434-1464. DOI 10.1108/IJLM-01-2023-0044 | Deposito frio con staging; picker-to-parts no explicitado | Reglas de asociacion sobre ventas + ABC | Simulacion de 8 estrategias de asignacion | Base simulada a partir de ordenes reales; baseline aleatorio; hasta 8% menos tiempo de picking y 22% menos espera en staging | Si: ruteo, zonificacion y batching |
| 3 | Debold (2025). *A storage assignment approach considering SKU repetitions in sequential zone picking*. Computers & Industrial Engineering. DOI 10.1016/j.cie.2025.111482 | Picker-to-parts con zone picking secuencial | Co-ocurrencia en el archivo de ordenes | Modelo binario + heuristica de tres etapas con VNS | Datos reales (HelloFresh); supera benchmarks hasta 19,5% | Anticipa el ruteo; batching no verificado |
| 4 | Zhuang, Zhou, Hassini, Yuan, Hu (2024). *Improving order picking efficiency through storage assignment optimization in robotic mobile fulfillment systems*. EJOR 316(2):718-732. DOI 10.1016/j.ejor.2024.02.025 | RMFS (parts-to-picker) | Afinidad + frecuencia | ILP (minimiza movimientos de racks) + heuristica | Optimos en instancias chicas y heuristicas en dataset real de e-commerce; mejora sin cifra | Secuenciamiento de ordenes y racks; batching no verificado |
| 5 | Zhang, Tian, Zhou (2024). *Joint optimization of item and pod storage assignment problems with picking aisles' workload balance in RMFS*. Complexity. DOI 10.1155/2024/9260431 | RMFS | Correlacion item-pod; medida no verificada | MIP + GA mejorado | Baselines Gurobi y heuristicas de dos etapas; datos no verificados | Balance de carga por pasillo |
| 6 | Chen & Li (2024). *Storage location assignment for improving human-robot collaborative order-picking efficiency in RMFS*. Sustainability 16(5):1742. DOI 10.3390/su16051742 | RMFS | Productos correlacionados a pods; medida no verificada | Heuristica en dos etapas | Baselines class-based y aleatorio; mejora cualitativa | No |
| 7 | Liu, Lu, Ren, Chen, Xu, Zhao (2025). *Joint optimization of storage assignment and order batching in RMFS with dynamic storage depth and surplus items*. Computers & Industrial Engineering 200:110767. DOI 10.1016/j.cie.2024.110767 | RMFS | No verificada | Greedy + VNS + SA en dos etapas | Conjunto supera a separado en 11,46% (snippet; abstract no accesible) | Batching si |
| 8 | Lu, Wang, Bi (2025). *A novel storage location allocation strategy for intelligent e-commerce warehouse with new products*. Int. J. Systems Science: Operations & Logistics 12(1). DOI 10.1080/23302674.2025.2549438 | RMFS e-commerce | Similitud por categoria (K-means) + correlacion | Metaheuristica (mayfly) | Datos reales de un deposito en China; supera enfoques existentes, sin cifra | No |
| 9 | Wu (2026). *Item storage reassignment problem in RMFS under customer order characteristic fluctuations*. J. Operational Research Society. DOI 10.1080/01605682.2026.2616411 | RMFS | No verificada | Heuristica (Interchange-Guided Sequencing) | No verificados | No |
| 10 | Yuan, Zhao, Wu, Cheng (2025). *Order picking efficiency: a scattered storage and clustered allocation strategy in automated drug dispensing systems*. Expert Systems with Applications. DOI 10.1016/j.eswa.2025.128264 | Dispensado automatico (parts-to-picker) | Frecuencia + correlacion | Programacion matematica en dos etapas + heuristica alternante | No verificados; minimiza maquinas visitadas | Coordina picking entre ordenes |
| 11 | Gamez Alban, Cornelissens, Sorensen (2024). *A new policy for scattered storage assignment to minimize picking travel distances*. EJOR 315(3):1006-1020. DOI 10.1016/j.ejor.2024.01.013 | Picker-to-parts, scattered storage | Proximidad intra-orden (co-ocurrencia implicita) | Metaheuristica VNS | Hasta 36% menos distancia vs scatter aleatorio y 56% vs politica por volumen; datos no verificados | Multiples puntos de deposito; sensibilidad al tamano de orden |
| 12 | Chen, Yang, Yu (2026). *Integrated scattered storage and picker routing in picker-to-parts warehouses*. EJOR 329(3):808-824. DOI 10.1016/j.ejor.2025.08.018 | Picker-to-parts e-commerce, scattered | Implicita en el conjunto de ordenes | MIP + busqueda adaptativa | ~14% menos costo vs practica estandar; datos no verificados | Ruteo si: return, S-shape, midpoint |
| 13 | Prunet, Absi, Cattaruzza (2025). *The storage location assignment and picker routing problem: a generic branch-cut-and-price algorithm*. EJOR 327(3):857-874. DOI 10.1016/j.ejor.2025.05.041 | Picker-to-parts | Implicita (SLAP + PRP integrado) | Exacto (branch-cut-and-price) | Instancias medianas; supera estado del arte | Ruteo optimo; varias politicas y layouts |
| 14 | Deng, Jiang, Wang, Xu (2025). *Optimizing order batching and picking problems considering the correlation between products under the scattered storage mode*. Sustainability 17(4):1646. DOI 10.3390/su17041646 | Centro B2C, scattered (picker-to-parts implicito) | Correlacion entre productos, para batching y no para slotting | 0-1 IP + semillas + tabu | Supera algoritmos de batching existentes | Batching si |
| 15 | Zhang, Wang, Lai, Shao, Zhao (2026). *An attention-based learning approach for joint optimization of storage selection and order picking paths in mobile shelving systems*. Mathematics 14(3):559. DOI 10.3390/math14030559 | Estanterias moviles (tipo RMFS) | Itemsets frecuentes (Apriori) | ML (atencion) + ALNS | Supera metodos existentes, sin cifra | Ruteo si |
| 16 | Pawar, Rao, Adil (2024). *Improving order-picking performance in e-commerce warehouses through entropy-based hierarchical scattering*. Sustainability 16(14):5953. DOI no verificado | Picker-to-parts e-commerce, scattered | Patron de demanda; afinidad no verificada | Heuristica + simulacion | Reduce esfuerzo de picking, sin cifra | No verificado |

## Descartados o marginales

- Ho et al. (2025, ESWA 272:126812): pronostico de demanda para asignacion, sin afinidad.
- Thairach et al. (2025, Int. J. Sustainable Engineering): diseno experimental de picking manual, sin reglas de asociacion.
- Zarinchang et al. (2023, J. Industrial and Production Engineering 41:40-59): metaheuristicas sin senal de afinidad.
- Gorbe & Bodis (2025, JIPD 9(2)): GA con agrupamiento de items, no es revision.

## Revisiones posteriores a Islam & Uddin (2023)

- Medrano-Zarazua, Saucedo-Martinez, Bolanos-Zuniga (2023). *Storage location assignment problem in a warehouse: a literature review*. Capitulo Springer, pp. 15-37. DOI 10.1007/978-3-031-34750-4_2.
- Casella, Volpi, Montanari, Tebaldi, Bottani (2023). *Trends in order picking: a 2007-2022 review of the literature*. Production & Manufacturing Research. DOI 10.1080/21693277.2023.2191115. 269 papers; storage assignment como una categoria.
- Boysen & de Koster (2025). *50 years of warehousing research: an operations research perspective*. EJOR 320(3):449-464. DOI 10.1016/j.ejor.2024.03.026.
- Chan, Ronnqvist, Lehoux (2023). *Trends and new practical applications for warehouse allocation and layout design*. SN Applied Sciences. DOI 10.1007/s42452-023-05608-0.
- No aparecio una revision especifica del CSLAP posterior a Islam & Uddin.

## Relevancia para la tesis

Los mas cercanos al caso de la tesis, manual picker-to-parts de e-commerce con ~27.000
SKU, son Islam & Uddin (2024), continuacion directa de la revision y el unico que resuelve
slotting por co-ocurrencia con heuristica en layout multi-bloque manual, y Debold (2025),
que agrupa por co-ocurrencia con datos reales y reporta mejora cuantificada. Como marco
sirven Benaglia et al. (2024), por reglas de asociacion con batching y ruteo, y la linea de
scattered storage en picker-to-parts (Gamez Alban 2024; Chen, Yang, Yu 2026; Prunet 2025),
que muestra a que escala y con que ruteo se evalua hoy la proximidad intra-orden. El bloque
RMFS (Zhuang 2024 en especial) sirve para justificar la senal de afinidad, pero el sistema
es distinto y no hay que extrapolar.
