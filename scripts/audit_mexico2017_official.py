#!/usr/bin/env python3
"""Aggregate QA audit of the official INEGI EOD 2017 package for Paper I.

No person-level microdata are written. The audit checks the internal redundancy
between TSDEM and TVIAJE before a direct person-day adapter is frozen.
"""

from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
from pathlib import Path
import zipfile

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
URL = "https://www.inegi.org.mx/contenidos/programas/eod/2017/datosabiertos/eod_2017_csv.zip"
EXPECTED_SHA256 = "120a43445039f5b9bbc7ff0c7365f8549e0bc1091ef828df7555e00cc4116a3a"
TVIAJE = "tviaje_eod2017/conjunto_de_datos/tviaje.csv"
TSDEM = "tsdem_eod2017/conjunto_de_datos/tsdem.csv"


def _clean_code(s: pd.Series) -> pd.Series:
    return s.astype("string").str.strip()


def run(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    r = requests.get(URL, timeout=180, headers={"User-Agent": "ENMODO Paper I reproducibility audit"})
    r.raise_for_status()
    digest = hashlib.sha256(r.content).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError(f"INEGI package SHA-256 changed: expected {EXPECTED_SHA256}, got {digest}")

    zf = zipfile.ZipFile(BytesIO(r.content))
    trips = pd.read_csv(zf.open(TVIAJE), dtype=str, low_memory=False)
    persons = pd.read_csv(zf.open(TSDEM), dtype=str, low_memory=False)

    for col in trips.columns:
        trips[col] = _clean_code(trips[col])
    for col in persons.columns:
        persons[col] = _clean_code(persons[col])

    weekday = trips.loc[trips["p5_3"] == "1"].copy()
    saturday = trips.loc[trips["p5_3"] == "2"].copy()
    other_day = trips.loc[~trips["p5_3"].isin(["1", "2"])].copy()

    # Travel-row counts against TSDEM declared weekday trip counts.
    observed = weekday.groupby("id_soc", dropna=False).size().rename("observed_weekday_trips")
    declared = pd.to_numeric(persons.set_index("id_soc")["p5_4"], errors="coerce").rename("declared_weekday_trips")
    consistency = declared.to_frame().join(observed, how="outer")
    consistency["observed_weekday_trips"] = consistency["observed_weekday_trips"].fillna(0).astype(int)
    consistency["declared_present"] = consistency["declared_weekday_trips"].notna()
    consistency["declared_equals_observed"] = (
        consistency["declared_weekday_trips"].fillna(0).astype(float)
        == consistency["observed_weekday_trips"].astype(float)
    )
    consistency["status"] = "match"
    consistency.loc[~consistency["declared_equals_observed"], "status"] = "mismatch"
    consistency.loc[
        ~consistency["declared_present"] & (consistency["observed_weekday_trips"] == 0), "status"
    ] = "declared_blank_observed_zero"
    consistency.loc[
        ~consistency["declared_present"] & (consistency["observed_weekday_trips"] > 0), "status"
    ] = "declared_blank_observed_positive"
    consistency_status = consistency["status"].value_counts().rename_axis("status").reset_index(name="n_persons")
    consistency_status.to_csv(output_dir / "tripcount_consistency.csv", index=False)

    # Home semantics redundancy: destination type vs stated purpose.
    dest_home = weekday["p5_11a"] == "01"
    purpose_home = weekday["p5_13"] == "01"
    semantic = pd.DataFrame(
        {
            "destination_home": dest_home,
            "purpose_home": purpose_home,
            "destination_unknown": weekday["p5_11a"].isin(["99", "", pd.NA]).fillna(True),
            "purpose_unknown": weekday["p5_13"].isin(["99", "", pd.NA]).fillna(True),
        }
    )
    home_table = (
        semantic.groupby(["destination_home", "purpose_home"], dropna=False)
        .size()
        .rename("n_trips")
        .reset_index()
    )
    home_table.to_csv(output_dir / "home_semantics_crosstab.csv", index=False)

    # Time completeness. 99 is the official non-response code for HH/MM fields.
    time_cols = ["p5_9_1", "p5_9_2", "p5_10_1", "p5_10_2"]
    invalid_time = pd.Series(False, index=weekday.index)
    time_rows = []
    for col in time_cols:
        bad = weekday[col].isna() | weekday[col].isin(["", "99"])
        invalid_time |= bad
        time_rows.append({"field": col, "n_invalid": int(bad.sum()), "share_invalid": float(bad.mean())})
    pd.DataFrame(time_rows).to_csv(output_dir / "time_field_qa.csv", index=False)

    invalid_person_ids = set(weekday.loc[invalid_time, "id_soc"].dropna())
    home_conflict = dest_home != purpose_home
    home_conflict_person_ids = set(weekday.loc[home_conflict, "id_soc"].dropna())
    tripcount_mismatch_ids = set(consistency.index[consistency["status"].isin(["mismatch", "declared_blank_observed_positive"])].astype(str))

    # Survey-design attributes must be constant within person in TVIAJE.
    design_variation = {}
    for col in ["factor", "upm_dis", "est_dis", "estrato", "sexo", "edad"]:
        n_unique = weekday.groupby("id_soc")[col].nunique(dropna=False)
        design_variation[col] = int((n_unique > 1).sum())

    # Residence expansion by official entity/municipality code from TSDEM.
    persons["factor_num"] = pd.to_numeric(persons["factor"], errors="coerce")
    residence = (
        persons.groupby(["ent", "mun"], dropna=False)
        .agg(sample_persons=("id_soc", "size"), expanded_persons=("factor_num", "sum"))
        .reset_index()
        .sort_values("expanded_persons", ascending=False)
    )
    residence.to_csv(output_dir / "residence_expansion.csv", index=False)

    declared_dist = (
        persons["p5_4"].fillna("<BLANK>").value_counts(dropna=False)
        .rename_axis("p5_4")
        .reset_index(name="n_persons")
    )
    declared_dist.to_csv(output_dir / "declared_weekday_trip_distribution.csv", index=False)

    observed_dist = (
        observed.value_counts().sort_index().rename_axis("n_weekday_trip_rows").reset_index(name="n_persons")
    )
    observed_dist.to_csv(output_dir / "observed_weekday_trip_distribution.csv", index=False)

    overall = {
        "source_url": URL,
        "source_sha256": digest,
        "n_tviaje_rows": int(len(trips)),
        "n_weekday_rows": int(len(weekday)),
        "n_saturday_rows": int(len(saturday)),
        "n_other_day_rows": int(len(other_day)),
        "n_tsdem_persons": int(len(persons)),
        "n_weekday_persons_in_tviaje": int(weekday["id_soc"].nunique()),
        "n_persons_invalid_weekday_time": int(len(invalid_person_ids)),
        "n_persons_home_semantics_conflict": int(len(home_conflict_person_ids)),
        "n_persons_tripcount_mismatch": int(len(tripcount_mismatch_ids)),
        "design_variation_person_counts": design_variation,
        "full_domain_expanded_persons": float(persons["factor_num"].sum()),
        "max_observed_weekday_trip_rows_per_person": int(observed.max()),
        "max_declared_weekday_trips": int(pd.to_numeric(persons["p5_4"], errors="coerce").max()),
        "scalar_result_created": False,
    }
    (output_dir / "mexico2017_official_audit.json").write_text(
        json.dumps(overall, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(overall, ensure_ascii=False, indent=2))
    print("\nTrip-count consistency:")
    print(consistency_status.to_string(index=False))
    print("\nHome semantics:")
    print(home_table.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs/mexico_2017_official_audit",
    )
    args = parser.parse_args()
    run(args.output_dir.resolve())


if __name__ == "__main__":
    main()
