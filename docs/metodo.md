# Estrategia de resolucion

Documenta las decisiones de diseno del metodo: las alternativas consideradas en cada punto,
su evaluacion y la opcion adoptada. La formulacion del problema esta en
[modelo.md](modelo.md); la implementacion, en [sistema.md](sistema.md).

Estado de cada decision: **[adoptada]**, **[recomendada]** (pendiente de confirmacion) o
**[abierta]** (variable experimental).

---

## 1. Descomposicion del problema

El QAP global es intratable de forma exacta a esta escala
([modelo.md](modelo.md#43-relacion-con-el-qap-y-limite-de-escala)). La estrategia consiste
en resolver un problema aproximado y tratable.

| Alternativa | Idea | Ventaja | Desventaja | Estado |
|---|---|---|---|---|
| Descomposicion bi-nivel | agrupar productos; asignar zonas a los grupos y resolver el interior de cada zona | subproblemas de tamano reducido, independientes, optimizables de forma exacta | la calidad depende del agrupamiento; ignora parte de la estructura global | **[adoptada]** |
| Truncado top-k | conservar solo los vinculos de afinidad mas fuertes | reduce el termino cuadratico; complementa la anterior | descarta afinidad debil | **[adoptada]** |
| Relajacion del QAP global | resolver una relajacion (LP u otra) del problema completo | formulacion unica | dimension inalterada; cota potencialmente floja | descartada |

```mermaid
flowchart TB
    QAP["QAP global<br/>decenas de miles de productos y ubicaciones<br/>intratable de forma exacta"]
    QAP -->|"agrupamiento + truncado top-k"| P1
    subgraph binivel["Descomposicion bi-nivel"]
        direction TB
        P1["Problema 1<br/>repartir ubicaciones entre ~10 grupos<br/>transporte lineal: exacto"]
        P2["Problema 2<br/>un QAP por zona, independientes entre si"]
        P1 --> P2
    end
    P2 -->|"zona pequena"| EX["resolvedor exacto"]
    P2 -->|"zona grande"| SW["busqueda por intercambios<br/>delta incremental O(k)"]
```

---

## 2. Problema 1: reparto de ubicaciones entre grupos

Asignar a cada grupo $c$ un conjunto de $\text{size}[c]$ ubicaciones.

| Alternativa | Modelo | Ventaja | Desventaja | Estado |
|---|---|---|---|---|
| A. Transporte lineal | $\min \sum \text{demanda}[c]\cdot\text{costo}[\ell]\cdot y_{\ell c}$ con $\sum_\ell y_{\ell c} = \text{size}[c]$, $\sum_c y_{\ell c} \le 1$ | lineal y exacto (matriz totalmente unimodular); la contiguidad resulta del orden por costo | usa demanda agregada como proxy; no considera afinidad entre grupos | **[recomendada]** |
| B. Regiones fijas con capacidad | particionar el deposito en regiones y asignar grupos con restriccion de capacidad | admite afinidad entre regiones | requiere definir las regiones; mayor complejidad | alternativa |
| C. Secuenciado de grupos | decidir el orden de los grupos sobre la linea ordenada por costo | representa zonas contiguas dimensionadas al grupo | el costo de cada bloque depende del orden acumulado; no es un QAP de coeficientes fijos | descartada |

La alternativa A se resuelve de forma exacta y economica; su optimo asigna las ubicaciones
de menor costo al grupo de mayor demanda agregada.

**Resolucion.** Se planteo como problema de optimizacion con solver, aunque el optimo
coincide con la forma cerrada de ordenar por demanda (verificado: ambos producen el mismo
costo). El planteo con solver generaliza al caso con afinidad entre grupos, que convierte
el problema en un QAP a nivel de grupo. **[adoptada]**

**Criterio de orden de las ubicaciones.** Determina la forma de las zonas. Medido sobre v1:

| Criterio | Forma resultante | Dispersion media de la zona sobre el recorrido |
|---|---|---:|
| Distancia al dock | bandas concentricas | 10.402 |
| Posicion en el recorrido serpenteante | zonas contiguas | 2.202 |

Se adopta la posicion en el recorrido: produce zonas casi cinco veces mas compactas.
**[adoptada]**

---

## 3. Problema 2: resolucion de cada zona

Para cada grupo, sobre sus ubicaciones asignadas, se resuelve el QAP completo. Las zonas
son independientes entre si.

| Alternativa | Ambito | Ventaja | Desventaja | Estado |
|---|---|---|---|---|
| Resolvedor exacto | zonas pequenas | optimo probado; referencia de calidad | no escala: una zona por vendor tiene entre ~250 (v2 `big`) y ~2.700 (v1) productos | **[adoptada]** |
| Busqueda por intercambios | zonas grandes | escala mediante el delta incremental | sin garantia de optimalidad | **[adoptada]** |
| `scipy.quadratic_assignment` (FAQ) | — | sin requisito de licencia | heuristica distinta de la estudiada | descartada |

Regla: por zona, resolucion exacta si el tamano lo permite; busqueda por intercambios en
caso contrario. El umbral se midio sobre v2 `small` (notebook `data2/02_el_codigo`, seccion
6b): con lambda igual a 0,01 el exacto prueba optimalidad en segundos hasta unos 20 productos
y corta por tiempo a los 30; el QAP puro (lambda igual a 0) no cierra en un minuto ni con 20.
Como ninguna zona de vendor baja de 250 productos, en la practica el resolvedor de zona es la
busqueda por intercambios, y el exacto queda como vara sobre subinstancias de ese tamano, donde
la busqueda quedo a menos de 0,2% del optimo y el greedy por demanda hasta 7% cuando la
afinidad pesa. **[adoptada]**

---

## 4. Afinidad entre grupos

| Alternativa | Ventaja | Desventaja | Estado |
|---|---|---|---|
| Descartarla: la afinidad solo cuenta dentro de cada grupo | descomposicion simple; Problema 1 lineal | pierde el co-picking entre grupos | **[adoptada]** |
| Modelarla: QAP a nivel de grupo en el Problema 1 | captura el co-picking entre grupos | el Problema 1 deja de ser lineal | alternativa pendiente |

Con la afinidad entre grupos descartada, la responsabilidad de reunir los productos afines
recae por completo en el agrupamiento: dos productos co-demandados que caen en grupos
distintos no se optimizan entre si. La implementacion ya calcula la afinidad agregada
entre grupos y la descarta, de modo que incorporarla es una extension acotada.

---

## 5. Criterio de agrupamiento

| Agrupamiento | Grupos | Resultado medido (v1) |
|---|---|---|
| `merchant` (vendor) | ~10, balanceados | 10% peor que el baseline por demanda |
| `demand_class` (A/B/C) | 3 | equivalente al baseline (-0,3%, dentro del ruido) |
| Componentes conexas de la afinidad | 1 | degenerado: una componente de ~15.500 productos y miles de aislados; descartado |
| Deteccion de comunidades | — | pendiente de implementacion |

El agrupamiento por vendor, plan inicial del trabajo, resulta contraproducente: obliga a
distribuir los productos de alta rotacion de todos los vendors a lo largo del deposito. El
fenomeno coincide en magnitud con lo reportado en la literatura (Zhang 2016: la
zonificacion ABC resulta 10,28% peor que la asignacion por rotacion pura). La eleccion del
agrupamiento queda **[abierta]**; la deteccion de comunidades sobre el grafo de afinidad
filtrado es la alternativa a implementar.

---

## 5b. Unidad de co-ocurrencia y peso lambda

| Alternativa | Idea | Estado |
|---|---|---|
| Co-ocurrencia por batch | la unica posible en v1; mezcla ~25 ordenes de varios merchants y diluye la co-demanda | conservada para comparar |
| Co-ocurrencia por orden | disponible en v2 (`cooccurrence_col="order_id"`); mide la co-demanda donde ocurre | **[adoptada]** para v2 |
| lambda sin normalizar | los terminos difieren en ~1.500 a 1; lambda igual a 0,5 equivale a demanda pura | es lo que se uso en v1 |
| lambda sobre proporciones | f y A divididas por su suma; L y Q pasan a ser distancias medias en pulgadas (`normalize=True`) | **[adoptada]** |

Con la co-ocurrencia por orden aparece una verificacion previa a cualquier metodo: si la
co-ocurrencia observada supera la que produciria el azar dados los soportes. En v1 y v2 no la
supera ([modelo.md](modelo.md#23-caracterizacion-exploratoria)), de modo que el aporte de la
afinidad no puede medirse con estos datos hasta que se confirme como se generan las ordenes o
se disponga de afinidad inyectada.

---

## 6. Regimen de evaluacion

| Alternativa | Supuesto | Estado |
|---|---|---|
| Simulacion con reposiciones | el deposito cambia: los productos se mudan al agotarse su stock | **[adoptada]** |
| Evaluacion estatica | el plan se respeta indefinidamente (almacenamiento dedicado) | conservada como caso de comparacion |

La evaluacion estatica es el caso particular de la simulacion bajo la politica `home`;
la equivalencia esta verificada numericamente
([sistema.md](sistema.md#8-validacion-del-simulador)).

Decisiones asociadas:

- **Origen de las reposiciones**: se replican del dato (momento, producto y cantidad);
  solo se decide la ubicacion destino. Evita introducir supuestos sobre cuanto reponer.
- **Ambito de decision de la politica**: todas las reposiciones. Mantener la ubicacion
  actual es una decision mas de la politica.
- **Multiplicidad de ubicaciones**: un producto puede ocupar varias ubicaciones. Ocurre en
  el dato durante una mudanza y una politica puede producirlo.
- **Costo del re-slotting inicial**: excluido del objetivo y declarado, siguiendo la
  convencion del area para slotting estatico.

---

## 7. Configuracion vigente

```
Reduccion:     bi-nivel + truncado top-k
Problema 1:    transporte lineal, exacto
                 ubicaciones ordenadas por posicion en el recorrido (zonas compactas)
Problema 2:    QAP por zona, en paralelo
                 zona pequena -> resolvedor exacto
                 zona grande  -> busqueda por intercambios
Afinidad entre grupos: descartada (solo intra-zona)
Agrupamiento:  abierto; vendor descartado por resultado, comunidades pendiente
Co-ocurrencia: por orden en v2 (por batch en v1)
Peso lambda:   sobre f y A normalizadas a proporciones (normalize=True)
Evaluacion:    simulacion con reposiciones; estatica como comparacion
```

Decisiones abiertas: criterio de agrupamiento definitivo, incorporacion de la afinidad
entre grupos. El umbral del Problema 2 quedo medido: exacto hasta unos 20 productos,
intercambios en el resto.
