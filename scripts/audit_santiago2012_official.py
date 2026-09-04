#!/usr/bin/env python3
"""Aggregate audit of the official SECTRA Santiago EOD 2012 Access database.

The script uses ``mdb-export`` to read selected tables from the official ACCDB,
then emits aggregate QA only. It establishes day-domain, weights, identifiers,
time semantics and purpose coding before a confirmatory Paper I adapter is
frozen. No person-level microdata are written to the output directory.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd


TABLES = [
    "Hogar",
    "Persona",
    "Viaje",
    "TipoDia",
    "Temporada",
    "Proposito",
    "PropositoAgregado",
    "CódigoTiempo",
    "NoViaja",
]


def _export(db: Path, table: str) -> pd.DataFrame:
    raw = subprocess.check_output(
        ["mdb-export", str(db), table],
        stderr=subprocess.STDOUT,
        timeout=180,
    )
    return pd.read_csv(io.BytesIO(raw), dtype=str, low_memory=False)


def _num(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype("string").str.strip().str.replace(",", ".", regex=False),
        errors="coerce",
    )


def _write_value_counts(frame: pd.DataFrame, columns: list[str], path: Path) -> None:
    rows: list[dict[str, object]] = []
    for col in columns:
        if col not in frame.columns:
            continue
        vc = frame[col].astype("string").fillna("<MISSING>").value_counts(dropna=False)
        for value, n in vc.head(500).items():
            rows.append({"column": col, "value": str(value), "n": int(n)})
    pd.DataFrame(rows).to_csv(path, index=False)


def _clock_to_minutes(series: pd.Series) -> pd.Series:
    """Best-effort parser used for QA only; reported TiempoViaje remains untouched."""
    text = series.astype("string").str.strip()
    extracted = text.str.extract(r"(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?$")
    h = pd.to_numeric(extracted["h"], errors="coerce")
    m = pd.to_numeric(extracted["m"], errors="coerce")
    s = pd.to_numeric(extracted["s"], errors="coerce").fillna(0)
    valid = h.between(0, 24) & m.between(0, 59) & s.between(0, 59)
    valid &= ~((h == 24) & ((m != 0) | (s != 0)))
    out = h * 60 + m + s / 60
    return out.where(valid)


def run(database: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not database.exists():
        raise FileNotFoundError(database)

    data = {table: _export(database, table) for table in TABLES}
    hh = data["Hogar"]
    persons = data["Persona"]
    trips = data["Viaje"]

    catalogs = []
    for table in ["TipoDia", "Temporada", "Proposito", "PropositoAgregado", "CódigoTiempo", "NoViaja"]:
        frame = data[table].copy()
        frame.insert(0, "catalog", table)
        catalogs.append(frame)
    pd.concat(catalogs, ignore_index=True, sort=False).to_csv(
        output_dir / "catalog_values.csv", index=False
    )

    _write_value_counts(
        hh,
        ["TipoDia", "DiaAsig", "Temporada", "Comuna", "Sector"],
        output_dir / "household_domain_counts.csv",
    )
    _write_value_counts(
        persons,
        ["NoViaja", "Viajes", "Factor_LaboralNormal", "Factor_SábadoNormal", "Factor_DomingoNormal"],
        output_dir / "person_domain_counts.csv",
    )
    _write_value_counts(
        trips,
        ["Proposito", "PropositoAgregado", "CódigoTiempo", "Periodo", "TiempoMedio"],
        output_dir / "trip_semantic_counts.csv",
    )

    # Key integrity.
    person_key = persons[["Hogar", "Persona"]].astype("string").agg("::".join, axis=1)
    trip_person_key = trips[["Hogar", "Persona"]].astype("string").agg("::".join, axis=1)
    trip_key = trips[["Hogar", "Persona", "Viaje"]].astype("string").agg("::".join, axis=1)

    # Expansion candidates.
    person_weight_rows = []
    for col in [
        "Factor_LaboralNormal",
        "Factor_SábadoNormal",
        "Factor_DomingoNormal",
        "Factor_LaboralEstival",
        "Factor_FindesemanaEstival",
        "Factor",
    ]:
        if col not in persons.columns:
            continue
        x = _num(persons[col])
        person_weight_rows.append(
            {
                "column": col,
                "sample_rows": int(len(x)),
                "n_nonmissing": int(x.notna().sum()),
                "n_positive": int((x > 0).sum()),
                "sum": float(x.sum(skipna=True)),
                "mean_nonmissing": float(x.mean(skipna=True)) if x.notna().any() else None,
                "min_nonmissing": float(x.min(skipna=True)) if x.notna().any() else None,
                "max_nonmissing": float(x.max(skipna=True)) if x.notna().any() else None,
            }
        )
    pd.DataFrame(person_weight_rows).to_csv(output_dir / "person_weight_candidates.csv", index=False)

    household_weight_rows = []
    if "Factor" in hh.columns:
        x = _num(hh["Factor"])
        for tipo, grp_idx in hh.groupby("TipoDia", dropna=False).groups.items():
            z = x.loc[grp_idx]
            household_weight_rows.append(
                {
                    "TipoDia": str(tipo),
                    "sample_households": int(len(grp_idx)),
                    "factor_sum": float(z.sum(skipna=True)),
                    "factor_nonmissing": int(z.notna().sum()),
                }
            )
    pd.DataFrame(household_weight_rows).to_csv(
        output_dir / "household_weight_by_tipodia.csv", index=False
    )

    # Join household day assignment to persons without changing row count.
    hh_domain = hh[["Hogar", "TipoDia", "DiaAsig", "Temporada"]].copy()
    if hh_domain.duplicated("Hogar").any():
        raise ValueError("Hogar table contains duplicate Hogar IDs")
    pj = persons.merge(hh_domain, on="Hogar", how="left", validate="many_to_one")
    if len(pj) != len(persons) or pj["TipoDia"].isna().any():
        raise ValueError("Person-to-household day-domain join is incomplete")

    person_labor = _num(pj["Factor_LaboralNormal"])
    labor_by_tipodia = (
        pj.assign(_factor_labor=person_labor)
        .groupby(["TipoDia", "Temporada"], dropna=False)
        .agg(
            sample_persons=("Persona", "size"),
            factor_labor_nonmissing=("_factor_labor", lambda x: int(x.notna().sum())),
            factor_labor_positive=("_factor_labor", lambda x: int((x > 0).sum())),
            factor_labor_sum=("_factor_labor", "sum"),
        )
        .reset_index()
    )
    labor_by_tipodia.to_csv(output_dir / "labor_factor_by_household_domain.csv", index=False)

    # Traveller population under the LaboralNormal weight candidate.
    travelling_ids = set(trip_person_key.astype(str))
    pids = set(person_key.astype(str))
    orphan_trip_persons = travelling_ids.difference(pids)
    if orphan_trip_persons:
        raise ValueError(f"Trip persons absent from Persona table; examples={list(orphan_trip_persons)[:10]}")
    person_travelled = person_key.astype(str).isin(travelling_ids)
    valid_labor_weight = person_labor.notna() & (person_labor > 0)
    population_labor_weight = float(person_labor.loc[valid_labor_weight].sum())
    traveller_labor_weight = float(person_labor.loc[valid_labor_weight & person_travelled].sum())

    # Time QA: compare official TiempoViaje against clocks when both parse.
    reported = _num(trips["TiempoViaje"])
    start = _clock_to_minutes(trips["HoraIni"])
    end = _clock_to_minutes(trips["HoraFin"])
    clock_duration = end - start
    clock_duration.loc[clock_duration < 0] += 1440
    comparable = reported.notna() & start.notna() & end.notna() & clock_duration.notna()
    diff = reported.loc[comparable] - clock_duration.loc[comparable]
    time_summary = pd.DataFrame(
        [
            {
                "trip_rows": int(len(trips)),
                "reported_time_nonmissing": int(reported.notna().sum()),
                "reported_time_positive": int((reported > 0).sum()),
                "reported_time_zero": int((reported == 0).sum()),
                "reported_time_negative": int((reported < 0).sum()),
                "clock_start_parseable": int(start.notna().sum()),
                "clock_end_parseable": int(end.notna().sum()),
                "clock_reported_comparable": int(comparable.sum()),
                "exact_clock_reported_matches": int(np.isclose(diff, 0, atol=1e-9).sum()),
                "within_1_minute": int((diff.abs() <= 1).sum()),
                "mean_reported_minus_clock": float(diff.mean()) if len(diff) else None,
                "median_abs_difference": float(diff.abs().median()) if len(diff) else None,
                "max_abs_difference": float(diff.abs().max()) if len(diff) else None,
                "reported_median": float(reported.median(skipna=True)),
                "reported_p99": float(reported.quantile(0.99)),
                "reported_max": float(reported.max(skipna=True)),
            }
        ]
    )
    time_summary.to_csv(output_dir / "trip_time_qa.csv", index=False)

    # Difference by official time-quality/imputation code.
    diff_frame = pd.DataFrame(
        {
            "CódigoTiempo": trips["CódigoTiempo"].astype("string").fillna("<MISSING>"),
            "reported": reported,
            "clock_duration": clock_duration,
            "difference": reported - clock_duration,
            "comparable": comparable,
        }
    )
    time_by_code = (
        diff_frame.groupby("CódigoTiempo", dropna=False)
        .agg(
            n_trips=("CódigoTiempo", "size"),
            n_comparable=("comparable", "sum"),
            reported_nonmissing=("reported", lambda x: int(x.notna().sum())),
            median_reported=("reported", "median"),
            median_abs_difference=("difference", lambda x: float(x.abs().median()) if x.notna().any() else np.nan),
            max_abs_difference=("difference", lambda x: float(x.abs().max()) if x.notna().any() else np.nan),
        )
        .reset_index()
    )
    time_by_code.to_csv(output_dir / "trip_time_qa_by_code.csv", index=False)

    metadata = {
        "tables_read": TABLES,
        "household_rows": int(len(hh)),
        "person_rows": int(len(persons)),
        "trip_rows": int(len(trips)),
        "unique_person_composite_keys": int(person_key.nunique()),
        "duplicate_person_composite_keys": int(person_key.duplicated().sum()),
        "unique_trip_composite_keys": int(trip_key.nunique()),
        "duplicate_trip_composite_keys": int(trip_key.duplicated().sum()),
        "unique_bare_persona_values": int(persons["Persona"].nunique(dropna=False)),
        "unique_bare_viaje_values": int(trips["Viaje"].nunique(dropna=False)),
        "laboral_normal_population_weight": population_labor_weight,
        "laboral_normal_traveller_weight_using_any_trip": traveller_labor_weight,
        "laboral_normal_nontraveller_weight_using_any_trip": population_labor_weight - traveller_labor_weight,
        "scalar_result_created": False,
    }
    (output_dir / "santiago2012_official_audit.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    print("\nCatalog values:")
    print(pd.concat(catalogs, ignore_index=True, sort=False).to_string(index=False))
    print("\nLabor factor by household domain:")
    print(labor_by_tipodia.to_string(index=False))
    print("\nTrip time QA:")
    print(time_summary.to_string(index=False))
    print("\nTrip time QA by CódigoTiempo:")
    print(time_by_code.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/santiago_2012_official_audit"),
    )
    args = parser.parse_args()
    run(args.database.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    main()
