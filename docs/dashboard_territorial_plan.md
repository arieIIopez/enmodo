# Estudio del repositorio para dashboard de mapeo e inteligencia territorial

## 1) Hallazgos clave del repositorio

- El repositorio está organizado por **ciudad** y, en algunos casos, por **año** (ej. `bogota/2015`, `bogota/2019`).
- Cada ciudad/año sigue un patrón consistente:
  - `source-*`: insumos originales (csv/xlsx/sav/shp/geojson).
  - `python/`: notebook de procesamiento principal por ciudad-año.
  - `csv` u `output-csv`: productos estandarizados para análisis comparado.
  - `shape` o `source-shp`: geografía de zonificación territorial.
- El script compartido `scripts/eod_analysis.py` concentra funciones de transformación e indicadores reutilizables.

## 2) Limitación detectada (importante)

En el clon actual, gran parte de los archivos CSV de salida están versionados con **Git LFS** y aparecen como punteros (`version https://git-lfs.github.com/spec/v1`) en lugar de datos tabulares descargados.

### Implicación

Antes de construir el dashboard con datos reales, hay que materializar datasets con:

```bash
git lfs pull
```

Sin ese paso no es posible perfilar volúmenes reales, nulos, distribuciones ni calidad final por tabla.

## 3) Qué ya podemos inferir para diseño del dashboard

A partir de notebooks y estructura del repo, el modelo analítico mínimo del dashboard puede considerar:

### Entidades

- **Viajes-personas** (tabla central por ciudad-año).
- **Matrices origen-destino por zonas** (trabajo, hábiles, total).
- **Geometrías de zonas** (shapefiles por ciudad-año).

### Variables comparables (núcleo cross-city)

- Identificador de viaje/persona (con variantes por ciudad).
- Zona origen / zona destino.
- Coordenadas de origen y destino.
- Modo de transporte (y agregaciones público/privado).
- Propósito de viaje (trabajo, estudio, etc.).
- Duración y distancia (incluyendo distancia manhattan en varios notebooks).
- Factores de expansión / ponderadores.
- Segmentadores sociodemográficos (sexo, edad/tramos, ocupación según disponibilidad).

### Perspectiva de género (obligatoria en el modelo)

El dashboard debe permitir análisis **conjunto** y **desagregado** para:

- Total población.
- Hombres.
- Mujeres.

Y adicionalmente incluir comparativas explícitas:

- Brecha absoluta (`mujeres - hombres`) por métrica.
- Brecha relativa (`mujeres / hombres`) por métrica.
- Participación de cada sexo en viajes, tiempos, distancias e inmovilidad.

## 4) Propuesta de arquitectura para dashboard territorial

## 4.1 Capa de datos (recomendada)

Construir un pipeline reproducible con 3 capas:

1. **Bronze**: copia cruda de `source-*` (sin transformación).
2. **Silver**: estandarización por ciudad-año a un esquema común.
3. **Gold**: métricas agregadas para BI y mapas (OD, accesibilidad, brechas).

## 4.2 Esquema canónico mínimo (Silver)

### `fact_trips`
- `city`, `year`
- `trip_id`, `person_id`, `household_id` (nullable según ciudad)
- `origin_zone_id`, `dest_zone_id`
- `origin_lon`, `origin_lat`, `dest_lon`, `dest_lat`
- `mode_std`, `purpose_std`
- `duration_min`, `distance_manhattan_m`
- `weight_trip`, `weight_person`
- `is_weekday`, `is_weekend`

### `dim_person`
- `city`, `year`, `person_id`
- `sex_std`, `age`, `age_group_std`
- `income_group_std`, `occupation_std`

### `dim_zone`
- `city`, `year`, `zone_id`
- `zone_name`
- `geometry`

### `fact_od_matrix`
- `city`, `year`, `segment` (`work`, `weekday`, `all`)
- `origin_zone_id`, `dest_zone_id`
- `trip_count_w`
- `share_cum` (si aplica filtro por percentil acumulado)

## 4.3 Capa analítica (Gold)

- Viajes ponderados por modo, propósito y franja horaria.
- Tiempo y distancia media/mediana por segmento.
- Índice de movilidad diaria (viajes per cápita).
- Flujos OD principales (top N por peso).
- Indicadores intra/inter-zona.
- Brechas por sexo/edad/ingreso (si existe variable local).

### 4.3.1 Módulo de Coeficiente de Movilidad (inspirado en Gini)

