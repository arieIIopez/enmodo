# Coeficiente de Movilidad — estado de investigación

**Actualizado:** 2026-09-01  
**Repositorio:** ENMODO / `arieIIopez/enmodo`  
**Propósito:** continuidad científica y operativa del programa iniciado a partir del estudio exploratorio CEPAL 2022.

## 1. Decisión conceptual vigente

El Coeficiente de Movilidad no se define ex ante mediante una razón `P/T` ni una frontera. El objeto primario es la relación entre tiempo diario de movilidad y participación urbana realizada:

\[
m_c(p)=E[T\mid P_1=p,c].
\]

- `T`: tiempo total diario de movilidad, min/persona-día.
- `P1`: número de episodios de actividad fuera del hogar durante un diario válido.
- unidad analítica: persona-día.
- universo base: diarios válidos con `T>0`; la tasa ponderada de no viajeros se reporta separadamente.

`P1` es la especificación confirmatoria primaria. Diversidad de propósitos, propósitos distintos y destinos únicos son validaciones/especificaciones alternativas.

## 2. Estimador primario

Como `P1` es discreto y cardinal, `m_c(p)` se estima mediante media ponderada por diseño dentro de cada celda ciudad × P1. No se impone forma funcional en la estimación confirmatoria básica.

Para una distribución de referencia común `H` sobre el soporte comparable `P0`:

\[
B_c(H)=\sum_{p\in P_0}H(p)m_c(p).
\]

`B_c(H)` se expresa en minutos/persona-día y se interpreta como tiempo de movilidad directamente estandarizado por nivel de participación realizada.

Las antiguas familias `CM-0`, `MY`, `CM-R`, `CM-Q`, fronteras cuantílicas y frontera estocástica se conservan como antecedentes, benchmarks o análisis secundarios. No definen el estimando confirmatorio principal.

## 3. Compresibilidad escalar

Para dos ciudades:

\[
\Delta_{ab}(H)=B_a(H)-B_b(H).
\]

Sea `𝓗` una familia de referencias admisibles. El sobre robusto es:

\[
\mathcal D_{ab}(\mathcal H)=
[\inf_{H\in\mathcal H}\Delta_{ab}(H),\sup_{H\in\mathcal H}\Delta_{ab}(H)].
\]

Con tolerancia práctica `δ_T`:

- `a` domina a `b` si todo el sobre está por debajo de `-δ_T`;
- equivalencia robusta si todo el sobre está en `[-δ_T,+δ_T]`;
- `b` domina a `a` si todo el sobre está sobre `+δ_T`;
- el resto es dependencia de referencia / incomparabilidad estructural.

La incertidumbre de referencia y la incertidumbre muestral son fenómenos distintos. Los intervalos bootstrap pareados deben aplicarse a `Δ_ab(H)` y no construirse restando intervalos marginales independientes.

## 4. Familia confirmatoria de referencias

Para un conjunto `C` de ciudades y soporte global común `P0^C`, sea `H_c^0` la distribución de `P1` de cada ciudad, calculada con ponderadores de diseño, restringida a `P0^C` y renormalizada.

La familia confirmatoria es:

\[
\mathcal H_{obs}=conv\{H_c^0:c\in C\}.
\]

Como `Δ_ab(H)` es lineal en `H`, basta evaluar las distribuciones observadas de cada ciudad como puntos extremos. La mezcla igualitaria de ciudades es un escenario descriptivo interior, no un nuevo extremo.

Como `P1` tiene escala cardinal discreta, una distribución uniforme sobre las categorías de `P0^C` se usará como **stress test estructural separado**. No integra la envolvente confirmatoria principal.

## 5. Invarianza y escalas alternativas de participación

La estandarización es invariante a una transformación monótona `s=g(r)` si la referencia se transforma simultáneamente por `H^g=g#H`. Por ello, referencias uniformes en coordenadas arbitrarias no deben usarse automáticamente para indicadores alternativos de participación. Esta cautela es especialmente importante para índices de diversidad o medidas normalizadas que no posean una escala cardinal natural.

## 6. Soporte común

Un grafo multiciudad sólo es interpretable como orden parcial si todas las aristas usan el mismo estimando:

