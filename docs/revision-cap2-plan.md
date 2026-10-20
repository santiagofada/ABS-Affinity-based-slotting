# Plan de revision del capitulo 2 a partir de los comentarios del director

Fuente: `~/Downloads/revision_tesis_ABS_checklist.md` (101 marcas de tinta + 19
comentarios, sintetizados) y el PDF anotado `~/Downloads/tesis.pdf`.
Fecha: 2026-10-15. El orden de las secciones NO cambia; lo que cambia es donde se
define cada cosa, como se pasa de una seccion a otra, y cuanto apoyo visual hay.

## 1. Esquema del capitulo: que define cada seccion y que usa

Leyenda: **define** = el termino se explica ahi por primera vez; **usa** = ya
definido antes; **usa sin definir** = problema a corregir (es lo que el director
marca como "te falta definir").

| Seccion | Define | Usa sin definir (hoy) | Comentarios del director | Figuras |
|---|---|---|---|---|
| Apertura del cap. | nada | — | "habla de mas", ultimo parrafo tachado | NUEVA: mapa del capitulo |
| 2.1 Evolucion | deposito/CD, consolidacion m x n, pallet, produccion ajustada, tipos de deposito, SKU, unidades de manipulacion | logistica (se usa "cadena logistica" antes de definirla), warehouse (mezcla con deposito) | citas en la historia; transicion al ejemplo de Navidad; salto a logistica; SKU redundante con Fig 2.1; Tabla 2.1 "feo" | Tabla 2.1 rehacer; Fig 2.1 ok; NUEVA: foto de deposito real |
| 2.2 Digitalizacion | WMS (sin expandir la sigla), stock locator, lista de recoleccion, codigo de barras, historial | WMS como sigla, inventario, put-away, "por conveniencia" | hilo contradictorio; definir; supermercado; 6-8 semanas sobra; "consecuencia" reiterativa; devoluciones sueltas | NUEVA: quien se mueve, picker-to-parts vs parts-to-picker (viene de 2.3.3) |
| 2.3 apertura | nada | — | escritura circular | — |
| 2.3.1 Costo | dock, etapas (recepcion, put-away, almacenamiento, picking, empaque, despacho), doble manipulacion | las etapas se nombran en la figura antes de explicarse; reposicion | definir etapas antes de la Fig 2.2; foto; cita doble manipulacion; origen de la Tabla 2.2 | Fig 2.2 rehacer como planta con el flujo |
| 2.3.2 Edificio | geometria/layout, flujo en U y pasante, pasillos transversales, espina, equipamiento | geometria (titulo antes del concepto) | definir geometria; revisar titulo; cita equipamiento | Fig 2.3 recolorear |
| 2.3.3 Picking | densidad de picking, batching (NO se nombra, solo se describe), zonas, ruteo, politica en S y de retorno | TSP, "estimaciones clasicas", batching (la palabra) | primer parrafo depende de la Tabla 2.2; parts-to-picker va antes; definir TSP; citet Bartholdi; cursivas de S | Fig 2.4 recolorear |
| 2.4 Otras decisiones | area de picking rapido, reserva | — | parrafo heterogeneo; "quien dijo eso" (reparto optimo) | — |
| 2.5 Perfil | perfil de actividad, pick, picks vs unidades, Pareto/ABC, lineas por pedido, estacionalidad, co-ocurrencia de familias | familia de productos, pick (se define tarde y mal), batching | apertura recuerda 2.2; fuentes de datos; parrafo denso; que es un pick; ABC/80-20 con fuente; ejemplos de surtido; estacionalidad; transicion a co-ocurrencia | Fig 2.5 rotulos |
| 2.6 Slotting | slotting, dedicado/compartido, reglas (aleatoria, mas cercana, por actividad, por clases), c_k, f_i, modelo lineal, r_i, rotacion, COI, zonas ABC, restricciones, re-slotting, congestion | — | organizar en subsecciones ("vistas"); Q/2 integral; que es la distancia de c_k; COI tachado, definir con formula; estilo dock/picks | Figs 2.6 y 2.7 ok; NUEVA: zonas ABC en franjas vs en pasillos |
| 2.7 Afinidad | co-ocurrencia, asociacion, correlacion, afinidad, transaccion, N s_i n_ij, seis medidas, matriz, grafo | — | apertura recuerda 2.5; cuatro definiciones como lista; negritas; batching y wave; ELIMINAR Tabla 2.3 y poner lista de seis; ejemplo mas claro; separar grafo; caption Fig 2.8 autosuficiente | Tabla 2.3 fuera; Fig 2.8 caption |
| 2.8 Formulacion | PL, simplex, poliedro, relajacion, asignacion, termino cuadratico, QAP, NP-hard, branch and bound, QAPLIB, cotas, heuristicas, optimo local, metaheuristicas, descomposicion, busqueda local | optimo local y metaheuristica se usan antes de definirse | afirmaciones de PL tachadas; citet Dantzig; descompactar NP-hard/B&B/QAPLIB; definir optimo local y metodos | NUEVA (opcional): lineal vs cuadratico en dos SKU |
| 2.9 Estado del arte | las cuatro preguntas, dos fases | scattered storage, baseline | anunciar las preguntas; hacerlas visibles; citet; sacar "cuando en esta seccion se dice que ninguno"; no anunciar 2.10 | NUEVA: esquema de dos fases (agrupar, asignar); Tabla 2.4 queda |
| 2.10 Sintesis | — | — | no abrir recordando 2.9; menos refs a Tabla 2.4; palabra "trabajo" (preguntar) ; "este final es genial" | — |

