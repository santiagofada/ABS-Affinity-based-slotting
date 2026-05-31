

---

### **Propuesta de Trabajo Especial \- Licenciatura en Matemática Aplicada**

**Alumno:** Santiago Fada

## **Directores**

Director: Dr. Juan Bautista Cabral (FaMAF)  
Director: Dr. Mariano Ferrero (ShipHero)

**Justificación de doble dirección:** Según lo estipulado en el Artículo 4, se requiere una dirección compartida debido a la naturaleza del proyecto. El Dr. Mariano Ferrero proporcionará la visión estratégica así como acceso a datos y demás conocimiento del sector logístico, mientras que el Dr. Juan Bautista Cabral supervisará el rigor metodológico y la **generalización de los modelos propuestos**.

**Título (provisorio):** Modelado y optimización de la asignación de productos en sistemas logísticos basado en patrones de demanda.

#### **Contexto y Definición del Problema**

En el ámbito de la logística, específicamente en grandes centros de distribución (denominados *warehouses*), la eficiencia se mide principalmente por el tiempo de respuesta y el costo operativo por orden procesada. El tiempo promedio de respuesta se ve condicionado por tres factores principales: el desplazamiento físico hasta el producto, el tiempo que el operario tarda en tomar el objeto de la estantería y el tiempo de empaquetado de los productos de la orden. Dentro de este proceso, el factor más crítico es el desplazamiento del operario hacia la ubicación del producto. En un entorno de e-commerce con miles de órdenes diarias, cada metro adicional de caminata se traduce en una pérdida de productividad que afecta directamente la capacidad de despacho del almacén.

Frecuentemente, en la gestión de grandes centros de distribución, también conocidos como warehouses, la ubicación de los productos en las estanterías se decide de manera heurística, esto significa que, ante la llegada de nuevo inventario, la asignación de espacios suele responder a la disponibilidad inmediata de huecos libres o a criterios de rotación individual. Sin embargo, este método no considera la relación entre los artículos. En la práctica, los productos no se demandan de forma aislada; existen patrones de compra recurrentes o “afinidades” donde ciertos artículos tienden a aparecer juntos en los mismos pedidos. Como consecuencia, es posible que productos con una altísima probabilidad de ser recolectados en el mismo viaje se encuentren almacenados en extremos opuestos del depósito, obligando al operario a realizar recorridos redundantes e ineficientes.

A esta ineficiencia se suma el dinamismo del mercado. Los hábitos de consumo y las afinidades entre productos cambian con el tiempo, lo que vuelve obsoleta cualquier organización estática del inventario. La falta de una estrategia de asignación de ubicaciones (*slotting*) basada en datos impide que el *warehouse* se adapte a estas fluctuaciones. El problema real es que, al no explotar la información histórica de los pedidos para organizar el espacio físico, se está operando un depósito "ciego" a las asociaciones de su propia demanda. Esto no sólo ralentiza la operación diaria, sino que complica el diseño y la escalabilidad de nuevos centros logísticos, donde la disposición inicial del inventario determinará el éxito o el fracaso de los flujos de trabajo.

#### **Objetivos y Metodología**

El objetivo principal de este trabajo es **modelar el problema de asignación de inventario y proponer un enfoque algorítmico** que permite transformar el registro histórico de ventas en una configuración optimizada del almacén. Para alcanzarlo, la propuesta se estructura sobre tres pilares fundamentales:

En primer lugar, se realizará un **Análisis de Patrones de Demanda** mediante técnicas de Ciencia de datos para procesar registros históricos de demanda provenientes de sistemas de gestión de almacenes (WMS). El propósito es identificar y cuantificar las "afinidades" o reglas de asociación entre productos, permitiendo determinar una métrica de atracción que refleje la probabilidad de que distintos artículos sean solicitados de forma simultánea.

En segundo lugar, se llevará a cabo el **Modelado del Espacio Físico**, traduciendo la geometría y las restricciones operativas del almacén, como por ejemplo la disposición de pasillos, niveles de estanterías y sentidos de circulación, a un modelo matemático de distancias. Este modelo servirá como el escenario sobre el cual se evaluará el costo logístico de cada posible configuración de productos.

Finalmente, la **Evaluación de Estrategias** abordará el desafío para obtener soluciones en tiempos computacionales razonables. La validez de estas estrategias se determinará mediante simulaciones, comparando el desempeño del modelo propuesto frente a  diversos modelos o enfoques ya establecidos en la industria, haciendo esta comparación en términos de reducción de distancias recorridas.

#### **Cronograma de Actividades**

El proyecto se desarrollará en un plazo de 8 meses aproximadamente. Durante el primer trimestre, se profundizará en el conocimiento del negocio, revisión de la bibliografía, estado del arte así como  la preparación de los datos. El segundo trimestre se centrará en el descubrimiento de patrones de afinidad mediante técnicas de aprendizaje automático. Finalmente, la última etapa estará dedicada al diseño y resolución del modelo de optimización de ubicaciones, asi como la validación de los resultados y la redacción del documento final.

|  | Mes 1 | Mes 2 | Mes 3 | Mes 4 | Mes 5 | Mes 6 | Mes 7 | Mes 8 | Mes 9 | Mes 10 | Mes 11 | Mes 12 |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| Conocimiento de negocio, revision bibliografica |  |  |  |  |  |  |  |  |  |  |  |  |
| Procesamiento y análisis de datos |  |  |  |  |  |  |  |  |  |  |  |  |
| Diseño de experimentos para modelar afinidades |  |  |  |  |  |  |  |  |  |  |  |  |
| Diseño de modelos de slotting |  |  |  |  |  |  |  |  |  |  |  |  |
| comparación entre modelos |  |  |  |  |  |  |  |  |  |  |  |  |
| Escritura del trabajo y conclusiones finales |  |  |  |  |  |  |  |  |  |  |  |  |

#### **Bibliografía Inicial**

* Koopmans, T. C., & Beckmann, M. (1957). *Assignment problems and the location of economic activities*.  
* Bartholdi, J. J., & Hackman, S. T. (2014). *Warehouse & Distribution Science* (Release 0.96). Georgia Institute of Technology.  
* Viveros, P., González, K., Mena, R., Kristjanpoller, F., & Robledo, J. (2021). *Slotting Optimization Model for a Warehouse with Divisible First-Level Accommodation Locations*. Applied Sciences, 11(3), 936\. [https://doi.org/10.3390/app11030936](https://doi.org/10.3390/app11030936)

---

