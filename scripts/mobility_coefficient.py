"""Calculo del Coeficiente de Movilidad con perspectiva de genero.

Este script implementa una version operativa del enfoque de grupos
(A1, A2, A3, B1, B2, B3, C, D) y los 11 indicadores usados en ENMODO.

Uso:
  python scripts/mobility_coefficient.py \
    --input path/a/viajes_personas.csv \
    --output-dir outputs/
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd


INDICATORS: List[Tuple[int, str]] = [
    (1, "(A1+A2+A3)/P"),
    (2, "A1/P"),
    (3, "(A2+A3)/P"),
    (4, "B3/P"),
    (5, "B1/P"),
    (6, "B2/P"),
    (7, "C/P"),
    (8, "D/P"),
    (9, "(C+D)/P"),
    (10, "<=15 min"),
    (11, "2 viajes diarios"),
]

SEX_ALIASES = ["sexo", "SEXO", "Sexo", "sex", "gender", "Genero", "género"]
TRIP_WEIGHT_ALIASES = ["PONDERADOR_CALIBRADO_VIAJES", "fe_via", "factor_x", "f_exp_x", "wcal0_x", "weight_trip"]
PERSON_WEIGHT_ALIASES = ["PONDERADOR_CALIBRADO_PERSONAS", "fe_pess", "factor", "f_exp", "wcal0", "weight_person"]
TRIP_ID_ALIASES = ["Viaje", "id_viaje", "id_viaje_u", "id_via", "n_viag", "trip_id"]
PERSON_ID_ALIASES = ["Persona", "id_persona", "id_pess", "nnper", "NUMERO_PERSONA", "person_id"]
DURATION_ALIASES = ["duracion_minutos", "TiempoViaje", "duracao", "duracion", "duration_min"]
TRIPS_PER_PERSON_ALIASES = ["n_viajes"]


@dataclass
class ColumnConfig:
    person_id: str
    sex: str
    duration_min: str
    trips_per_person: Optional[str]
    person_weight: Optional[str]


def _first_existing(columns: Iterable[str], aliases: Iterable[str]) -> Optional[str]:
    colset = set(columns)
    for alias in aliases:
        if alias in colset:
            return alias
    return None


def infer_columns(df: pd.DataFrame) -> ColumnConfig:
    person_id = _first_existing(df.columns, PERSON_ID_ALIASES)
    sex = _first_existing(df.columns, SEX_ALIASES)
    duration_min = _first_existing(df.columns, DURATION_ALIASES)
    trips_per_person = _first_existing(df.columns, TRIPS_PER_PERSON_ALIASES)
    person_weight = _first_existing(df.columns, PERSON_WEIGHT_ALIASES)

    missing = []
    if not person_id:
        missing.append("person_id")
    if not sex:
        missing.append("sex")
    if not duration_min:
        missing.append("duration_min")
    if missing:
        raise ValueError(f"No fue posible inferir columnas requeridas: {', '.join(missing)}")

    return ColumnConfig(
        person_id=person_id,
        sex=sex,
        duration_min=duration_min,
        trips_per_person=trips_per_person,
        person_weight=person_weight,
    )


def normalize_sex(value: object) -> str:
    if pd.isna(value):
        return "sin_dato"
    s = str(value).strip().lower()
    if s in {"m", "masculino", "hombre", "male", "1"}:
        return "hombre"
    if s in {"f", "femenino", "mujer", "female", "2"}:
        return "mujer"
    return "otro"


def build_person_day(df: pd.DataFrame, config: ColumnConfig) -> pd.DataFrame:
    work = df.copy()
    work["sex_group"] = work[config.sex].map(normalize_sex)
    work["duration_min"] = pd.to_numeric(work[config.duration_min], errors="coerce")
    work = work[work["duration_min"].notna()].copy()

    if config.trips_per_person and config.trips_per_person in work.columns:
        work["trip_counter"] = pd.to_numeric(work[config.trips_per_person], errors="coerce").fillna(0)
        agg_trips = ("trip_counter", "max")
    else:
        work["trip_counter"] = 1
        agg_trips = ("trip_counter", "sum")

    if config.person_weight and config.person_weight in work.columns:
        work["person_weight"] = pd.to_numeric(work[config.person_weight], errors="coerce")
    else:
        work["person_weight"] = 1.0

    person_day = (
        work.groupby([config.person_id, "sex_group"], dropna=False)
        .agg(
            n_viajes=agg_trips,
            tiempo_total=("duration_min", "sum"),
            fe=("person_weight", "max"),
        )
        .reset_index()
    )
    return person_day[(person_day["n_viajes"] >= 1) & (person_day["tiempo_total"] >= 0)].copy()


def _regression_line(df: pd.DataFrame) -> Tuple[float, float, float]:
    x = df["n_viajes"].astype(float).values
    y = df["tiempo_total"].astype(float).values
    if len(df) < 2 or np.allclose(x, x[0]):
        slope = 0.0
        intercept = float(np.nanmedian(y)) if len(y) else 0.0
    else:
        slope, intercept = np.polyfit(x, y, 1)
    median_y = float(np.nanmedian(y)) if len(y) else 0.0
    return float(slope), float(intercept), median_y


def assign_groups(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    slope, intercept, median_y = _regression_line(data)

    if slope == 0:
        x0 = float(np.nanmedian(data["n_viajes"]))
    else:
        x0 = (median_y - intercept) / slope

    line_y = slope * data["n_viajes"] + intercept
    data["group"] = ""

    one_trip = data["n_viajes"] == 1
    data.loc[one_trip & (data["tiempo_total"] < line_y), "group"] = "c"
    data.loc[one_trip & (data["tiempo_total"] >= line_y), "group"] = "d"

    multi = data["n_viajes"] > 1
    low_x = multi & (data["n_viajes"] < x0)
    high_x = multi & (data["n_viajes"] >= x0)

    data.loc[high_x & (data["tiempo_total"] >= median_y), "group"] = "b2"
    data.loc[high_x & (data["tiempo_total"] < median_y) & (data["tiempo_total"] >= line_y), "group"] = "b1"
    data.loc[high_x & (data["tiempo_total"] < line_y), "group"] = "a1"

    data.loc[low_x & (data["tiempo_total"] < median_y) & (data["tiempo_total"] < line_y), "group"] = "a2"
    data.loc[low_x & (data["tiempo_total"] >= median_y) & (data["tiempo_total"] < line_y), "group"] = "a3"
    data.loc[low_x & (data["tiempo_total"] >= line_y), "group"] = "b3"

    data.loc[data["group"] == "", "group"] = "d"
    return data


def _sum_group(df: pd.DataFrame, group: str) -> float:
    return float(df.loc[df["group"] == group, "fe"].sum())


def calculate_11_indicators(df: pd.DataFrame) -> Dict[int, float]:
    pop_total = float(df["fe"].sum())
    if pop_total <= 0:
        return {idx: 0.0 for idx, _ in INDICATORS}

    a1 = _sum_group(df, "a1")
    a2 = _sum_group(df, "a2")
    a3 = _sum_group(df, "a3")
    b1 = _sum_group(df, "b1")
    b2 = _sum_group(df, "b2")
    b3 = _sum_group(df, "b3")
    c = _sum_group(df, "c")
    d = _sum_group(df, "d")

    values = {
        1: (a1 + a2 + a3) / pop_total,
        2: a1 / pop_total,
        3: (a2 + a3) / pop_total,
        4: b3 / pop_total,
        5: b1 / pop_total,
        6: b2 / pop_total,
        7: c / pop_total,
        8: d / pop_total,
        9: (c + d) / pop_total,
        10: float(df.loc[df["tiempo_total"] <= 15, "fe"].sum()) / pop_total,
        11: float(df.loc[df["n_viajes"] == 2, "fe"].sum()) / pop_total,
    }
    return values


def build_indicator_table(person_day: pd.DataFrame, city: str, year: int) -> pd.DataFrame:
    out_rows = []
    groups = {
        "total": person_day,
        "hombre": person_day[person_day["sex_group"] == "hombre"],
        "mujer": person_day[person_day["sex_group"] == "mujer"],
    }

    for sex_group, subset in groups.items():
        if subset.empty:
            values = {idx: 0.0 for idx, _ in INDICATORS}
        else:
            tagged = assign_groups(subset)
            values = calculate_11_indicators(tagged)

        for idx, name in INDICATORS:
            out_rows.append(
                {
                    "city": city,
                    "year": year,
                    "sex_group": sex_group,
                    "indicator_id": idx,
                    "indicator_name": name,
                    "value": round(float(values[idx]), 6),
                }
            )

    return pd.DataFrame(out_rows)


def build_gap_table(indicator_table: pd.DataFrame) -> pd.DataFrame:
    pivot = indicator_table.pivot_table(
        index=["city", "year", "indicator_id", "indicator_name"],
        columns="sex_group",
        values="value",
        aggfunc="first",
    ).reset_index()

    pivot["female_value"] = pivot.get("mujer", 0.0)
    pivot["male_value"] = pivot.get("hombre", 0.0)
    pivot["gap_abs"] = pivot["female_value"] - pivot["male_value"]
    pivot["gap_ratio"] = np.where(pivot["male_value"] == 0, np.nan, pivot["female_value"] / pivot["male_value"])

    return pivot[["city", "year", "indicator_id", "indicator_name", "female_value", "male_value", "gap_abs", "gap_ratio"]]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calcula Coeficiente de Movilidad con enfoque de genero")
    parser.add_argument("--input", required=True, help="CSV viajes_personas")
    parser.add_argument("--output-dir", required=True, help="Carpeta de salida")
    parser.add_argument("--city", default="unknown_city", help="Nombre de ciudad")
    parser.add_argument("--year", type=int, default=0, help="Anio de referencia")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.makedirs(args.output_dir, exist_ok=True)

    df = pd.read_csv(args.input)
    config = infer_columns(df)
    person_day = build_person_day(df, config)

    indicators = build_indicator_table(person_day, city=args.city, year=args.year)
    gaps = build_gap_table(indicators)

    indicators_path = os.path.join(args.output_dir, "fact_mobility_coefficient.csv")
    gaps_path = os.path.join(args.output_dir, "fact_mobility_gap.csv")

    indicators.to_csv(indicators_path, index=False)
    gaps.to_csv(gaps_path, index=False)

    print(f"OK -> {indicators_path}")
    print(f"OK -> {gaps_path}")


if __name__ == "__main__":
    main()
