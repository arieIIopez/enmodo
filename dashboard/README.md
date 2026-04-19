# Dashboard ENMODO Territorial

Aplicación Streamlit para explorar movilidad territorial con:

- KPIs de viajes y duración.
- Enfoque de género (hombre/mujer/total).
- Coeficiente de Movilidad (11 indicadores).
- Brechas mujer-hombre.
- Top flujos origen-destino.
- Mapa interactivo con **Mapbox GL JS v3.22.0**.

## Ejecutar

```bash
streamlit run dashboard/app.py
```

Luego, en la barra lateral del dashboard:

- pega tu `Mapbox token`,
- define el `Map style` (ejemplo: `mapbox://styles/mapbox/dark-v11`).

## Dependencias

- streamlit
- pandas
- numpy
- plotly