Incorporar un módulo específico para el **Coeficiente de Movilidad** (CEPAL, Ariel López), enfocado en inequidad de movilidad/accesibilidad, y calcularlo:

- Para población total.
- Para hombres.
- Para mujeres.

Implementación recomendada (alineada a la lógica ya existente en `scripts/eod_analysis.py`):

1. Construir dataset persona-día con:
   - `n_viajes` (interacción),
   - `tiempo_total` (accesibilidad, como costo temporal),
   - `peso_persona`.
2. Clasificar personas en grupos `A1`, `A2`, `A3`, `B1`, `B2`, `B3`, `C`, `D` usando la lógica de intersección regresión-mediana.
3. Calcular los 11 indicadores base reportados en la metodología:
   - `(A1+A2+A3)/P`, `A1/P`, `(A2+A3)/P`, `B3/P`, `B1/P`, `B2/P`, `C/P`, `D/P`, `(C+D)/P`, `<=15 min`, `2 viajes diarios`.
4. Publicar resultados en formato tablero:
   - General,
   - Hombre,
   - Mujer,
   - Brechas H-M (absoluta y relativa).

Tablas sugeridas:

- `fact_mobility_coefficient`
  - `city`, `year`, `sex_group` (`total|hombre|mujer`)
  - `indicator_id` (1..11)
  - `indicator_name`
  - `value`
- `fact_mobility_gap`
  - `city`, `year`, `indicator_id`
  - `female_value`, `male_value`
  - `gap_abs`, `gap_ratio`

## 4.4 Front-end recomendado

- **Mapa principal**: coropletas + flujos OD (line/arc) por selección de segmento.
- **Panel de filtros**: ciudad, año, día (hábil/no hábil), modo, propósito, sexo, edad.
- **KPIs**: viajes ponderados, duración mediana, distancia mediana, viajes per cápita.
- **Tabs**:
  1. Movilidad general
  2. Trabajo y estudio
  3. Equidad territorial
  4. Género y movilidad (hombres/mujeres juntos y por separado)
  5. Comparador entre ciudades/años

## 5) Plan de desarrollo propuesto (iterativo)

## Sprint 0 — habilitación

- [ ] Ejecutar `git lfs pull` y validar integridad de archivos.
- [ ] Definir diccionario canónico (mapping por ciudad-año).
- [ ] Extraer catálogo de columnas reales de todos los outputs.

## Sprint 1 — modelo de datos

- [ ] Implementar normalizador a esquema Silver.
- [ ] Generar tablas Gold con métricas base y OD.
- [ ] Crear pruebas de calidad (nulos críticos, rangos válidos, zonas huérfanas).
- [ ] Estandarizar variable de sexo y cobertura por ciudad-año para análisis comparado.

## Sprint 2 — MVP de dashboard

- [ ] Mapa OD + filtros + KPIs.
- [ ] Vista comparativa modo/purpose.
- [ ] Tab de género con resultados total/hombres/mujeres y brechas.
- [ ] Exportación CSV/PNG de resultados.

## Sprint 3 — inteligencia territorial

- [ ] Detección de centralidades por flujo.
- [ ] Clustering de zonas por patrón de movilidad.
- [ ] Índices compuestos de accesibilidad y desigualdad de tiempos.
- [ ] Coeficiente de Movilidad completo (11 indicadores) con serie comparativa por sexo y ciudad.

## 6) Riesgos y mitigaciones

- **Heterogeneidad semántica** entre ciudades (modo, propósito, ponderadores).  
  - Mitigación: data contract + tabla de equivalencias versionada.
- **CRS distinto por shapefile**.  
  - Mitigación: normalizar a EPSG:4326 en Silver.
- **Pesos mal aplicados** (persona vs viaje).  
  - Mitigación: validar indicadores contra notebooks originales.
- **Faltantes en coordenadas**.  
  - Mitigación: fallback a centroides de zona para visualización.
- **Sesgo de género por codificaciones distintas de sexo**.  
  - Mitigación: capa de homologación + reporte de trazabilidad por ciudad/año.

## 7) Próximo paso sugerido

Construir un script de **perfilamiento automático** que, tras `git lfs pull`, recorra todas las salidas `viajes_personas_*` y `matriz_zonas_*` para producir:

- inventario de columnas,
- tipos inferidos,
- nulos,
- dominios/catálogos básicos,
- reporte consolidado (`docs/data_profile.md`).

Con ese reporte podemos cerrar el modelo canónico, activar el módulo de coeficiente de movilidad con perspectiva de género y arrancar el dashboard con baja fricción.
