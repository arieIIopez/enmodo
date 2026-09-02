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

## 2. Archivos canónicos de viajes/personas

| ciudad-año | ruta canónica | LFS SHA-256 esperado | bytes esperados | rol |
|---|---|---|---:|---|
| Ciudad de México 2017 | `ciudad-de-mexico/viajes_personas_mexico_2017.csv` | `f84c1162c12408889f4ea9175e95e9f9bdad756d4ab4d3d03c68b31658a7a95c` | 132263428 | piloto primario |
| Santiago 2012 | `santiago/csv/viajes_personas_santiago_2012.csv` | `33acc8744cde019b2a47abe9e120a14253658733da57494598e0a92a5575f169` | 36704476 | piloto primario |
| Bogotá 2015 | `bogota/2015/output-csv/viajes_personas_bogota_2015.csv` | `4a43428f72b1e963d116083d366cfcaeb673ba4b338f21109f340525b35ad90a` | 55449326 | piloto primario |
| Bogotá 2019 | `bogota/2019/csv/viajes_personas_bogota_2019.csv` | `0bb99370ab46496d97f0b1f217e6d5cd446efff1467e1bfbf90d4274c513cef8` | 54901849 | extensión longitudinal |

El SHA-256 corresponde al `oid` de Git LFS y permite verificar el contenido hidratado byte a byte.

## 3. Universos de personas para estimar no viajeros

La tasa de no viajeros no se derivará de `viajes_personas`. Para cada ciudad se usará el universo de personas de la EOD:

| ciudad-año | ruta | almacenamiento | identificador verificado | bytes |
|---|---|---|---|---:|
| Ciudad de México 2017 | `ciudad-de-mexico/source-csv/tsdem.csv` | Git LFS | SHA-256 `1b739929ef0207251c835870e29376a1066b53253b4b879f1f330c2622d8ce93` | 22649303 |
| Santiago 2012 | `santiago/source-csv/personas.csv` | Git LFS | SHA-256 `57a5ae5631cc0a9ab61aa86ab48524b06f6a6c507cb3c696f23fe7d568b454fa` | 6862309 |
| Bogotá 2015 | `bogota/2015/source-xlsx/encuesta 2015 - personas.xlsx` | blob Git regular | blob SHA-1 `252a4d99434ede490f0c9b2670bddfb25178f093` | 24555372 |

El script `scripts/hydrate_paper1_lfs.sh` hidrata y verifica los dos universos LFS y comprueba el blob de Bogotá 2015.

## 4. Duplicados que no deben usarse como fuente canónica

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

## 5. Hallazgo de auditoría sobre G6 histórico

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

## 6. Unidad y limitación de los archivos `viajes_personas`

Estos archivos son tablas de viajes enriquecidas con atributos de persona. Permiten reconstruir persona-día **entre personas que registran al menos un viaje**.

No deben utilizarse por sí solos para estimar la tasa de no viajeros, porque una persona con cero viajes no genera una fila en una tabla de viajes. La proporción ponderada de no viajeros se recuperará desde los universos de personas indicados en la sección 3.

Esta separación es obligatoria:

- `T|P1` base: se reconstruye desde `viajes_personas` para viajeros;
- tasa de no viajeros: se estima desde el universo de personas;
- una métrica poblacional que combine ambos componentes no se construirá hasta disponer de una regla teórica y de datos comparable.

## 7. Contrato mínimo de reconstrucción persona-día

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

## 8. Salidas obligatorias de la fase de reconstrucción

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
- cobertura de variables de diseño muestral;
- personas del universo sin viaje observado y su peso expandido.

## 9. Secuencia de ejecución

1. hidratar los objetos LFS canónicos mediante `scripts/hydrate_paper1_lfs.sh`;
2. verificar SHA-256/tamaño y el blob de personas Bogotá 2015;
3. auditar esquema real de cada tabla;
4. fijar mapeos ciudad-específicos de propósito y retorno al hogar;
5. reconstruir persona-día de viajeros con `scripts/person_day.py`;
6. estimar no viajeros desde los universos de personas;
7. calibrar soporte estimable ciudad × `P1`;
8. congelar `P0^C`;
9. estimar `m_c(p)`;
10. construir referencias observadas y ejecutar prueba de compresibilidad.

Ningún resultado escalar del Paper I debe calcularse antes de completar los pasos 1–8.