\[
P_0^C=\bigcap_{c\in C}supp(P_{1,c}),
\]

pero la presencia nominal de una categoría no basta. El soporte confirmatorio será un **soporte común estimable**, evaluado mediante:

- `n_raw` por ciudad × P1;
- masa de ponderadores;
- participación ponderada de la celda;
- tamaño muestral efectivo de Kish `n_eff=(Σw)^2/Σw^2`.

No existe un umbral por defecto en el código. El corte de estimabilidad debe calibrarse con el piloto y congelarse antes de la ejecución confirmatoria.

Comparaciones pareadas sobre soportes `P_ab` más amplios son admisibles como sensibilidad, pero no permiten clausura transitiva ni ranking global.

## 7. G6b

El ejercicio G6b previo pasa a interpretarse como antecedente histórico de sensibilidad de referencia / compresibilidad, pero **no puede reusarse como estimación de `T|P1`**. La auditoría de los notebooks originales mostró que el G6 histórico no medía tiempo total diario.

La reejecución debe:

1. reconstruir `P1`, `T` y ponderadores en las ciudades incluidas;
2. auditar soporte efectivo;
3. fijar `P0^C`;
4. estimar `m_c(p)` mediante medias ponderadas;
5. construir `H_c^0`;
6. estimar `B_c(H_k)` para cada referencia extrema;
7. realizar bootstrap compatible con el diseño de cada EOD;
8. construir `𝓓_ab(𝓗_obs)` y clasificar cada par;
9. ejecutar uniforme-P1 como stress test separado;
10. sólo si existe compresibilidad robusta, explorar una representación adimensional `CM_B`.

El valor `δ_T=5 min/persona-día` utilizado en ejercicios previos debe considerarse provisional hasta cerrar su justificación y análisis de sensibilidad; no debe hardcodearse como umbral universal.

## 8. Tier A

Tier A se utiliza después de establecer el patrón `T|P1` y su robustez comparativa.

- **Tier A.1:** impedancia geométrica / geometría del espacio de oportunidades. Validez de constructo y mecanismo exploratorio; no equivale a accesibilidad confirmatoria por transporte.
- **Tier A.2:** red histórica y oportunidades; prueba mecanística confirmatoria cuando la reconstrucción histórica sea defendible.

Tier A no define el coeficiente.

## 9. Código y documentación creados

- `docs/scalar_compressibility.md`: especificación matemática y reglas de decisión.
- `docs/paper1_data_manifest.md`: triada piloto, objetos canónicos, hashes, duplicados, universos de personas y contrato de reconstrucción.
- `scripts/scalar_compressibility.py`: escalarización, deltas pareados, sobre robusto, clasificación y aristas de dominancia.
- `scripts/reference_distributions.py`: referencias observadas por ciudad, mezcla igualitaria, stress test uniforme y cobertura del soporte.
- `scripts/support_diagnostics.py`: diagnóstico de soporte y tamaño efectivo de Kish; sin thresholds implícitos.
- `scripts/mobility_function.py`: estimación directa de `m_c(p)` y tasa separada de no viajeros.
- `scripts/person_day.py`: reconstrucción estricta viaje → persona-día; `T=sum(t_j)` y retorno al hogar excluido de `P1`.
- `scripts/paper1_adapters.py`: adaptadores explícitos para Santiago 2012, México 2017 y Bogotá 2015.
- `scripts/hydrate_paper1_lfs.sh`: hidratación selectiva y verificación criptográfica de los objetos LFS requeridos.
- `scripts/kitagawa_mobility.py`: descomposición descriptiva de diferencia agregada en componente `T|P1` y composición de participación.
- tests sintéticos correspondientes para compresibilidad, referencias, función, persona-día, adaptadores y descomposición.

Los tests están versionados, pero esta nota no debe interpretarse como evidencia de que un workflow CI haya sido ejecutado sobre los microdatos reales.

## 10. Triada confirmatoria congelada

La primera prueba multiciudad se realizará con:

1. Santiago 2012;
2. Ciudad de México 2017;
3. Bogotá 2015.

Bogotá 2019 se reserva para una extensión longitudinal posterior. La selección conserva continuidad con el benchmark exploratorio de 2022 y permite probar armonización entre instrumentos de estructura distinta.

