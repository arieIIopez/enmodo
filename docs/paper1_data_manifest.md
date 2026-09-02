# Paper I — manifiesto de datos del piloto confirmatorio

**Estado:** congelado para la primera reestimación del Coeficiente de Movilidad  
**Fecha:** 2026-09-01  
**Objeto:** triada Santiago 2012 + Ciudad de México 2017 + Bogotá 2015.

## 1. Regla de selección

La primera prueba confirmatoria multiciudad utilizará las mismas tres ciudades que formaron parte del benchmark exploratorio de 2022 y que ofrecen instrumentos de estructura suficientemente distinta para tensionar la armonización:

1. Santiago 2012;
2. Ciudad de México 2017;
3. Bogotá 2015.

Bogotá 2019 queda fuera de la triada primaria. Se reserva como extensión longitudinal posterior para probar estabilidad temporal dentro de una misma ciudad.

Los resultados 2022 se consideran únicamente antecedentes históricos. No se reutilizarán como resultados del método nuevo.

## 2. Archivos canónicos Git LFS

| ciudad-año | ruta canónica | LFS SHA-256 esperado | bytes esperados | rol |
|---|---|---|---:|---|
| Ciudad de México 2017 | `ciudad-de-mexico/viajes_personas_mexico_2017.csv` | `f84c1162c12408889f4ea9175e95e9f9bdad756d4ab4d3d03c68b31658a7a95c` | 132263428 | piloto primario |
| Santiago 2012 | `santiago/csv/viajes_personas_santiago_2012.csv` | `33acc8744cde019b2a47abe9e120a14253658733da57494598e0a92a5575f169` | 36704476 | piloto primario |
| Bogotá 2015 | `bogota/2015/output-csv/viajes_personas_bogota_2015.csv` | `4a43428f72b1e963d116083d366cfcaeb673ba4b338f21109f340525b35ad90a` | 55449326 | piloto primario |
| Bogotá 2019 | `bogota/2019/csv/viajes_personas_bogota_2019.csv` | `0bb99370ab46496d97f0b1f217e6d5cd446efff1467e1bfbf90d4274c513cef8` | 54901849 | extensión longitudinal |

El SHA-256 corresponde al `oid` de Git LFS y, por definición, permite verificar el contenido hidratado byte a byte.

## 3. Duplicados que no deben usarse como fuente canónica

El repositorio conserva copias históricas que no siempre son idénticas al archivo canónico.

### Bogotá 2015

- `bogota/2015/csv/Copia de viajes_personas_bogota_2015.csv`
- LFS SHA-256: `4d3dbeb5150b23ee946b312d77eb31d018b4010d7cf31da42f8e91c741ce3589`
- tamaño: 55449312 bytes.

Difiere del archivo canónico de `output-csv` y no debe mezclarse con él.

### Bogotá 2019

- `bogota/2019/csv/Copia de viajes_personas_bogota_2019.csv`
- LFS SHA-256: `4195b6abc94c782901743ec4c9ab701eac088455e66d983cfbe6c1f926782858`
- tamaño: 54901847 bytes.

Difiere en SHA-256 y tamaño respecto del archivo canónico aun cuando el nombre y contenido aparente sean casi equivalentes. La diferencia debe auditarse sólo si Bogotá 2019 entra en una fase posterior.

## 4. Hallazgo de auditoría sobre G6 histórico

El notebook histórico de Santiago construyó una tabla por persona mediante una consulta equivalente a:

```sql
SELECT Persona,
       Sexo,
       PONDERADOR_CALIBRADO,
       count(*) AS n_viajes,
       AVG(duracion_minutos) AS tiempo_total
FROM viajes_personas
WHERE duracion_minutos < 150
GROUP BY 1,2,3;
```

Por tanto, la variable denominada `tiempo_total` era en realidad **duración media por viaje**, no tiempo total diario de movilidad. Adicionalmente, el conteo de viajes no equivale a participación urbana realizada.

La nueva especificación no debe reutilizar esa agregación. Debe reconstruir desde cada archivo `viajes_personas`:

\[
T_i=\sum_j t_{ij}
\]

y

\[
P_{1i}=\#\{\text{episodios de actividad fuera del hogar observados}\}.
\]

CM-0 se reproducirá únicamente como benchmark histórico.

## 5. Unidad y limitación de los archivos `viajes_personas`

Estos archivos son tablas de viajes enriquecidas con atributos de persona. Permiten reconstruir persona-día **entre personas que registran al menos un viaje**.

No deben utilizarse por sí solos para estimar la tasa de no viajeros, porque una persona con cero viajes no genera una fila en una tabla de viajes. La proporción ponderada de no viajeros deberá recuperarse desde la tabla de personas de cada EOD o desde un adaptador que conserve explícitamente diarios `T=0`.

Esta separación es obligatoria:

- `T|P1` base: puede reconstruirse desde `viajes_personas` para viajeros;
- tasa de no viajeros: requiere universo de personas;
- una métrica poblacional que combine ambos componentes no se construirá hasta disponer de una regla teórica y de datos comparable.

## 6. Contrato mínimo de reconstrucción persona-día

Para cada ciudad el adaptador debe identificar explícitamente:

- identificador de persona;
- identificador de viaje;
- duración del viaje en minutos;
- propósito/destino de actividad;
- código inequívoco de retorno al hogar;
- ponderador de persona;
- variables de diseño muestral disponibles para bootstrap (estrato, conglomerado/UPM u otras).

Reglas confirmatorias:

1. `T_i` es la suma de todas las duraciones válidas del diario; no la media por viaje.
2. Los viajes de retorno al hogar aportan tiempo a `T_i` pero no incrementan `P1`.
3. Cada destino no-hogar que representa una actividad observada incrementa `P1` una vez.
4. No se aplicará el antiguo corte `duracion_minutos < 150` de forma silenciosa. Cualquier trimming se auditará y preregistrará.
5. El ponderador de persona debe ser constante entre los viajes de una misma persona; las inconsistencias se consideran error de datos/adaptador.
6. Los duplicados persona-viaje deben identificarse antes de agregar.

## 7. Salidas obligatorias de la fase de reconstrucción

Cada adaptador deberá producir una tabla persona-día con, al menos:

- `city`;
- `person_id`;
- `t_minutes`;
- `r` (`P1`);
- `weight`;
- `n_trips`;
- `n_home_returns`;
- variables de diseño muestral cuando existan;
- flags de calidad/diario válido.

Además deberá producir un reporte QA con:

- filas de viaje leídas y retenidas;
- personas únicas;
- duplicados persona-viaje;
- tiempos faltantes, negativos y extremos;
- propósitos faltantes/no mapeados;
- distribución de `P1`;
- distribución de `T`;
- variación del ponderador dentro de persona;
- cobertura de variables de diseño muestral.

## 8. Secuencia de ejecución

1. hidratar sólo los objetos LFS canónicos mediante `scripts/hydrate_paper1_lfs.sh`;
2. verificar SHA-256 y tamaño;
3. auditar esquema real de cada CSV;
4. fijar mapeos ciudad-específicos de propósito y retorno al hogar;
5. reconstruir persona-día;
6. recuperar no viajeros desde tabla de personas;
7. calibrar soporte estimable ciudad × `P1`;
8. congelar `P0^C`;
9. estimar `m_c(p)`;
10. construir referencias observadas y ejecutar prueba de compresibilidad.

Ningún resultado escalar del Paper I debe calcularse antes de completar los pasos 1–8.
