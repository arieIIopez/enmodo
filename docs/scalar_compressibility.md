# Compresibilidad escalar del Coeficiente de Movilidad

## Estado

Especificación metodológica para implementación y preregistro. Esta nota formaliza cuándo la relación tiempo–participación puede resumirse legítimamente mediante un escalar y cuándo debe conservarse como perfil funcional u orden parcial.

## 1. Objeto primario

Para cada ciudad `c`, el estimando primario es

\[
m_c(r)=E[T\mid R=r,c],
\]

donde `T` es tiempo diario de movilidad (min/persona-día) y `R` es participación urbana realizada. Para dos ciudades `a` y `b`:

\[
d_{ab}(r)=m_a(r)-m_b(r).
\]

La comparación funcional precede a cualquier índice o normalización.

## 2. Escalarización bajo referencia común

Sea `R0` el soporte común y `H` una distribución de referencia común sobre dicho soporte:

\[
B_c(H)=\int_{R_0}m_c(r)\,dH(r),
\]

\[
\Delta_{ab}(H)=B_a(H)-B_b(H)=\int_{R_0}d_{ab}(r)\,dH(r).
\]

`B_c(H)` se expresa en minutos/persona-día y es la síntesis escalar primaria. Un índice adimensional del tipo

\[
CM_{B,c}=\frac{B_{ref}(H)}{B_c(H)}
\]

es secundario y sólo debe reportarse cuando se demuestre compresibilidad escalar.

## 3. La compresibilidad es relacional

Toda ciudad puede producir un escalar una vez escogido `H`. La cuestión científica no es si existe `B_c(H)`, sino si la comparación entre ciudades es robusta frente a referencias admisibles.

Sea `𝓗` una familia explícita de distribuciones de referencia. Definimos el sobre robusto:

\[
\mathcal D_{ab}(\mathcal H)=
[\inf_{H\in\mathcal H}\Delta_{ab}(H),\;\sup_{H\in\mathcal H}\Delta_{ab}(H)].
\]

Si menor tiempo para igual participación representa mejor desempeño y `δ_T>0` es la tolerancia de equivalencia práctica:

- `a` domina robustamente a `b` si `sup_H Δ_ab(H) < -δ_T`;
- existe equivalencia práctica robusta si todo `Δ_ab(H)` pertenece a `[-δ_T, δ_T]`;
- `b` domina robustamente a `a` si `inf_H Δ_ab(H) > δ_T`;
- en cualquier otro caso la comparación es dependiente de referencia y no admite un orden escalar robusto.

## 4. Proposición de invariancia

Si `𝓗` contiene todas las distribuciones de probabilidad sobre `R0`, el signo de `Δ_ab(H)` es invariante para todo `H` si y sólo si `d_ab(r)` conserva el mismo signo casi en todas partes de `R0`, admitiendo igualdad.

Si `d_ab(r)` cambia de signo y la familia de referencias puede asignar masa positiva a regiones de signos opuestos, existen referencias capaces de invertir el orden escalar.

**Cautela:** para una familia `𝓗` restringida, un cruce de las curvas `m_a(r)` y `m_b(r)` no implica necesariamente una inversión del orden. La conclusión depende de la masa que las referencias admisibles puedan asignar a las regiones del soporte.

## 5. Familia finita y envolvente convexa

La implementación debe usar un conjunto finito, explícito y preregistrado de referencias `H_1,…,H_K`. La familia admisible se define como su envolvente convexa:

\[
\mathcal H=\left\{\sum_{k=1}^K\omega_kH_k:\omega_k\ge0,\;\sum_k\omega_k=1\right\}.
\]

Como `Δ_ab(H)` es lineal en `H`, sus máximos y mínimos sobre `𝓗` ocurren en las referencias extremas `H_k`. Por tanto, evaluar los `K` escenarios basta para conocer el sobre robusto de todas sus mezclas convexas.

Esta propiedad debe implementarse como prueba principal de sensibilidad de referencia: no se seleccionará ex post la referencia que produzca el orden deseado.

