#!/usr/bin/env python3
"""Audit the residence/geographic domain and expansion weights of Bogotá EOD 2015.

The official survey covers Bogotá and surrounding municipalities. Paper I must
select a resident population domain before comparing traveller/non-traveller
rates or T|P1 across cities. This audit emits only aggregate schema, value-count
and expansion summaries; it never persists person-level microdata.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SURVEYS = ROOT / "bogota/2015/source-xlsx/encuesta 2015 - encuestas.xlsx"
PERSONS = ROOT / "bogota/2015/source-xlsx/encuesta 2015 - personas.xlsx"

KEYWORDS = re.compile(
    r"(municip|localid|ciudad|depart|residen|barrio|zona|zat|upz|direccion|estrato|area)",
    re.I,
)


def _num(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    return pd.to_numeric(
        series.astype("string").str.strip().str.replace(",", ".", regex=False),
        errors="coerce",
    )


def run(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    surveys = pd.read_excel(SURVEYS, engine="openpyxl")
    persons = pd.read_excel(PERSONS, engine="openpyxl")

    schema = pd.DataFrame(
        {
            "column": surveys.columns.astype(str),
            "dtype": [str(surveys[c].dtype) for c in surveys.columns],
            "n_nonmissing": [int(surveys[c].notna().sum()) for c in surveys.columns],
            "n_unique_nonmissing": [int(surveys[c].nunique(dropna=True)) for c in surveys.columns],
            "keyword_candidate": [bool(KEYWORDS.search(str(c))) for c in surveys.columns],
        }
    )
    schema.to_csv(output_dir / "encuestas_schema.csv", index=False)

    candidate_rows: list[dict[str, object]] = []
    for col in surveys.columns:
        nunique = int(surveys[col].nunique(dropna=True))
        if KEYWORDS.search(str(col)) or nunique <= 60:
            vc = surveys[col].astype("string").fillna("<MISSING>").value_counts(dropna=False)
            for value, n in vc.head(200).items():
                candidate_rows.append(
                    {
                        "column": str(col),
                        "value": str(value),
                        "n": int(n),
                        "n_unique_nonmissing": nunique,
                        "keyword_candidate": bool(KEYWORDS.search(str(col))),
                    }
                )
    pd.DataFrame(candidate_rows).to_csv(output_dir / "candidate_value_counts.csv", index=False)

    # Residence domain comes from the household/survey table. Join it to persons
    # with many-to-one validation so a geographic filter can never duplicate a
    # person silently.
    domain = surveys[["ID_ENCUESTA", "MUNICIPIO", "DEPARTAMENTO"]].copy()
    p = persons.merge(domain, on="ID_ENCUESTA", how="left", validate="many_to_one")
    if p["MUNICIPIO"].isna().any():
        raise ValueError("Bogotá 2015: persons missing household residence domain")

    p_weight = _num(p["PONDERADOR_CALIBRADO"])
    if p_weight.isna().any():
        raise ValueError("Bogotá 2015: person PONDERADOR_CALIBRADO contains non-numeric values")
    p["_person_weight"] = p_weight

    h_weight = _num(surveys["PONDERADOR_CALIBRADO"])
    surveys2 = surveys.copy()
    surveys2["_household_weight"] = h_weight

    person_summary = (
        p.groupby(["DEPARTAMENTO", "MUNICIPIO"], dropna=False)
        .agg(
            sample_persons=("ID_ENCUESTA", "size"),
            expanded_person_weight=("_person_weight", "sum"),
            mean_person_weight=("_person_weight", "mean"),
        )
        .reset_index()
    )
    household_summary = (
        surveys2.groupby(["DEPARTAMENTO", "MUNICIPIO"], dropna=False)
        .agg(
            sample_households=("ID_ENCUESTA", "size"),
            expanded_household_weight=("_household_weight", "sum"),
            mean_household_weight=("_household_weight", "mean"),
        )
        .reset_index()
    )
    weight_summary = person_summary.merge(
        household_summary,
        on=["DEPARTAMENTO", "MUNICIPIO"],
        how="outer",
        validate="one_to_one",
    )
    weight_summary.to_csv(output_dir / "domain_weight_summary.csv", index=False)

    survey_ids = set(surveys["ID_ENCUESTA"].astype(str).str.replace(r"\.0$", "", regex=True))
    person_ids = set(persons["ID_ENCUESTA"].astype(str).str.replace(r"\.0$", "", regex=True))
    metadata = {
        "survey_rows": int(len(surveys)),
        "person_rows": int(len(persons)),
        "survey_columns": [str(c) for c in surveys.columns],
        "person_columns": [str(c) for c in persons.columns],
        "person_weight_sum_full_domain": float(p["_person_weight"].sum()),
        "household_weight_sum_full_domain": float(surveys2["_household_weight"].sum()),
        "person_households_without_survey_row": int(len(person_ids - survey_ids)),
        "survey_rows_without_person": int(len(survey_ids - person_ids)),
        "purpose": "identify resident geographic domain and expansion semantics before Paper I comparison",
    }
    (output_dir / "domain_audit_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("Bogotá 2015 domain/weight audit complete")
    print(schema.loc[schema.keyword_candidate].to_string(index=False))
    print("\nExpansion by residence domain:")
    print(weight_summary.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs/bogota_2015_domain_audit",
    )
    args = parser.parse_args()
    run(args.output_dir.resolve())


if __name__ == "__main__":
    main()
