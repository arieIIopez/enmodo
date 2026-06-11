# Propuesta metodológica para el coeficiente de movilidad

## 1. Pregunta de investigación

El coeficiente de movilidad busca describir qué tan favorable es la relación entre la **interacción urbana observada** y el **tiempo requerido para desplazarse**. La unidad de análisis es la persona en un día de encuesta.

La hipótesis central es que, manteniendo las demás condiciones constantes, una persona que realiza más viajes con una duración media baja puede interactuar con más actividades y oportunidades urbanas que una persona que realiza pocos viajes de larga duración.

El indicador no pretende afirmar que viajar más sea siempre mejor. Los viajes son una aproximación a interacciones realizadas y pueden incluir desplazamientos obligados, actividades de cuidado o fragmentación modal. Por eso deben publicarse junto con propósito, modo, sexo, ingreso y otros estratificadores cuando estén disponibles.

## 2. Fundamento teórico

La propuesta combina dos ideas:

1. **Presupuesto de tiempo de viaje (Yacov Zahavi).** La población dispone de un presupuesto temporal limitado para desplazarse. La carga diaria de transporte debe analizarse junto con la cantidad de desplazamientos que permite realizar.
2. **Accesibilidad y reinversión del tiempo (David Metz).** Una mejora del transporte puede expresarse menos como ahorro permanente de tiempo y más como aumento de destinos, actividades u oportunidades alcanzables dentro de un presupuesto temporal.

La propuesta es coherente con estas ideas, pero no debe presentar los viajes observados como una medición directa de todas las oportunidades potencialmente accesibles. En el paper se distinguirán:

- **interacción observada:** viajes, destinos o actividades realizados;
- **carga temporal observada:** minutos diarios de viaje;
- **accesibilidad potencial:** oportunidades alcanzables, cuando exista información territorial o de redes.

## 3. Variables fundamentales

Para la persona `i` y sus viajes válidos `j`:

- `n_i`: cantidad de viajes realizados durante el día;
- `d_ij`: duración en minutos del viaje `j`;
- `t_prom_i`: duración media de viaje;
- `t_total_i`: tiempo total diario de viaje.

Se cumple la identidad:

```text
t_total_i = n_i * t_prom_i = suma(d_ij)
```

La representación principal conserva `n_i` en el eje horizontal y `t_prom_i` en el vertical porque permite distinguir dos personas con igual carga diaria pero diferente combinación de interacción y duración. El tiempo total se calcula y publica siempre como indicador derivado y control de consistencia.

### Ejemplo

- Persona A: 4 viajes de 20 minutos; `t_total = 80`.
- Persona B: 2 viajes de 40 minutos; `t_total = 80`.

Ambas dedican el mismo tiempo diario, pero A registra más interacciones con menor duración media. Esa diferencia es precisamente la información que se perdería si se utilizara solamente el tiempo total.

## 4. Hipótesis que deben declararse y probarse

### H1. Interacción

Una mayor cantidad de viajes diarios se interpreta como mayor interacción urbana observada, condicionada por propósito y características personales.

### H2. Eficiencia temporal

Para una cantidad dada de viajes, una duración media menor representa una relación temporal más favorable.

### H3. Inmovilidad compatible con privilegio

Una persona con cero o muy pocos viajes puede decidir no desplazarse porque dispone de buena accesibilidad local, teletrabajo, servicios de proximidad o capacidad de sustitución. Esta situación se denomina **inmovilidad compatible con privilegio**, no privilegio demostrado.

### H4. Inmovilidad compatible con exclusión

Una persona con cero o muy pocos viajes puede estar restringida por grandes distancias, falta de transporte, costo, discapacidad, inseguridad o ausencia de oportunidades. Esta situación se denomina **inmovilidad compatible con exclusión**, no exclusión demostrada.

Las hipótesis H3 y H4 no pueden distinguirse causalmente solo con cantidad y duración de viajes. Para personas con un viaje puede utilizarse la duración como señal provisional. Para personas con cero viajes no existe duración observada y la clasificación debe quedar como **inmovilidad no identificada**, salvo que haya una medida externa de accesibilidad o preguntas sobre razones para no viajar.

## 5. Universo y unidad de observación