## 2. Transiciones circulares a corregir

El director marca un patron: una seccion termina anunciando la siguiente y la
siguiente empieza recordando la anterior. Regla: ninguna de las dos; el enlace
tiene que ser conceptual.

1. Apertura del capitulo, ultima oracion ("Todo lo que sigue habla de...").
2. Cierre de 2.2 ("buena parte de este capitulo esta dedicada a recorrerlas").
3. Apertura de 2.3 ("En las secciones anteriores la operacion aparecio de costado").
4. Apertura de 2.5 ("el historial que la Seccion 2.2 dejo").
5. Apertura de 2.7 ("La Seccion 2.5 termino contando pares de familias").
6. Cierre de 2.9 ("y la Seccion 2.10 recoge de todo esto").
7. Apertura de 2.10 ("Lo que la Seccion 2.9 deja").
8. Cierre de 2.3.3 ("la de la Seccion 2.6") se mantiene: es una referencia con contenido, no un anuncio.

## 3. Decisiones que dependen de Santiago

- Listas: el director pide vinetas en tres lugares (cuatro definiciones de 2.7,
  seis medidas en lugar de la Tabla 2.3, cuatro preguntas de 2.9). Va contra la
  regla previa de "sin listas"; manda el director salvo indicacion contraria.
- picker-to-parts / parts-to-picker: mover a 2.2 (cierre, como las dos respuestas
  de la industria) y declarar ahi que la tesis trabaja en picker-to-parts; 2.3.3
  pierde ese parrafo.
- Integral de Q/2: el director duda; opcion A dejar la cuenta, opcion B explicar
  el promedio en una oracion y que la figura lo muestre.
- Tabla 2.1: opcion A cuatro columnas (tipo, pedido, surtido, lo que manda) en
  vertical; opcion B seis columnas apaisada.
- Foto de deposito real: pedir a ShipHero una del deposito estudiado; si no, buscar
  una con licencia libre. Va en 2.3.1 (o en 2.1 junto a los tipos).
- Palabra "trabajo": nota manuscrita de la p. 29 ("trabajo, esto es una tesis").
  Probable objecion a usar "trabajo" para los papers y para la tesis a la vez.
  Preguntar a Juan; si es eso, "trabajos revisados" pasa a "estudios" o "articulos"
  y la tesis se llama siempre "esta tesis".
- Preliminares: titulo, resumen, abstract, agradecimientos, reconocimientos,
  resultados originales (uso en produccion?), organizacion del trabajo.

## 4. Apoyo visual: estilo del manual

Reusar de `docs/manual/manual.tex` la paleta (datos, modelo, plan, batch, sim,
exp, gris) y los estilos TikZ (caja, flecha, pasillo, bay, dock). Se copian al
preambulo de `escritos/main.tex`. Las figuras existentes se recolorean con esa
paleta para que el capitulo sea consistente.

Figuras nuevas, en orden de prioridad:

