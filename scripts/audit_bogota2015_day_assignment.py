#!/usr/bin/env python3
"""Audit workday/non-workday sample assignment in Bogotá EOD 2015.

The 2015 delivery combines day-type information at trip level. A person with no
workday trip must not automatically be classified as a workday non-traveller:
they may belong to the non-workday subsample. This audit reconstructs day-type
membership from observed trips at person and household level and quantifies the
remaining unclassified no-trip households. It emits aggregate diagnostics only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TRIPS = ROOT / "bogota/2015/source-xlsx/encuesta 2015 - viajes.xlsx"
PERSONS = ROOT / "bogota/2015/source-xlsx/encuesta 2015 - personas.xlsx"
SURVEYS = ROOT / "bogota/2015/source-xlsx/encuesta 2015 - encuestas.xlsx"


def _norm(series: pd.Series) -> pd.Series:
    return series.astype("string").str.strip().str.lower()


def _yes(series: pd.Series) -> pd.Series:
    return _norm(series).isin({"s", "si", "sí", "1", "true"})


def _num(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    return pd.to_numeric(
        series.astype("string").str.strip().str.replace(",", ".", regex=False),
        errors="coerce",
    )


def _key(df: pd.DataFrame) -> pd.Series:
    return (
        df["ID_ENCUESTA"].astype(str).str.replace(r"\.0$", "", regex=True)
        + "::"
        + df["NUMERO_PERSONA"].astype(str).str.replace(r"\.0$", "", regex=True)
    )


def _classify(any_hab: pd.Series, any_nohab: pd.Series) -> pd.Series:
    out = pd.Series("no_trip_evidence", index=any_hab.index, dtype="string")
    out.loc[any_hab & ~any_nohab] = "workday_only"
    out.loc[~any_hab & any_nohab] = "nonworkday_only"
    out.loc[any_hab & any_nohab] = "both_day_types"
    return out


def run(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    trips = pd.read_excel(TRIPS, engine="openpyxl")
    persons = pd.read_excel(PERSONS, engine="openpyxl")
    surveys = pd.read_excel(SURVEYS, engine="openpyxl")

    required = {"ID_ENCUESTA", "NUMERO_PERSONA", "DIA_HABIL", "DIA_NOHABIL"}
    missing = sorted(required.difference(trips.columns))
    if missing:
        raise ValueError(f"Trips missing required fields: {missing}")

    t = trips.copy()
    t["person_id"] = _key(t)
    t["is_workday"] = _yes(t["DIA_HABIL"])
    t["is_nonworkday"] = _yes(t["DIA_NOHABIL"])

    # Row-level coding QA.
    row_codes = (
        t.assign(
            DIA_HABIL_N=_norm(t["DIA_HABIL"]).fillna("<missing>"),
            DIA_NOHABIL_N=_norm(t["DIA_NOHABIL"]).fillna("<missing>"),
        )
        .groupby(["DIA_HABIL_N", "DIA_NOHABIL_N"], dropna=False)
        .size()
        .reset_index(name="trip_rows")
        .sort_values("trip_rows", ascending=False)
    )
    row_codes.to_csv(output_dir / "trip_day_flag_combinations.csv", index=False)

    trip_person = (
        t.groupby(["person_id", "ID_ENCUESTA"], as_index=False)
        .agg(
            any_workday=("is_workday", "any"),
            any_nonworkday=("is_nonworkday", "any"),
            workday_trip_rows=("is_workday", "sum"),
            nonworkday_trip_rows=("is_nonworkday", "sum"),
            total_trip_rows=("person_id", "size"),
        )
    )
    trip_person["trip_day_class"] = _classify(
        trip_person["any_workday"], trip_person["any_nonworkday"]
    )

    p = persons.copy()
    p["person_id"] = _key(p)
    p["weight"] = _num(p["PONDERADOR_CALIBRADO"])
    if p["weight"].isna().any():
        raise ValueError("Person PONDERADOR_CALIBRADO contains non-numeric values")
    p = p.merge(
        trip_person[
            [
                "person_id",
                "any_workday",
                "any_nonworkday",
                "workday_trip_rows",
                "nonworkday_trip_rows",
                "total_trip_rows",
                "trip_day_class",
            ]
        ],
        on="person_id",
        how="left",
        validate="one_to_one",
    )
    for col in ["any_workday", "any_nonworkday"]:
        p[col] = p[col].fillna(False).astype(bool)
    for col in ["workday_trip_rows", "nonworkday_trip_rows", "total_trip_rows"]:
        p[col] = p[col].fillna(0).astype(int)
    p["trip_day_class"] = p["trip_day_class"].fillna("no_trip_evidence")

    person_summary = (
        p.groupby("trip_day_class", dropna=False)
        .agg(
            sample_persons=("person_id", "size"),
            expanded_weight=("weight", "sum"),
            households=("ID_ENCUESTA", "nunique"),
            workday_travellers=("any_workday", "sum"),
            nonworkday_travellers=("any_nonworkday", "sum"),
        )
        .reset_index()
    )
    person_summary.to_csv(output_dir / "person_day_assignment_summary.csv", index=False)

    # REALIZO_DESPLAZAMIENTO is potentially informative for zero-trip people;
    # preserve all observed values rather than imposing semantics here.
    if "REALIZO_DESPLAZAMIENTO" in p.columns:
        p["REALIZO_DESPLAZAMIENTO_N"] = (
            p["REALIZO_DESPLAZAMIENTO"].astype("string").fillna("<MISSING>").str.strip()
        )
        displacement = (
            p.groupby(["trip_day_class", "REALIZO_DESPLAZAMIENTO_N"], dropna=False)
            .agg(sample_persons=("person_id", "size"), expanded_weight=("weight", "sum"))
            .reset_index()
        )
        displacement.to_csv(output_dir / "realizo_desplazamiento_by_day_class.csv", index=False)

    # Household-level inference: if day type is assigned at household level,
    # travelling members should reveal a single common reference-day class.
    hh_trip = (
        t.groupby("ID_ENCUESTA", as_index=False)
        .agg(
            any_workday=("is_workday", "any"),
            any_nonworkday=("is_nonworkday", "any"),
            workday_trip_rows=("is_workday", "sum"),
            nonworkday_trip_rows=("is_nonworkday", "sum"),
            total_trip_rows=("ID_ENCUESTA", "size"),
        )
    )
    hh_trip["household_day_class"] = _classify(
        hh_trip["any_workday"], hh_trip["any_nonworkday"]
    )

    hh = surveys[["ID_ENCUESTA", "MUNICIPIO", "DEPARTAMENTO"]].copy()
    if "PONDERADOR_CALIBRADO" in surveys.columns:
        hh["household_weight"] = _num(surveys["PONDERADOR_CALIBRADO"])
    hh = hh.merge(hh_trip, on="ID_ENCUESTA", how="left", validate="one_to_one")
    for col in ["any_workday", "any_nonworkday"]:
        hh[col] = hh[col].fillna(False).astype(bool)
    for col in ["workday_trip_rows", "nonworkday_trip_rows", "total_trip_rows"]:
        hh[col] = hh[col].fillna(0).astype(int)
    hh["household_day_class"] = hh["household_day_class"].fillna("no_trip_evidence")

    # Attach household class to every person and compute implied day-specific
    # population totals, including non-travelling household members.
    p = p.merge(
        hh[["ID_ENCUESTA", "household_day_class", "MUNICIPIO", "DEPARTAMENTO"]],
        on="ID_ENCUESTA",
        how="left",
        validate="many_to_one",
    )
    implied = (
        p.groupby("household_day_class", dropna=False)
        .agg(
            sample_persons=("person_id", "size"),
            expanded_population=("weight", "sum"),
            workday_traveller_weight=("weight", lambda s: float(s[p.loc[s.index, "any_workday"]].sum())),
            nonworkday_traveller_weight=("weight", lambda s: float(s[p.loc[s.index, "any_nonworkday"]].sum())),
            households=("ID_ENCUESTA", "nunique"),
        )
        .reset_index()
    )
    implied.to_csv(output_dir / "household_inferred_population.csv", index=False)

    hh_summary = (
        hh.groupby("household_day_class", dropna=False)
        .agg(
            sample_households=("ID_ENCUESTA", "size"),
            household_weight_sum=("household_weight", "sum") if "household_weight" in hh.columns else ("ID_ENCUESTA", "size"),
            sample_trip_rows=("total_trip_rows", "sum"),
        )
        .reset_index()
    )
    hh_summary.to_csv(output_dir / "household_day_assignment_summary.csv", index=False)

    # Diagnose whether ID ranges or REG_ANTIGUO are associated with day class.
    id_diag = hh[["ID_ENCUESTA", "household_day_class"]].copy()
    id_diag["ID_NUM"] = pd.to_numeric(id_diag["ID_ENCUESTA"], errors="coerce")
    id_quantiles = (
        id_diag.groupby("household_day_class")["ID_NUM"]
        .quantile([0, 0.1, 0.25, 0.5, 0.75, 0.9, 1.0])
        .rename("ID_ENCUESTA_quantile")
        .reset_index()
    )
    id_quantiles.to_csv(output_dir / "household_id_quantiles_by_day_class.csv", index=False)

    if "REG_ANTIGUO" in p.columns:
        reg = (
            p.assign(REG_ANTIGUO_N=p["REG_ANTIGUO"].astype("string").fillna("<MISSING>").str.strip())
            .groupby(["household_day_class", "REG_ANTIGUO_N"], dropna=False)
            .agg(sample_persons=("person_id", "size"), expanded_weight=("weight", "sum"))
            .reset_index()
        )
        reg.to_csv(output_dir / "reg_antiguo_by_household_day_class.csv", index=False)

    metadata = {
        "trip_rows": int(len(t)),
        "person_rows": int(len(p)),
        "household_rows": int(len(hh)),
        "persons_with_any_workday_trip": int(p["any_workday"].sum()),
        "persons_with_any_nonworkday_trip": int(p["any_nonworkday"].sum()),
        "persons_with_both_day_types": int((p["any_workday"] & p["any_nonworkday"]).sum()),
        "households_with_both_day_types": int((hh["any_workday"] & hh["any_nonworkday"]).sum()),
        "households_without_any_trip_evidence": int((hh["household_day_class"] == "no_trip_evidence").sum()),
        "interpretation_rule": "day class inferred only from explicit DIA_HABIL/DIA_NOHABIL trip flags; no-trip households remain unclassified",
    }
    (output_dir / "day_assignment_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("Bogotá 2015 day-assignment audit complete")
    print("\nPerson trip-day classes:")
    print(person_summary.to_string(index=False))
    print("\nHousehold inferred population:")
    print(implied.to_string(index=False))
    print("\nHousehold classes:")
    print(hh_summary.to_string(index=False))
    print("\nMetadata:")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs/bogota_2015_day_assignment_audit",
    )
    args = parser.parse_args()
    run(args.output_dir.resolve())


if __name__ == "__main__":
    main()