El universo debe construirse desde la tabla de personas, no desde la tabla de viajes. Así se conservan las personas con cero viajes.

Requisitos mínimos:

- un registro por persona y día;
- factor de expansión de persona positivo;
- viajes identificados de forma única;
- duración no negativa;
- reglas explícitas para viajes que cruzan medianoche;
- distinción entre viaje completo y etapa.

Cuando una encuesta contiene etapas, `n_i` debe contar identificadores de viaje únicos y no filas de etapa.

## 6. Tratamiento de datos

### 6.1 Duraciones extremas

No se usarán umbrales diferentes por ciudad sin justificación. La limpieza debe combinar:

1. reglas oficiales de cada encuesta;
2. un criterio armonizado para comparabilidad;
3. análisis de sensibilidad, por ejemplo sin recorte y con percentil ponderado 99 o 99,5.

Cada publicación debe informar registros y población expandida excluidos.

### 6.2 Ponderación

Los factores de expansión deben intervenir en:

- la regresión de referencia;
- la mediana de duración;
- los cuantiles;
- las proporciones finales.

La frontera se estima en la población general y luego se aplica sin recalcular a cada sexo u otro subgrupo. Esto permite comparar a todos con el mismo estándar metropolitano.

## 7. Frontera empírica

La versión inicial estima una regresión lineal ponderada:

```text
t_prom_i = alfa + beta * n_i + error_i
```

La recta no representa causalidad ni un estándar normativo; es una referencia empírica de la relación observada. Deben reportarse pendiente, intercepto, tamaño expandido y mediana ponderada.

Antes del paper se comparará esta especificación con:

- regresión robusta;
- cuantiles ponderados;
- suavizado no paramétrico;
- fronteras normativas comunes entre ciudades.

## 8. Tipología propuesta, versión 2

La implementación reproducible genera estados interpretables y mutuamente excluyentes:

| Estado | Regla básica | Interpretación |
|---|---|---|
| `alta_interaccion_favorable` | viajes por encima del punto de referencia y duración bajo la recta | muchas interacciones con condición temporal favorable |
| `alta_interaccion_costosa` | viajes por encima del punto de referencia y duración sobre la recta | muchas interacciones con costo temporal alto |
| `baja_interaccion_favorable` | más de un viaje, por debajo del punto de referencia y bajo la recta | pocas interacciones, pero condición temporal favorable |
| `baja_interaccion_costosa` | más de un viaje, por debajo del punto de referencia y sobre la recta | pocas interacciones y costo temporal alto |
| `inmovilidad_privilegio_compatible` | un viaje corto respecto de la referencia | baja movilidad compatible con buena accesibilidad |
| `inmovilidad_exclusion_compatible` | un viaje largo respecto de la referencia | baja movilidad compatible con restricción espacial |
| `inmovilidad_no_identificada` | cero viajes sin información externa | no es posible distinguir voluntad de restricción |

El punto de referencia de interacción es la intersección entre la recta y la mediana ponderada. Si la pendiente no permite una intersección estable, se usa la mediana ponderada de viajes y se registra esta decisión en los metadatos.

## 9. Resultado principal

En la etapa de validación se recomienda llamar al resultado **perfil de movilidad y accesibilidad**, compuesto por la proporción ponderada en cada estado.

Puede publicarse un escalar provisional:

```text
CM_favorable =
  P(alta_interaccion_favorable
    + baja_interaccion_favorable
    + inmovilidad_privilegio_compatible)
  / P(clasificable)
```

Este valor se encuentra entre 0 y 1. No debe interpretarse como equivalente matemático al Gini. El denominador excluye `inmovilidad_no_identificada` y la publicación debe mostrar qué proporción quedó sin identificar.

La categoría compatible con privilegio debe incluirse y excluirse en análisis de sensibilidad, porque su valoración favorable depende de evidencia adicional.

## 10. Estrategia de validación

### Validez de constructo

Comprobar si los estados favorables se asocian con:

- mayor número de oportunidades a 15, 30 y 45 minutos;
- mayor diversidad de destinos y propósitos;
- proximidad a empleo, educación, salud y cuidados;
- menor duración total condicionada por cantidad de actividades.