1. Mapa del capitulo (apertura): cadena de conceptos con una caja por seccion y
   debajo los terminos que define. Responde "hacete un diagramita".
2. Planta del deposito con el flujo de las seis etapas (reemplaza la Fig 2.2 de
   cajitas): dock, estanterias, zona de empaque, y las flechas recepcion, put-away,
   almacenamiento, picking, empaque, despacho.
3. Quien se mueve: dos paneles, picker-to-parts (el operario camina) y
   parts-to-picker (el producto viaja), en 2.2.
4. Foto de deposito real (la aporta Santiago).
5. Zonas ABC en franjas a lo largo del pasillo vs en pasillos enteros (2.6).
6. Esquema de dos fases, agrupar y despues asignar (2.9).
7. Opcional: por que el termino cuadratico rompe el orden (2.8), dos SKU afines y
   dos ubicaciones.
8. Fig 2.8 (grafo de afinidad): ELIMINADA el 2026-10-19. Ni 2.9 ni el metodo
   propio usan nada de grafos sobre la afinidad, asi que no aportaba. El cierre
   de 2.7 ahora habla de la poda de la matriz (umbral o k vecinas). Solo volveria
   si el metodo usa herramientas de grafos, y entonces con datos reales.

## 5. Pasadas y orden de ejecucion (una cosa por vez, con aprobacion)

Decision de Santiago (2026-10-15): primero los cambios directos, de una oracion o
un parrafo, en orden de documento; recien despues los de esqueleto. Lo visual
queda para el final y con moderacion (nada de cajas de colores; escala de grises
o un solo color de acento, a decidir).

### Pasada 0, cambios directos (una oracion o un parrafo, en orden de documento)

HECHA el 2026-10-15. Cada cambio esta marcado en el PDF con `\corregir` (texto
nuevo en verde y nota entre corchetes con el comentario o la pagina del director
que responde). Santiago revisa en el PDF y saca el comando al aprobar. Ademas de
la lista de abajo se hicieron: las dos oraciones de la intro (comentarios 1 y 3),
la aclaracion de sinonimos (warehouse) en la apertura del capitulo, la cita de
Womack 1990 para produccion ajustada (nueva en el bib, chequear), el traslado del
contraste parts-to-picker a 2.2 con la declaracion de alcance (comentario 8), la
lista de cuatro definiciones y la de seis medidas en 2.7 (Tabla 2.3 eliminada,
comentarios 15 y 16), la tabla chica del ejemplo de dos pares, los parrafos de
2.8 (PL, branch and bound, QAPLIB, optimo local), los titulos de parrafo con las
cuatro preguntas en 2.9 y el recorte de referencias hacia atras en 2.10.
NO se hizo (es de esqueleto o decision pendiente): subsecciones de 2.6, Q/2,
Tabla 2.1, foto, mapa del capitulo, palabra "trabajo", preliminares.
ESTADO 2026-10-19: revision de todas las marcas verdes TERMINADA con Santiago,
pagina por pagina del PDF de Juan (intro p.1-2 y cap 2 p.4-29). No queda
ningun \corregir en el fuente. Ademas de lo planificado se hizo: lista
enumerate de las cuatro decisiones en 1.2; apertura del cap 2 reescrita como
relato (version de otro LLM ajustada); parrafo de consolidacion m x n movido
despues de la logistica en 2.1; \gls para SKU, WMS y COI (hipervinculos
desactivados hasta tener glosario); rotulos de description y \paragraph en
versalitas (no negrita); S de la politica en S en modo matematico; pallet,
warehouse, dock, picks en cursiva en todo el capitulo; TSP y programacion
lineal desarrollados (Karp 1972, Applegate 2006, Karmarkar 1984 agregados,
chequear); Fig 2.8 del grafo ELIMINADA; 2.9 con cinco \paragraph titulados como
las columnas de la Tabla 2.4; cierre de 2.10 restaurado al original (Juan lo
dio por bueno) salvo "Esta tesis" -> "Este trabajo".
Pendiente de Santiago: confirmar capitulos/secciones de Bartholdi citados de
memoria (2.1 doble manipulacion; 2.3 "dos depositos"; 5 equipamiento; 6, 9, 11,
13 otras decisiones; 14.2 ejemplos de surtido; 8.3 reparto optimo), y la pagina
de Ballou 2007 para "la ubicacion exacta importaba menos".
Sigue: pasada 1 (esqueleto: 2.6 en subsecciones, Tabla 2.1, foto, mapa del
capitulo opcional), pasada de figuras en gris, preliminares, glosario.

