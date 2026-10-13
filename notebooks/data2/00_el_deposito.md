# El deposito, contado en llano

Resumen para entender que hay en `data/v2/` antes de abrir un notebook. Es la version en
palabras de lo que despues se mide en `01_EDA_v2`.

## Que es este dataset

Es un deposito sintetico que ShipHero genero en septiembre de 2026, en tres tamanos que
comparten la misma logica y solo cambian de escala: `small`, `medium` y `big`. Cada uno trae
seis meses de actividad, del 1 de enero al 30 de junio de 2026, siete dias por semana y casi
las 24 horas. A diferencia del dataset anterior, ahora se sabe a que orden del cliente
pertenece cada linea de picking.

| | small | medium | big |
|---|---:|---:|---:|
| pasillos | 4 | 8 | 16 |
| bays por lado de pasillo | 10 | 16 | 24 |
| pasillos transversales | 1 | 2 | 3 |
| estantes por bay | 4 | 5 | 6 |
| ubicaciones | 1.920 | 7.680 | 27.648 |
| SKUs (ubicaciones ocupadas) | 1.728 | 6.912 | 24.883 |
| merchants | 4 | 50 | 100 |
| pickers | 5 | 20 | 60 |
| ordenes | 27.150 | 203.625 | 452.500 |
| batches | 1.086 | 8.145 | 18.100 |
| lineas de picking | 95.043 | 712.137 | 1.583.010 |
| reposiciones | 9.417 | 76.966 | 171.333 |

Cada carpeta trae ademas un `manifest.json` con los parametros del generador y un
`layout.html` que dibuja el plano y permite consultar distancias entre dos bays.

## El espacio: como esta armado el deposito

El deposito es una sola zona, la `A`, con pasillos paralelos. A cada lado de un pasillo hay
una hilera de **bays**, que son las columnas de estanteria. Un bay se identifica con el pasillo
y un numero, por ejemplo `A03-07` es el bay 7 del pasillo 3. La numeracion va en zigzag: los
impares quedan de un lado del pasillo (`odd`, el de menor x) y los pares del otro (`even`), de
modo que `A03-07` y `A03-08` estan enfrentados, a la misma altura, y a distancia cero entre si.

Cada bay tiene varios **estantes** (`A`, `B`, `C`, ...) y cada estante seis **bins**. La
combinacion bay, estante y bin es una **ubicacion**, que es el hueco fisico donde vive un
producto, por ejemplo `A03-07-B-02`. Las ubicaciones tienen ademas un `location_id` numerico
que es el que usan las demas tablas.

Los **pasillos transversales** son cortes que atraviesan las estanterias y permiten pasar de
un pasillo a otro sin ir hasta la punta. En las coordenadas se ven como un salto mas grande
entre dos niveles consecutivos de `y` (216 pulgadas en vez de 96), y en la tabla de
distancias se nota porque dos bays enfrentados en pasillos vecinos estan mas cerca a la altura
del transversal que en el medio de un bloque.

El **dock** es la mesa de empaque, el punto donde empieza y termina cada recorrido. Esta en
la esquina, a la altura del arranque del pasillo 1. Las distancias entre bays y hasta el dock
son distancias caminadas por los pasillos, no en linea recta, y estan en pulgadas. No se
modela el movimiento dentro de un bay, asi que dos ubicaciones del mismo bay estan a
distancia cero.

## Los actores

Un **SKU** es un producto distinto, `SKU-00042`. En el arranque cada SKU ocupa exactamente
una ubicacion y cada ubicacion tiene a lo sumo un SKU; un 10% de las ubicaciones esta vacio.

Un **merchant** es el vendedor dueno del SKU, `MER-007`. El deposito es compartido por varios
merchants, con catalogos de tamano parecido entre si. Importa porque cada orden pertenece a un
solo merchant.

Un **picker** es el operario que recorre el deposito recolectando, y un **repositor** el que
repone stock. Son grupos distintos de `user_id`.

## La demanda: ordenes y batches

Una **orden** es lo que pidio un cliente: entre dos y cinco SKUs distintos de un mismo
merchant, con una a tres unidades de cada uno. En el dato una orden nunca repite un SKU.

Un **batch** es un viaje de picking. El deposito junta 25 ordenes consecutivas, tal como
llegaron, y las manda a recolectar en una sola pasada a un unico picker. Como las ordenes
llegan mezcladas, un batch contiene ordenes de varios merchants. Un batch termina con unos 60
a 90 SKUs distintos, y sus lineas vienen ordenadas en el orden en que el picker las recorrio,
serpenteando por pasillo y numero de bay.

Esta distincion es la que faltaba en el dataset anterior. Que dos productos se compren juntos
es un hecho de la orden. Que se recolecten juntos es un hecho del batch, y depende de como se
arme el batch. Con `order_id` se puede medir lo primero y construir lo segundo a voluntad.

## El stock y las reposiciones

Cada linea de picking descuenta unidades de la ubicacion donde estaba el SKU. Cuando un pick
dejaria el stock en negativo, justo antes ocurre una **reposicion**. Si todavia quedaban
unidades, se recarga en el mismo lugar. Si el stock habia llegado a cero, con probabilidad 0,9
el SKU se **muda** a una ubicacion vacia elegida al azar y la vieja queda libre; el resto de
las veces se recarga donde estaba. Alrededor del 45% de las reposiciones son mudanzas, asi que
el plano del deposito cambia durante los seis meses.

La reposicion queda registrada con el momento, el SKU, la cantidad, de donde salio y a donde
fue. Lo unico que un algoritmo de slotting puede decidir de todo esto es el destino.

## Las cinco tablas y como se unen

| tabla | una fila por | clave |
|---|---|---|
| `coordinates` | bay, mas el dock | `bay_id`, con `aisle`, `bay_number`, `side`, `x`, `y` |
| `distances` | par de bays sin ordenar, incluido el dock | `bay_a` < `bay_b`, `distance_in` |
| `initial_stock` | ubicacion, ocupada o vacia | `location_id`, `location_name`, `bay_id`, `sku`, `merchant_account_id`, `units` |
| `picking_events` | linea de pick | `batch_id`, `order_id`, `timestamp`, `user_id`, `location_id`, `sku`, `merchant_account_id`, `quantity` |
| `replenishment_events` | reposicion | `timestamp`, `user_id`, `source_location_id`, `target_location_id`, `sku`, `quantity` |

Las lineas de picking y las reposiciones se unen al stock inicial por `location_id`. El stock
inicial y las lineas de picking se unen a las coordenadas por el bay (`bay_id` y `bay_name`).
La tabla de distancias guarda cada par una sola vez, con el id menor primero, asi que para
buscar la distancia entre dos bays hay que ordenarlos antes.

## Que cambia respecto de v1

El dataset anterior, hoy en `data/v1/`, era un solo deposito de 25 pasillos y 27.000 SKUs con
30 dias de historia, sin pasillos transversales, con 10 merchants y sin `order_id`. Los
batches tenian unos 76 SKUs distintos y eran la unica unidad de co-demanda observable, lo que
diluia cualquier afinidad. Todo lo publicado hasta ahora en la tesis sale de ese dataset.

En v2 la geometria, el stock y las reposiciones siguen la misma logica, pero hay tres tamanos,
seis meses en vez de uno, pasillos transversales y la orden del cliente. El codigo del paquete
lee cualquiera de las carpetas con `WarehouseDataLoader(ruta)`, y la ruta la da
`dataset_dir("v1")` o `dataset_dir("v2", "small")` en `config.py`.