### Validez convergente

Comparar el perfil con indicadores de accesibilidad acumulativa, gravitatoria y basada en transporte público.

### Validez discriminante

Verificar que el indicador no sea únicamente una transformación de ingreso, motorización o centralidad residencial.

### Robustez

Recalcular con:

- duración total y duración media;
- distintos tratamientos de extremos;
- viajes, tours, destinos y actividades;
- frontera lineal, cuantílica y no paramétrica;
- inclusión y exclusión de viajes de regreso al hogar.

### Equidad

Estimar brechas con una frontera común por sexo, ingreso, edad, discapacidad, ocupación, responsabilidades de cuidado y territorio.

## 11. Estructura sugerida del paper

1. Problema: limitaciones de medir movilidad solo por velocidad, distancia o viajes.
2. Marco teórico: Zahavi, Metz, accesibilidad e interacción.
3. Definiciones e hipótesis falsables.
4. Fuentes y armonización de encuestas origen-destino.
5. Construcción del perfil y del escalar provisional.
6. Resultados comparativos por ciudad.
7. Validación externa y análisis de sensibilidad.
8. Desigualdades por sexo y nivel socioeconómico.
9. Limitaciones: viajes observados no equivalen a oportunidades y la inmovilidad tiene causas latentes.
10. Discusión, uso en política pública y agenda futura.

## 12. Requisitos del sistema

El sistema debería separar cuatro capas:

1. **adaptadores por ciudad:** nombres y códigos originales;
2. **esquema armonizado:** persona, viaje, duración, peso, propósito, modo y geografía;
3. **motor del indicador:** resumen persona-día, frontera, clasificación y métricas;
4. **productos:** tablas auditables, gráficos, mapas y metadatos.

Cada ejecución debe guardar:

- versión del código y configuración;
- fuente y fecha de descarga;
- reglas de limpieza;
- cantidad muestral y expandida antes y después de filtros;
- parámetros de la frontera;
- cobertura de clasificación;
- resultados generales y por subgrupo;
- análisis de sensibilidad.

## 13. Ejemplo mínimo de implementación

```python
from scripts.mobility_coefficient import (
    build_person_day,
    calculate_profile,
    classify_person_days,
    fit_reference_model,
)

persona_dia = build_person_day(
    viajes,
    persons=personas,
    person_id="id_persona",
    trip_id="id_viaje",
    duration="duracion_minutos",
    weight="factor_expansion",
    attributes=("sexo",),
)

# La frontera se estima una sola vez con toda la población.
referencia = fit_reference_model(
    persona_dia,
    weight="factor_expansion",
)
clasificacion = classify_person_days(persona_dia, referencia)

perfil_general = calculate_profile(
    clasificacion,
    weight="factor_expansion",
)
perfil_sexo = calculate_profile(
    clasificacion,
    weight="factor_expansion",
    group_by=("sexo",),
)
```

Los adaptadores de cada ciudad deben producir estas columnas armonizadas. No deben volver a estimar la frontera dentro de cada sexo, ingreso o territorio.

## 14. Hoja de ruta para publicación

### Fase 1: auditoría y reproducción

- reconstruir una tabla persona-día comparable para cada ciudad;
- reproducir los resultados históricos;
- explicar cualquier diferencia entre la versión histórica y la versión 2;
- publicar configuraciones, parámetros y tablas agregadas.

### Fase 2: validación

- incorporar oportunidades y tiempos de red para al menos una ciudad piloto;
- contrastar las categorías compatibles con privilegio y exclusión;
- ejecutar análisis de sensibilidad y remuestreo;
- acordar si el resultado final será un perfil, un escalar o ambos.

### Fase 3: paper comparativo

- congelar una versión metodológica antes de comparar ciudades;
- reportar intervalos de confianza que respeten el diseño muestral;
- separar resultados descriptivos, validación e interpretación causal;
- publicar código, diccionario armonizado y resultados no identificables.

### Fase 4: sistema

- implementar adaptadores declarativos por encuesta;
- validar automáticamente esquema, cobertura, pesos y consistencia temporal;
- producir artefactos versionados para API, tablero y descarga;
- mantener trazabilidad completa desde la fuente hasta cada indicador.
