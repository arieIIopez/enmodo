# Paper I — protocolo de dominio territorial

**Estado:** congelado antes de la primera ejecución multiciudad integrada  
**Fecha:** 2026-09-03  
**Aplica a:** Santiago 2012, ZMVM 2017 y Bogotá 2015.

## 1. Problema

Las tres encuestas no están diseñadas sobre una unidad administrativa equivalente. Usar el municipio/comuna central como si representara la ciudad introduciría una selección territorial distinta entre instrumentos y, además, cortaría sistemas cotidianos de movilidad que operan a escala metropolitana.

La unidad territorial del Paper I será por tanto el **dominio residencial metropolitano oficial de cada EOD**, no el límite administrativo de la capital.

## 2. Regla confirmatoria

Para cada encuesta se retendrán las personas cuyo hogar pertenece al universo residencial definido por el diseño muestral oficial de esa EOD:

- **Santiago 2012:** dominio oficial de la Encuesta Origen-Destino del Gran Santiago;
- **México 2017:** dominio oficial de la Encuesta Origen-Destino de la Zona Metropolitana del Valle de México (ZMVM);
- **Bogotá 2015:** Bogotá D.C. y los 17 municipios vecinos incluidos en el diseño oficial de la EODH 2015.

La pertenencia territorial se determina por **residencia del hogar/persona**. No se filtrarán personas en función del origen, destino o proporción de sus viajes dentro del área, porque eso condicionaría la muestra por el comportamiento de movilidad que se pretende estimar.

## 3. Sensibilidades territoriales

Los resultados restringidos a unidades administrativas centrales (por ejemplo, Bogotá D.C. o CDMX) podrán calcularse únicamente como análisis descriptivo/sensibilidad. No reemplazarán el estimando metropolitano principal ni se utilizarán para escoger el dominio que produzca mayor compresibilidad, mejor ajuste o un ranking más conveniente.

No se define una sensibilidad equivalente usando únicamente la comuna de Santiago, porque esa unidad administrativa no es territorialmente comparable con Bogotá D.C. o CDMX y representa sólo una fracción del sistema urbano del Gran Santiago.

## 4. Consecuencias para la armonización

1. Los ponderadores deben reproducir el universo poblacional del **dominio oficial de la encuesta y del tipo de día seleccionado**. Un ponderador que expanda correctamente otro universo no se utilizará por similitud numérica.
2. Los no viajeros se estimarán dentro del mismo dominio residencial y tipo de día que los viajeros.
3. Las curvas `T|P1` se construirán sólo después de validar dominio, ponderación y completitud del diario en cada ciudad.
4. El soporte común `P0^C` se evaluará después de aplicar esta regla territorial a las tres EOD.
5. Ningún resultado escalar se calculará antes de cerrar esas verificaciones.

## 5. Bogotá 2015: hallazgo que motivó la auditoría

La tabla fuente contiene hogares de Bogotá D.C. y 17 municipios de Cundinamarca. La variable `MUNICIPIO` identifica de forma explícita el dominio residencial. Una primera ejecución provisional usando todas las personas y `PONDERADOR_CALIBRADO` produjo una expansión cercana a 18,08 millones, aproximadamente el doble de la población del área de estudio reportada para 2015. Ese resultado **no se acepta como estimación**: activó una auditoría específica de `PONDERADOR_CALIBRADO`, `FE_TOTAL`, `FACTOR_AJUSTE` y componentes de probabilidad antes de continuar.

La curva provisional de Bogotá generada durante esa auditoría no se utilizará para seleccionar el soporte común ni para tomar decisiones sobre el coeficiente.

## 6. México 2017: control de dominio

`TSDEM` conserva entidad y municipio/delegación de residencia (`ent`, `mun`) y las variables de diseño (`upm_dis`, `est_dis`). La suma del factor oficial en el dominio completo es coherente en orden de magnitud con la ZMVM y se mantendrá como estimando principal sujeto a los restantes controles de diario.

## 7. Principio de decisión

Si una ciudad requiere una corrección de ponderación, recodificación o exclusión adicional, ésta deberá justificarse por el diseño/documentación del instrumento o por una inconsistencia verificable de los microdatos. No se aceptarán transformaciones cuyo único argumento sea acercar una cifra a un benchmark externo o mejorar la compresibilidad del Coeficiente de Movilidad.