GLOSARIO HECHO (2026-10-19): sin la opcion xindy (makeindex), regla
add_cus_dep de makeglossaries en latexmkrc, \gls en SKU, WMS y COI con la forma
larga adelante de la descripcion. El Glosario sale al final con las tres
entradas y sus paginas; los \gls son hipervinculos que funcionan. En el Action
funciona igual (latexmk lee latexmkrc; makeglossaries y makeindex vienen con
TeX Live); en Overleaf makeglossaries corre solo.
- Intro, apertura: fundir la segunda y tercera oracion.
- Intro, 1.2: cierre que no anuncie el objetivo.
- Cap 2, apertura: sacar la ultima oracion (tachada).
- 2.1: definir logistica antes de "cadena logistica"; punto seguido antes del
  ejemplo de Navidad.
- 2.2: expandir WMS en la primera aparicion; definir put-away; "por conveniencia"
  explicado; sacar las 6-8 semanas.
- 2.3 apertura: sacar la oracion circular.
- 2.3.1: definir dock en su primera oracion; cita de la doble manipulacion.
- 2.3.2: definir geometria en la primera oracion.
- 2.3.3: nombrar batching donde se describe; definir TSP; citet Bartholdi.
- 2.4: cita del reparto optimo del area rapida.
- 2.5: apertura sin 2.2; definir familia de productos; explicar "ternas crece";
  rotulos de la Fig 2.5 con mayuscula.
- 2.6: precisar c_k; COI con definicion y formula.
- 2.7: apertura sin 2.5; caption de la Fig 2.8 autosuficiente.
- 2.8: PL corregida; citet Dantzig.
- 2.9: sacar la aclaracion de "ninguno"; cierre sin anunciar 2.10.
- 2.10: apertura sin 2.9.

### Pasada 1, estructura
1. Preambulo: paleta y estilos del manual en `main.tex`.
2. Apertura del capitulo: mapa del capitulo + tres oraciones, sin el parrafo final.
3. Las siete transiciones circulares de la seccion 2.
4. Mover picker-to-parts / parts-to-picker a 2.2 con la declaracion de alcance.
5. 2.6 en subsecciones: dedicado y compartido; reglas; el costo de una ubicacion;
   picks, reposiciones y COI; clases y restricciones; cuando se decide.
6. 2.9 con las cuatro preguntas anunciadas y como parrafos titulados.
7. 2.7: apertura sin recordar 2.5, cuatro definiciones en lista.

### Pasada 2, contenido y definiciones
8. 2.1: logistica definida antes de usarla; transicion al ejemplo de Navidad;
   SKU en un solo lugar; warehouse unificado; citas de la historia.
9. 2.2: WMS, inventario, put-away y lista de recoleccion definidos al aparecer;
   "por conveniencia" explicado; supermercado reescrito o fuera; sin 6-8 semanas;
   parrafo del historial reformulado; devoluciones enganchadas.
10. 2.3.1: las seis etapas explicadas antes de la figura; dock definido; cita de
    doble manipulacion; batching nombrado en 2.3.3.
11. 2.3.2: geometria definida; titulo "La geometria del deposito"; cita equipamiento.
12. 2.3.3: primer parrafo sin remitir a la Tabla 2.2; TSP definido; citet.
13. 2.4: parrafo heterogeneo recortado; cita del reparto optimo (Bartholdi cap 8).
14. 2.5: apertura nueva; fuentes de datos concretas; parrafo denso partido en
    definiciones (pick, linea, lista) y relaciones; familia de productos definida;
    ABC con fuente; "ternas crece" explicado con la cuenta.
15. 2.6: c_k precisado; COI con definicion, formula y fuente; Q/2 segun decision.
16. 2.7: Tabla 2.3 fuera y lista de seis medidas con formula; ejemplo en dos
    bloques (datos, resultados); grafo separado; caption de la Fig 2.8.
