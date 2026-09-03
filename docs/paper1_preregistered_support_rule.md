# Paper I — regla preregistrada de soporte común estimable

**Fecha de congelamiento:** 2026-09-03  
**Estado:** fijada antes de inspeccionar `support_diagnostics.csv` de la ejecución canónica multiciudad.  
**Ciudades primarias:** Santiago 2012, Ciudad de México 2017 y Bogotá 2015.

## 1. Objeto

El estimando confirmatorio primario utiliza `P1`, definido como el número de episodios de actividad fuera del hogar observados durante un persona-día viajero válido, y:

\[
m_c(p)=E_w[T\mid P_1=p,c].
\]

La comparación escalar sólo puede utilizar categorías de `P1` que sean estimables en todas las ciudades. La presencia nominal de una categoría no es suficiente.

## 2. Regla primaria congelada

El soporte confirmatorio común se define como:

\[
P_0^C=\{1,2,\ldots,p^*\},
\]

donde `p*` es el mayor entero consecutivo tal que, para cada `p <= p*` y para **cada una de las tres ciudades**, la celda ciudad × `P1=p` satisface:

\[
n_{eff,Kish}\ge100,
\]

con:

\[
n_{eff,Kish}=\frac{(\sum_i w_i)^2}{\sum_i w_i^2}.
\]

La regla se implementa en `scripts/paper1_protocol.py` y `scripts/support_diagnostics.py`.

### Por qué soporte consecutivo

No se permitirán soportes como `{1,2,3,5}` cuando `P1=4` falla el criterio. Reingresar a categorías de cola después de una brecha introduciría una selección difícil de justificar y facilitaría decisiones post hoc. Por ello el soporte se detiene en la primera categoría que no es comúnmente estimable.

### Por qué `P1=0` no integra el soporte primario

Un persona-día con `T>0` y `P1=0` implica que se observó movilidad sin ningún destino de actividad fuera del hogar. En una tabla de viajes completa esto puede reflejar un diario truncado en su borde temporal, un retorno al hogar sin actividad previa observada o un problema de codificación de propósito. Estos registros se conservarán y reportarán mediante `p1_zero_with_travel`, pero no definirán la función confirmatoria primaria.

## 3. Sensibilidades preregistradas

Se evaluarán exactamente dos reglas adicionales, sin reemplazar la primaria:

- sensibilidad menos exigente: `n_eff,Kish >= 50` en cada ciudad × P1;
- sensibilidad más exigente: `n_eff,Kish >= 200` en cada ciudad × P1.

En ambos casos se mantiene la condición de soporte consecutivo desde `P1=1`.

## 4. Variables que se reportan pero no recortan el soporte primario

Se reportarán por ciudad × P1:

- `n_raw`;
- suma de ponderadores;
- participación ponderada de la celda;
- `n_eff,Kish`.

La participación ponderada no se utilizará como umbral adicional en la especificación primaria. Una categoría rara puede seguir siendo estadísticamente estimable si dispone de suficiente muestra efectiva. La incertidumbre resultante se reflejará posteriormente en el bootstrap y no se resolverá eliminando categorías después de observar los deltas.

## 5. Salvaguardas contra decisiones post hoc

1. El umbral primario `100` y las sensibilidades `50` y `200` no se modificarán después de observar `B_c(H)`, `Delta_ab(H)` o clasificaciones de dominancia.
2. Si el soporte primario contiene un solo nivel de `P1`, la compresibilidad será considerada **mecánicamente trivial** y no sustentará una afirmación de coeficiente escalar.
3. No se interpolarán categorías ausentes dentro del soporte confirmatorio.
4. No se ampliará el soporte mediante comparaciones pareadas para construir un ranking global. Los soportes pareados podrán reportarse sólo como sensibilidad separada.
5. `P1=0,T>0` se reportará como diagnóstico de calidad y permanecerá fuera del soporte confirmatorio primario.

## 6. Secuencia posterior

Una vez disponible la ejecución canónica de etapa 1:

1. verificar QA de adaptadores, propósitos, ponderadores y universo de personas;
2. aplicar mecánicamente la regla anterior a `support_diagnostics.csv`;
3. registrar el `P0^C` resultante y su cobertura ponderada por ciudad;
4. congelar ese soporte en un artefacto versionado;
5. recién entonces estimar referencias `H_c^0`, `B_c(H)`, bootstrap conjunto y envolventes de compresibilidad.

No se calculará un ranking ni un `CM_B` antes de completar esta secuencia.
