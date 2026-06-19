# Formulación matemática

Este documento presenta la formulación rigurosa del problema. Es la referencia
formal del proyecto; los demás documentos de `docs/` lo describen en términos más
accesibles.

## Notación

| Símbolo | Significado |
|---|---|
| $I$, $n = \lvert I \rvert$ | conjunto de productos a ubicar |
| $L$, $m = \lvert L \rvert$ | conjunto de ubicaciones candidatas, con $m \ge n$ |
| $f_i \ge 0$ | demanda del producto $i$ (métrica primaria: *pick lines*) |
| $c_\ell \ge 0$ | costo de acceso de la ubicación $\ell$ (distancia al dock) |
| $a_{ij} \ge 0$ | afinidad entre los productos $i, j$; simétrica, con $a_{ii} = 0$ |
| $d_{\ell k} \ge 0$ | distancia entre las ubicaciones $\ell, k$ (vía sus bays); simétrica, con $d_{\ell\ell} = 0$ |
| $x_{i\ell} \in \{0, 1\}$ | variable de decisión: vale $1$ si el producto $i$ se ubica en $\ell$ |
| $\lambda \in [0, 1]$ | peso relativo entre demanda-acceso y afinidad-proximidad |

## Programa cuadrático binario

$$
\min_{x}\;\; \lambda \sum_{i \in I} \sum_{\ell \in L} f_i\, c_\ell\, x_{i\ell}
\;+\; (1 - \lambda) \sum_{i \in I} \sum_{j \in I} \sum_{\ell \in L} \sum_{k \in L}
a_{ij}\, d_{\ell k}\, x_{i\ell}\, x_{jk}
$$

sujeto a

$$
\sum_{\ell \in L} x_{i\ell} = 1 \quad \forall i \in I, \qquad
\sum_{i \in I} x_{i\ell} \le 1 \quad \forall \ell \in L, \qquad
x_{i\ell} \in \{0, 1\}.
$$

El **término lineal** modela el objetivo de ubicar los productos frecuentes en
posiciones de bajo costo de acceso. El **término cuadrático** penaliza ubicar
lejos a los productos con alta afinidad: cada par $(i, j)$ aporta su afinidad
$a_{ij}$ multiplicada por la distancia $d_{\ell k}$ entre las ubicaciones que se les
asignan.

Las restricciones imponen que cada producto ocupe exactamente una ubicación
($\sum_\ell x_{i\ell} = 1$) y que cada ubicación aloje a lo sumo un producto
($\sum_i x_{i\ell} \le 1$). La desigualdad admite ubicaciones vacías, dado que
$m > n$.

## Relación con el QAP

Restringida a las $n$ ubicaciones efectivamente utilizadas, una solución factible
asigna a cada producto una única ubicación, y el costo adopta la forma de
**Koopmans-Beckmann** del **Quadratic Assignment Problem (QAP)** con término
lineal. El QAP es **NP-hard** y resulta intratable de forma exacta incluso para
instancias moderadas, lo que descarta su resolución directa a esta escala y
motiva la estrategia de baselines y heurísticas.

## Escala y consecuencias

Con $n \approx 27.000$ y $m \approx 30.000$: el número de variables binarias es
$n \cdot m \approx 8{,}1 \times 10^{8}$, y la afinidad densa tendría
$n^2 \approx 7{,}3 \times 10^{8}$ entradas. De ahí dos decisiones de diseño:

1. **Afinidad dispersa.** $a_{ij}$ se almacena como matriz CSR y se restringe a
   los vínculos más fuertes (top-$k$ por producto), reduciendo las entradas de
   $O(n^2)$ a $O(nk)$.
2. **Evaluación incremental de movimientos.** La búsqueda local no recomputa el
   costo total ante cada movimiento, sino su variación (ver más abajo).

## Evaluación incremental de un intercambio

Sea $\ell_i$ la ubicación asignada al producto $i$ en una solución dada (la única
$\ell$ con $x_{i\ell} = 1$). Considérese intercambiar las ubicaciones de dos
productos $a$ y $b$: tras el intercambio, $a$ pasa a $\ell_b$ y $b$ a $\ell_a$. La
variación de costo $\Delta = C_{\text{después}} - C_{\text{antes}}$ se calcula sin
recomputar la suma global. Con $a$ y $d$ simétricas y diagonal nula:

$$
\Delta_{\text{lineal}} = (f_a - f_b)\,(c_{\ell_b} - c_{\ell_a}),
$$

$$
\Delta_{\text{cuad}} = 2 \sum_{k \neq a, b} (a_{ak} - a_{bk})\,
\bigl(d_{\ell_b, \ell_k} - d_{\ell_a, \ell_k}\bigr),
$$

$$
\Delta = \lambda\, \Delta_{\text{lineal}} + (1 - \lambda)\, \Delta_{\text{cuad}}.
$$

El factor $2$ proviene de contar cada par en sus dos órdenes, válido por la
simetría de $a$ (de ahí que la instancia exija una afinidad simétrica). El término
$a_{ab}\, d_{\ell_a \ell_b}$ no cambia porque $d$ es simétrica. El cálculo es
$O(n)$ en el caso denso, pero $O(\deg(a) + \deg(b)) = O(k)$ con afinidad top-$k$:
este es el argumento que vuelve viable la búsqueda local sobre decenas de miles de
productos.

## Costo de ruta (evaluación)

El objetivo $C$ es un *surrogate* que guía la búsqueda. El desempeño se reporta con
una medida distinta: el costo de los recorridos reales sobre test, descrito en
[pipeline.md](pipeline.md#6-evaluation--la-medición-sobre-test). La distinción
entre ambos se trata en [bloques.md](bloques.md#objetivo-y-evaluador-dos-medidas-distintas).

## Preguntas abiertas

- **Calibración de $\lambda$** y elección de la métrica de afinidad: son
  hiperparámetros a estudiar empíricamente por su sensibilidad sobre test.
- **Definición de zona** para los métodos en dos etapas (bi-nivel).
- **Política para ubicaciones sobrantes** ($m > n$): qué hacer con los huecos no
  utilizados.
- **Ruteo:** se parte de un orden serpenteante simple; el refinamiento a S-shape
  estricto queda como extensión.
- **Generalización temporal:** se usa un único corte train/test; convendría validar
  con múltiples ventanas.

## Referencias

- Koopmans, T. C., & Beckmann, M. (1957). *Assignment problems and the location of
  economic activities.* Econometrica.
- Bartholdi, J. J., & Hackman, S. T. (2014). *Warehouse & Distribution Science*
  (Rel. 0.96). Georgia Institute of Technology.
- Viveros, P., et al. (2021). *Slotting Optimization Model for a Warehouse with
  Divisible First-Level Accommodation Locations.* Applied Sciences, 11(3), 936.