## 6. Separar incertidumbre estructural de estadística

Para cada `H_k`, estimar mediante bootstrap compatible con el diseño muestral:

\[
[L_{ab}(H_k),U_{ab}(H_k)].
\]

Criterios confirmatorios:

- dominancia robusta de `a`: `max_k U_ab(H_k) < -δ_T`;
- equivalencia robusta: `min_k L_ab(H_k) >= -δ_T` y `max_k U_ab(H_k) <= δ_T`;
- dominancia robusta de `b`: `min_k L_ab(H_k) > δ_T`.

Cuando no se satisfaga ninguno:

1. **Incomparabilidad estructural:** la clasificación puntual cambia entre referencias `H_k`.
2. **Indeterminación estadística:** la clasificación puntual es estable entre referencias, pero los intervalos muestrales cruzan los umbrales.
3. **Ambas:** hay sensibilidad de referencia y de muestreo simultáneamente.

Estas categorías no deben colapsarse en la etiqueta genérica de “no significativo”.

## 7. Más de dos ciudades: orden parcial

Para `C` ciudades se estiman todas las comparaciones pareadas sobre soporte común apropiado. La salida principal es un grafo de dominancia robusta:

- nodo = ciudad;
- arista `a → b` = `a` requiere robustamente menos tiempo que `b` para una referencia común de participación, dentro de `𝓗` y `δ_T`;
- ausencia de arista = equivalencia o incomparabilidad, que debe distinguirse explícitamente.

No se forzará un ranking total. `CM_B` global sólo se reportará si las relaciones pareadas producen una estructura suficientemente estable y coherente.

## 8. Relación con G6b

G6b debe reinterpretarse como la primera prueba empírica de compresibilidad escalar. El hallazgo metodológicamente relevante es que algunas comparaciones presentan separaciones estandarizadas ampliamente mayores que otras, mientras las comparaciones cercanas al umbral de equivalencia pueden cambiar de clasificación al variar `H*`.

La siguiente ejecución debe transformar G6b desde una sensibilidad informal a `H*` en una estimación completa de `𝓓_ab(𝓗)` para todos los pares.

## 9. Relación con Tier A

Tier A no define el coeficiente. Su función es examinar mecanismos que puedan explicar la relación `T|R` observada.

- **Tier A.1:** impedancia geométrica / geometría del espacio de oportunidades. Evidencia de validez de constructo; no es accesibilidad confirmatoria por transporte.
- **Tier A.2:** accesibilidad basada en red histórica. Prueba mecanística confirmatoria cuando los insumos históricos sean defendibles.

La secuencia analítica es: relación funcional `T|R` → prueba de compresibilidad → orden robusto / `B(H)` → contraste mecanístico Tier A.

## 10. Decisiones para el siguiente experimento

Antes de volver a estimar G6b se debe congelar:

1. definición operacional de `R` y `T`;
2. soporte común `R0` y reglas de trimming;
3. conjunto de referencias extremas `H_k`;
4. tolerancia práctica `δ_T` y su justificación sustantiva;
5. procedimiento bootstrap y número de réplicas;
6. reglas exactas de dominancia, equivalencia, incomparabilidad e indeterminación;
7. política de publicación de `CM_B` cuando la compresión no sea robusta.

## 11. Hipótesis de novedad

La literatura de accesibilidad discute el compromiso entre rigor e interpretabilidad; la literatura de indicadores compuestos documenta la sensibilidad a normalización, ponderación y agregación; y los métodos de ordenamiento robusto admiten órdenes parciales bajo conjuntos de supuestos. La hipótesis de contribución específica de este programa es tratar la **posibilidad de comprimir una relación funcional tiempo–participación en un escalar como una propiedad empírica que debe demostrarse**, manteniendo unidades físicas y separando incertidumbre muestral de incertidumbre de referencia.

Esta novedad debe considerarse provisional hasta completar la revisión sistemática de literatura.