Los archivos canónicos, hashes LFS y duplicados excluidos se encuentran en `docs/paper1_data_manifest.md`. No se mezclarán copias históricas de Bogotá con objetos canónicos aun cuando tengan nombres casi idénticos.

## 11. Hallazgo crítico de la auditoría histórica

Los tres notebooks del G6 histórico construyeron la variable llamada `tiempo_total` mediante `AVG(duracion_minutos)` agrupado por persona, no mediante suma diaria de duraciones:

- Santiago 2012: además aplicaba `duracion_minutos < 150`;
- Ciudad de México 2017: aplicaba `duracion_minutos < 180`;
- Bogotá 2015: aplicaba `duracion_minutos < 180`.

Por tanto, G6 relacionaba número de viajes con **duración media por viaje**, y además utilizaba umbrales no armonizados. Esto impide interpretar aquella variable como presupuesto temporal diario.

La nueva formulación corrige ambos problemas:

\[
T_i=\sum_j t_{ij}
\]

sin trimming implícito, y

\[
P_{1i}=\#\{\text{episodios de actividad fuera del hogar}\}.
\]

Los retornos al hogar agregan minutos a `T_i` pero no incrementan `P1`. CM-0 permanece sólo como benchmark de reproducibilidad histórica.

## 12. Universo primario de día

La primera comparación no mezclará días laborales con sábado/domingo ni, en Santiago, componentes estivales.

- Santiago 2012: viaje con `FactorLaboralNormal` observado; ponderación de persona mediante `Factor_LaboralNormal`.
- Ciudad de México 2017: `p5_3 == 1`, correspondiente al bloque entre semana; el sábado (`p5_3 == 2`) queda fuera de la especificación primaria. El ponderador de persona es `factor_y` tras el merge TVIAJE–TSDEM; `factor_x` queda como control QA.
- Bogotá 2015: `DIA_HABIL == 'Si'`, con `PONDERADOR_CALIBRADO` como peso de persona repetido en los viajes.

La armonización es por tipo de día, no una afirmación de equivalencia estacional entre fechas de levantamiento.

## 13. Viajeros y no viajeros

Los archivos `viajes_personas` sólo contienen personas con al menos un viaje. Sirven para reconstruir `T|P1` entre viajeros, pero no permiten inferir la tasa de no viajeros.

La tasa de no viajeros debe derivarse de los universos de personas originales:

- Santiago: `santiago/source-csv/personas.csv`;
- México: `ciudad-de-mexico/source-csv/tsdem.csv`;
- Bogotá 2015: `bogota/2015/source-xlsx/encuesta 2015 - personas.xlsx`.

No se combinarán ambas piezas en una métrica poblacional hasta demostrar una regla defendible para interpretar `T=0`.

## 14. Próxima tarea científica

La próxima ejecución debe completar, en este orden:

1. hidratar y verificar los objetos del manifiesto;
2. ejecutar los adaptadores sobre microdatos reales y producir QA de esquemas, tiempos, propósitos, ponderadores y duplicados;
3. recuperar variables de diseño muestral para bootstrap; México dispone explícitamente de UPM y estrato de diseño en los microdatos oficiales;
4. reconstruir los universos de no viajeros;
5. calibrar y congelar soporte común estimable `P0^C`;
6. generar `support_diagnostics.csv`, `reference_distributions.csv` y `scalar_compressibility_results.csv`;
7. decidir, sólo con esos resultados, si el Paper I admite `CM_B` o si su conclusión principal es una función `T|P1` acompañada de orden parcial.

## 15. Hipótesis de contribución

La operación de estandarización directa no es nueva y no debe presentarse como tal. La contribución potencial es la combinación de:

- un constructo de conversión entre tiempo de movilidad y participación realizada;
- una función `T|P1` armonizable entre EOD;
- una prueba explícita de cuándo esa función admite compresión escalar;
- separación entre incertidumbre muestral y sensibilidad a población de referencia;
- posibilidad de producir un orden parcial en vez de forzar rankings;
- contraste posterior con accesibilidad potencial, territorio y estructura social.

La afirmación de novedad seguirá siendo provisional hasta cerrar una revisión sistemática específica.