17. 2.8: PL corregida (optimo en un vertice si la region es acotada y hay optimo;
    simplex recorre vertices adyacentes); citet Dantzig; NP-hard, B&B, QAPLIB y
    cotas en parrafos separados; optimo local, busqueda local y metaheuristica
    definidos antes de nombrar metodos.
18. 2.9: scattered storage y baseline definidos; sin la aclaracion de "ninguno".
19. 2.10: apertura sin 2.9; menos refs a la Tabla 2.4; "trabajo" segun Juan.
20. Auditoria de citas: lista de afirmaciones marcadas "CITA" con su fuente.

### Pasada 3, figuras
21. Figuras nuevas 2 a 7 y recoloreo de las existentes; Tabla 2.1 rehecha.

### Pasada 4, redaccion y LaTeX
22. Cursivas de terminos ingleses en todo el capitulo, negritas solo en las
    definiciones de 2.7, citet donde el autor es sujeto, S de la politica, tipeos.

### Pasada 5, preliminares
23. Titulo, resumen, abstract, agradecimientos, resultados originales,
    organizacion del trabajo.

### Catalogo de figuras (2026-10-19)
`docs/propuesta-figuras/propuesta-figuras.pdf` (fuente al lado, no va en git):
N1 PL y relajacion entera (2.7), N2 planta con seis etapas (reemplaza Fig 2.2),
N3 quien se mueve (2.2), N4 zonas ABC franjas vs pasillos (2.5.4), N5 dos fases
(2.8), N6 perfil con datos de data/v2/medium (reemplaza Fig 2.5), N7 mapa del
capitulo (apertura, opcional), N8 el cuadratico rompe el orden (2.7), y R1-R6
las existentes recoloreadas con la paleta del manual (azul/naranja sobre gris).
Pendiente: el si de Santiago figura por figura.
HALLAZGO: en data/v2/medium las lineas por orden son uniformes en {2,3,4,5}
(parametro del simulador de ShipHero), no hay ordenes de 1 linea. Afecta (b) de
N6 y cualquier frase de la tesis que describa el perfil de ordenes del deposito
como real. El Pareto si es informativo: 20% de las SKU = 76% de los picks.
Datos y script en docs/propuesta-figuras/perfil-real/.

Version 2 del catalogo (2026-10-19, tras la revision de Santiago): quedan N1 PL
(poligono pintado, enteros marcados), N2 planta con UN camino continuo numerado,
N3 conveniencia continua + cortes ABC, N4 dos fases con chips y zonas por color,
N5 ejemplo numerico 3 SKU (lineal 14+8=22 vs 16+4=20), R1-R4 iguales, R5 viajes
con doble punta, R6 leyenda de un cuadrado. Descartadas: quien se mueve, mapa
del capitulo, perfil con datos (va al capitulo de datos). Fuente v1 guardada
como propuesta-figuras.v1.tex.
Version 3 (2026-10-19): N2 redibujada con un solo recorrido de picking sin
tramos repetidos (sale de empaque, corredor frontal, sube el pasillo del
producto, fondo, baja por otro pasillo a empaque); N5 (ejemplo numerico del
cuadratico) DESCARTADA por Santiago. Quedan N1-N4 y R1-R6 a la espera de su si.
Revision por subagente (2026-10-19): R1-R4 "va"; N1-N4, R5, R6 "va con
ajustes", todos aplicados (etiquetas pisadas en N1, circulos 1/6 fuera del
edificio y punto azul explicado en N2, tono plano por pasillo y paneles
alineados en N3, pedido {F} solo y dock naranja en N4, viajes que salen del
dock en direcciones distintas y solo letras en R5, leyenda y ejes en R6).
Catalogo listo para el si de Santiago.
FIGURAS EN LA TESIS (2026-10-20): N1 (fig:pl-relajacion, 2.7), N2 (reemplaza
fig:flujo-operaciones, 2.3.1, etapas numeradas en la prosa), N3
(fig:zonas-abc, 2.5.4, con la razon del ruteo en la prosa), N4 (fig:dos-fases,
2.7, citada tambien en 2.8), y R1-R6 recoloreadas en su lugar (prosa de
fig:perfil-lineas dice azul/naranja en vez de clara/oscura). Colores azul y
naranja definidos en main.tex. 54 paginas, sin errores. Pendiente: ampliar la
oracion de las restricciones en 2.5.4 (pedido de Santiago).
