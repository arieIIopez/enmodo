#!/usr/bin/env python3
"""Diary-level QA for Santiago EOD 2012 normal working-day sample."""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import re
import subprocess

import numpy as np
import pandas as pd


def _export(db: Path, table: str) -> pd.DataFrame:
    raw = subprocess.check_output(["mdb-export", str(db), table], timeout=180)
    return pd.read_csv(io.BytesIO(raw), dtype=str, low_memory=False)


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype("string").str.strip().str.replace(",", ".", regex=False), errors="coerce"
    )


def _clock(s: pd.Series) -> pd.Series:
    text = s.astype("string").str.strip()
    ex = text.str.extract(r"(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<sec>\d{2}))?$")
    h = pd.to_numeric(ex.h, errors="coerce")
    m = pd.to_numeric(ex.m, errors="coerce")
    sec = pd.to_numeric(ex.sec, errors="coerce").fillna(0)
    valid = h.between(0, 24) & m.between(0, 59) & sec.between(0, 59)
    valid &= ~((h == 24) & ((m != 0) | (sec != 0)))
    return (h * 60 + m + sec / 60).where(valid)


def run(database: Path, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    p = _export(database, "Persona")
    t = _export(database, "Viaje")
    h = _export(database, "Hogar")

    p_factor = _num(p["Factor_LaboralNormal"])
    t_factor = _num(t["FactorLaboralNormal"])
    p_lab = p.loc[p_factor.notna() & (p_factor > 0)].copy()
    p_lab["_factor"] = p_factor.loc[p_lab.index]
    t_lab = t.loc[t_factor.notna() & (t_factor > 0)].copy()
    t_lab["_trip_factor"] = t_factor.loc[t_lab.index]

    p_ids = set(p_lab["Persona"].astype(str))
    t_ids = set(t_lab["Persona"].astype(str))
    orphan_travellers = sorted(t_ids.difference(p_ids))
    if orphan_travellers:
        raise ValueError(f"LaboralNormal trip persons absent from person universe: {orphan_travellers[:10]}")

    observed = t_lab.groupby("Persona", observed=True).size().rename("observed_trips")
    declared = _num(p_lab.set_index("Persona")["Viajes"]).rename("declared_trips")
    compare = declared.to_frame().join(observed, how="left")
    compare["observed_trips"] = compare["observed_trips"].fillna(0).astype(int)
    compare["declared_for_compare"] = compare["declared_trips"].fillna(0)
    compare["difference"] = compare["declared_for_compare"] - compare["observed_trips"]
    mismatch = compare["difference"] != 0

    start = _clock(t_lab["HoraIni"])
    end = _clock(t_lab["HoraFin"])
    duration = end - start
    duration.loc[duration < 0] += 1440
    invalid_time_rows = start.isna() | end.isna() | duration.isna() | (duration < 0) | (duration > 1440)
    invalid_time_ids = set(t_lab.loc[invalid_time_rows, "Persona"].astype(str))

    purpose_num = _num(t_lab["Proposito"])
    invalid_purpose_rows = purpose_num.isna() | ~purpose_num.between(1, 14)
    invalid_purpose_ids = set(t_lab.loc[invalid_purpose_rows, "Persona"].astype(str))
    mismatch_ids = set(compare.index[mismatch].astype(str))
    excluded_ids = invalid_time_ids | invalid_purpose_ids | mismatch_ids

    reported = _num(t_lab["TiempoViaje"])
    comparable = reported.notna() & ~invalid_time_rows
    time_difference = reported.loc[comparable] - duration.loc[comparable]
    mismatched_reported_time_ids = set(
        t_lab.loc[comparable & ~np.isclose(reported, duration, atol=1e-9), "Persona"].astype(str)
    )

    # Household domain consistency for selected person sample.
    domain = h[["Hogar", "TipoDia", "Temporada", "DiaAsig"]].copy()
    pj = p_lab.merge(domain, on="Hogar", how="left", validate="many_to_one")
    domain_counts = (
        pj.groupby(["TipoDia", "Temporada", "DiaAsig"], dropna=False)
        .agg(sample_persons=("Persona", "size"), expanded_weight=("_factor", "sum"))
        .reset_index()
    )
    domain_counts.to_csv(output_dir / "laboral_normal_domain_counts.csv", index=False)

    mismatch_distribution = (
        compare["difference"].value_counts(dropna=False).rename_axis("declared_minus_observed").reset_index(name="n_persons")
    )
    mismatch_distribution.to_csv(output_dir / "tripcount_difference_distribution.csv", index=False)

    # Distribution of trip-level FactorLaboralNormal within person. It is not
    # the person weight for Paper I but should not silently redefine the sample.
    factor_variation = t_lab.groupby("Persona", observed=True)["_trip_factor"].nunique(dropna=False)
    factor_variation.value_counts().rename_axis("n_unique_trip_factor_values").reset_index(
        name="n_persons"
    ).to_csv(output_dir / "trip_factor_variation.csv", index=False)

    qa = pd.DataFrame(
        [
            {"quantity": "laboral_normal_persons", "value": len(p_lab)},
            {"quantity": "laboral_normal_travellers", "value": len(t_ids)},
            {"quantity": "laboral_normal_nontravellers", "value": len(p_lab) - len(t_ids)},
            {"quantity": "laboral_normal_trip_rows", "value": len(t_lab)},
            {"quantity": "tripcount_mismatch_persons", "value": int(mismatch.sum())},
            {"quantity": "invalid_time_rows", "value": int(invalid_time_rows.sum())},
            {"quantity": "invalid_time_persons", "value": len(invalid_time_ids)},
            {"quantity": "invalid_purpose_rows", "value": int(invalid_purpose_rows.sum())},
            {"quantity": "invalid_purpose_persons", "value": len(invalid_purpose_ids)},
            {"quantity": "reported_clock_mismatch_persons", "value": len(mismatched_reported_time_ids)},
            {"quantity": "any_diary_quality_exclusion_persons", "value": len(excluded_ids)},
        ]
    )
    qa.to_csv(output_dir / "diary_quality_summary.csv", index=False)

    metadata = {
        "laboral_normal_population_weight": float(p_lab["_factor"].sum()),
        "laboral_normal_traveller_weight": float(
            p_lab.loc[p_lab["Persona"].astype(str).isin(t_ids), "_factor"].sum()
        ),
        "laboral_normal_nontraveller_weight": float(
            p_lab.loc[~p_lab["Persona"].astype(str).isin(t_ids), "_factor"].sum()
        ),
        "reported_clock_comparable_trips": int(comparable.sum()),
        "reported_clock_exact_matches": int(np.isclose(time_difference, 0, atol=1e-9).sum()),
        "declared_observed_tripcount_exact_persons": int((~mismatch).sum()),
        "declared_observed_tripcount_total_persons": int(len(compare)),
        "home_return_trip_rows": int((purpose_num == 7).sum()),
        "quality_retained_traveller_persons": int(len(t_ids - excluded_ids)),
        "scalar_result_created": False,
    }
    (output_dir / "diary_audit_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(qa.to_string(index=False))
    print("\nTrip-count difference distribution:")
    print(mismatch_distribution.to_string(index=False))
    print("\nLaboralNormal household domain:")
    print(domain_counts.to_string(index=False))
    print("\nMetadata:")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/santiago_2012_diary_audit"))
    args = parser.parse_args()
    run(args.database.resolve(), args.output_dir.resolve())


if __name__ == "__main__":
    main()
