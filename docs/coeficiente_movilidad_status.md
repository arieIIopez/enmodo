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

El ejercicio G6b previo pasa a interpretarse como primera evidencia de sensibilidad de referencia / compresibilidad. Debe reejecutarse bajo la especificación actual:

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

## 9. Código creado en esta fase

- `docs/scalar_compressibility.md`: especificación matemática y reglas de decisión.
- `scripts/scalar_compressibility.py`: escalarización, deltas pareados, sobre robusto, clasificación y aristas de dominancia.
- `scripts/reference_distributions.py`: referencias observadas por ciudad, mezcla igualitaria, stress test uniforme y cobertura del soporte.
- `scripts/support_diagnostics.py`: diagnóstico de soporte y tamaño efectivo de Kish; sin thresholds implícitos.
- `scripts/mobility_function.py`: estimación directa de `m_c(p)` y tasa separada de no viajeros.
- `tests/test_scalar_compressibility.py`.
- `tests/test_reference_distributions.py`.
- `tests/test_mobility_function.py`.

Los tests sintéticos están versionados, pero esta nota no debe interpretarse como evidencia de que un workflow CI haya sido ejecutado.

## 10. Próxima tarea científica

La próxima ejecución no debe comenzar por Tier A. Debe comenzar por reconstruir o localizar las tablas persona-día utilizadas en G6/G6b para Santiago 2012, Ciudad de México 2017 y Bogotá, aplicar la nueva especificación directa y generar tres productos congelados:

1. `support_diagnostics.csv`;
2. `reference_distributions.csv`;
3. `scalar_compressibility_results.csv` con bootstrap y clasificación pareada.

Una vez cerrados esos resultados se decide si el Paper I puede sostener una representación escalar única o si su resultado principal debe ser la función `T|P1` más un orden parcial.

## 11. Hipótesis de contribución

La operación de estandarización directa no es nueva y no debe presentarse como tal. La contribución potencial es la combinación de:

- un constructo de conversión entre tiempo de movilidad y participación realizada;
- una función `T|P1` armonizable entre EOD;
- una prueba explícita de cuándo esa función admite compresión escalar;
- separación entre incertidumbre muestral y sensibilidad a población de referencia;
- posibilidad de producir un orden parcial en vez de forzar rankings;
- contraste posterior con accesibilidad potencial, territorio y estructura social.

La afirmación de novedad seguirá siendo provisional hasta cerrar una revisión sistemática específica.