from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components

from scripts.mobility_coefficient import build_gap_table, build_indicator_table, build_person_day, infer_columns

st.set_page_config(page_title="ENMODO Territorial", page_icon="🗺️", layout="wide")


CSS = """
<style>
.main {background: linear-gradient(180deg,#0b1220 0%, #111827 100%); color: #e5e7eb;}
h1,h2,h3 {color:#f9fafb !important;}
[data-testid="stSidebar"] {background:#0f172a;}
.metric-card {
    background: #1f2937;
    border: 1px solid #374151;
    border-radius: 14px;
    padding: 16px;
    box-shadow: 0 8px 24px rgba(0,0,0,.25);
}
.metric-title {font-size: .9rem; color:#9ca3af;}
.metric-value {font-size: 1.8rem; font-weight: 700; color: #93c5fd;}
.small-note {color:#9ca3af; font-size:.85rem;}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def is_lfs_pointer(path: Path) -> bool:
    try:
        first_line = path.read_text(encoding="utf-8", errors="ignore").splitlines()[0]
    except Exception:
        return False
    return first_line.startswith("version https://git-lfs.github.com/spec/v1")


def find_available_trip_files() -> List[Path]:
    files = sorted(Path(".").glob("**/csv/viajes_personas_*.csv"))
    files += sorted(Path(".").glob("**/output-csv/viajes_personas_*.csv"))
    return [f for f in files if f.is_file() and not is_lfs_pointer(f)]


def infer_city_year(path: Path) -> Dict[str, str]:
    parts = path.parts
    city = parts[0] if len(parts) > 0 else "unknown"
    year = "unknown"
    for p in parts:
        if p.isdigit() and len(p) == 4:
            year = p
            break
    return {"city": city, "year": year}


def normalize_sex(value: object) -> str:
    if pd.isna(value):
        return "sin_dato"
    s = str(value).strip().lower()
    if s in {"m", "masculino", "hombre", "male", "1"}:
        return "hombre"
    if s in {"f", "femenino", "mujer", "female", "2"}:
        return "mujer"
    return "otro"


def weighted_mean(df: pd.DataFrame, value_col: str, weight_col: Optional[str]) -> float:
    x = pd.to_numeric(df[value_col], errors="coerce").fillna(0)
    if not weight_col or weight_col not in df.columns:
        return float(x.mean()) if len(x) else 0.0
    w = pd.to_numeric(df[weight_col], errors="coerce").fillna(0)
    den = w.sum()
    return float((x * w).sum() / den) if den else 0.0


def build_od(df: pd.DataFrame) -> Optional[pd.DataFrame]:
    origin_candidates = ["ZonaOrigen", "zona_o", "zat_origen", "ZAT_ORIGEN", "origin_zone_id"]
    dest_candidates = ["ZonaDestino", "zona_d", "zat_destino", "ZAT_DESTINO", "dest_zone_id"]
    weight_candidates = ["PONDERADOR_CALIBRADO_VIAJES", "fe_via", "factor_x", "f_exp_x", "wcal0_x", "weight_trip"]

    o_col = next((c for c in origin_candidates if c in df.columns), None)
    d_col = next((c for c in dest_candidates if c in df.columns), None)
    w_col = next((c for c in weight_candidates if c in df.columns), None)

    if not o_col or not d_col:
        return None

    work = df[[o_col, d_col] + ([w_col] if w_col else [])].copy()
    work = work[(work[o_col].notna()) & (work[d_col].notna()) & (work[o_col] != work[d_col])]
    if w_col:
        work[w_col] = pd.to_numeric(work[w_col], errors="coerce").fillna(0)
        out = work.groupby([o_col, d_col], as_index=False)[w_col].sum().sort_values(w_col, ascending=False)
        out.columns = ["origen", "destino", "n_viajes"]
    else:
        out = work.groupby([o_col, d_col], as_index=False).size().sort_values("size", ascending=False)
        out.columns = ["origen", "destino", "n_viajes"]
    return out.head(20)


def build_geojson_points(df: pd.DataFrame, max_points: int = 5000) -> Optional[dict]:
    lon_candidates = ["LONGITUD_ORIGEN", "OrigenCoordX", "co_o_x", "origin_lon", "lon_origen", "LON_ORIGEN"]
    lat_candidates = ["LATITUD_ORIGEN", "OrigenCoordY", "co_o_y", "origin_lat", "lat_origen", "LAT_ORIGEN"]

    lon_col = next((c for c in lon_candidates if c in df.columns), None)
    lat_col = next((c for c in lat_candidates if c in df.columns), None)
    if not lon_col or not lat_col:
        return None

    geo = df[[lon_col, lat_col, "sex_group"]].copy()
    geo[lon_col] = pd.to_numeric(geo[lon_col], errors="coerce")
    geo[lat_col] = pd.to_numeric(geo[lat_col], errors="coerce")
    geo = geo[(geo[lon_col].between(-180, 180)) & (geo[lat_col].between(-90, 90))]
    if geo.empty:
        return None

    geo = geo.head(max_points)
    features = []
    for _, row in geo.iterrows():
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(row[lon_col]), float(row[lat_col])]},
                "properties": {"sex_group": row["sex_group"]},
            }
        )
    return {"type": "FeatureCollection", "features": features}


st.title("🗺️ Dashboard Territorial de Movilidad")
st.caption("Estilo ejecutivo inspirado en paneles de movilidad urbana. Incluye enfoque de género y coeficiente de movilidad.")

trip_files = find_available_trip_files()

if not trip_files:
    st.warning("No se encontraron CSV materializados. Ejecuta `git lfs pull` para descargar datasets y vuelve a abrir el dashboard.")
    st.stop()

file_options = {f"{infer_city_year(f)['city']} · {infer_city_year(f)['year']} ({f})": f for f in trip_files}
selected_label = st.sidebar.selectbox("Ciudad / Año", list(file_options.keys()))
selected_file = file_options[selected_label]
mapbox_token = st.sidebar.text_input("Mapbox token", value="", type="password", help="Pega tu token público de Mapbox aquí.")
mapbox_style = st.sidebar.text_input(
    "Map style",
    value="mapbox://styles/mapbox/dark-v11",
    help="Puedes usar un estilo de Mapbox o un style URL propio.",
)

raw = pd.read_csv(selected_file)
config = infer_columns(raw)
raw["sex_group"] = raw[config.sex].map(normalize_sex)

sex_filter = st.sidebar.multiselect("Sexo", ["hombre", "mujer", "otro", "sin_dato"], default=["hombre", "mujer"])
filtered = raw[raw["sex_group"].isin(sex_filter)].copy()

# KPIs
trip_weight_col = next((c for c in ["PONDERADOR_CALIBRADO_VIAJES", "fe_via", "factor_x", "f_exp_x", "wcal0_x", "weight_trip"] if c in filtered.columns), None)
total_trips = weighted_mean(filtered.assign(one=1), "one", trip_weight_col) * len(filtered)
avg_duration = weighted_mean(filtered, config.duration_min, trip_weight_col)
unique_people = filtered[config.person_id].nunique()
trips_per_person = (total_trips / unique_people) if unique_people else 0

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(f"<div class='metric-card'><div class='metric-title'>Viajes ponderados (aprox)</div><div class='metric-value'>{total_trips:,.0f}</div></div>", unsafe_allow_html=True)
with c2:
    st.markdown(f"<div class='metric-card'><div class='metric-title'>Duración media (min)</div><div class='metric-value'>{avg_duration:,.1f}</div></div>", unsafe_allow_html=True)
with c3:
    st.markdown(f"<div class='metric-card'><div class='metric-title'>Viajes por persona</div><div class='metric-value'>{trips_per_person:,.2f}</div></div>", unsafe_allow_html=True)

# gender charts
left, right = st.columns((1, 1))
with left:
    trips_by_sex = filtered.groupby("sex_group", as_index=False).size().rename(columns={"size": "viajes"})
    fig = px.bar(trips_by_sex, x="sex_group", y="viajes", color="sex_group", title="Viajes por sexo")
    st.plotly_chart(fig, use_container_width=True)

with right:
    dur = pd.to_numeric(filtered[config.duration_min], errors="coerce").dropna()
    fig = px.histogram(dur, nbins=40, title="Distribución de duración de viaje (min)")
    st.plotly_chart(fig, use_container_width=True)

# mobility coefficient tables
meta = infer_city_year(selected_file)
year_num = int(meta["year"]) if str(meta["year"]).isdigit() else 0
person_day = build_person_day(filtered, config)
indicators = build_indicator_table(person_day, meta["city"], year_num)
gaps = build_gap_table(indicators)

st.subheader("Coeficiente de Movilidad (11 indicadores)")
st.dataframe(indicators, use_container_width=True, hide_index=True)

st.subheader("Brecha de movilidad Mujer - Hombre")
st.dataframe(gaps, use_container_width=True, hide_index=True)

# OD flows
st.subheader("Top flujos Origen-Destino")
od = build_od(filtered)
if od is None or od.empty:
    st.info("No se detectaron columnas de zonas origen/destino para esta fuente.")
else:
    fig = px.bar(od.head(15), x="n_viajes", y=od.head(15).apply(lambda r: f"{r['origen']} → {r['destino']}", axis=1), orientation="h", title="Top 15 flujos OD")
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Mapa de viajes (Mapbox GL JS)")
geojson = build_geojson_points(filtered)
if geojson is None:
    st.info("No se detectaron columnas de coordenadas válidas para renderizar el mapa.")
else:
    if not mapbox_token:
        st.warning("Falta token de Mapbox. Carga tu token en el panel lateral para habilitar el mapa.")

    map_html = f"""
    <link href='https://api.mapbox.com/mapbox-gl-js/v3.22.0/mapbox-gl.css' rel='stylesheet' />
    <script src='https://api.mapbox.com/mapbox-gl-js/v3.22.0/mapbox-gl.js'></script>
    <div id='mapbox-map' style='width: 100%; height: 560px; border-radius: 12px;'></div>
    <script>
      mapboxgl.accessToken = {json.dumps(mapbox_token)};
      const geojson = {json.dumps(geojson)};
      const map = new mapboxgl.Map({{
        container: 'mapbox-map',
        style: {json.dumps(mapbox_style)},
        center: [-74.07, 4.65],
        zoom: 10,
        attributionControl: true
      }});

      map.addControl(new mapboxgl.NavigationControl(), 'top-right');
      map.on('load', () => {{
        map.addSource('trips-points', {{ type: 'geojson', data: geojson }});
        map.addLayer({{
          id: 'trips-points-layer',
          type: 'circle',
          source: 'trips-points',
          paint: {{
            'circle-radius': 3.5,
            'circle-opacity': 0.75,
            'circle-color': [
              'match',
              ['get', 'sex_group'],
              'hombre', '#60a5fa',
              'mujer', '#f472b6',
              'otro', '#fbbf24',
              '#9ca3af'
            ]
          }}
        }});

        const bounds = new mapboxgl.LngLatBounds();
        geojson.features.forEach(f => bounds.extend(f.geometry.coordinates));
        if (!bounds.isEmpty()) map.fitBounds(bounds, {{ padding: 40, duration: 0 }});
      }});
    </script>
    """
    components.html(map_html, height=590)

st.markdown("<p class='small-note'>Tip: para una experiencia completa usa salidas `viajes_personas_*` materializadas con Git LFS.</p>", unsafe_allow_html=True)
