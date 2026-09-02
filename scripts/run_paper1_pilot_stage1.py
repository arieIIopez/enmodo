#!/usr/bin/env python3
"""Paper I pilot — stage 1: reconstruct, audit, and diagnose support.

This runner intentionally STOPS before scalar compressibility. It produces the
person-day tables, full person universes, survey-design metadata, QA summaries,
and city×P1 support diagnostics needed to freeze the confirmatory support.

Prerequisite:
    bash scripts/hydrate_paper1_lfs.sh

Then:
    python scripts/run_paper1_pilot_stage1.py

Outputs are written under `outputs/paper1_stage1/` and ignored by Git.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

import numpy as np
import pandas as pd

from scripts.mobility_function import estimate_time_participation_curve
from scripts.paper1_adapters import (
    build_bogota_2015_person_days,
    build_mexico_2017_person_days,
    build_santiago_2012_person_days,
    prepare_bogota_2015,
    prepare_mexico_2017,
    prepare_santiago_2012,
)
from scripts.person_day import person_day_qa
from scripts.person_universe import (
    bogota_2015_person_universe,
    mexico_2017_person_universe,
    santiago_2012_person_universe,
)
from scripts.support_diagnostics import support_diagnostics


ROOT = Path(__file__).resolve().parents[1]

PATHS = {
    "mexico_trips": ROOT / "ciudad-de-mexico/viajes_personas_mexico_2017.csv",
    "mexico_persons": ROOT / "ciudad-de-mexico/source-csv/tsdem.csv",
    "santiago_trips": ROOT / "santiago/csv/viajes_personas_santiago_2012.csv",
    "santiago_persons": ROOT / "santiago/source-csv/personas.csv",
    "bogota_trips": ROOT / "bogota/2015/output-csv/viajes_personas_bogota_2015.csv",
    "bogota_persons": ROOT / "bogota/2015/source-xlsx/encuesta 2015 - personas.xlsx",
}


def _assert_hydrated(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"missing input: {path}")
    with path.open("rb") as handle:
        first = handle.readline(200)
    if first.startswith(b"version https://git-lfs.github.com/spec/v1"):
        raise RuntimeError(
            f"{path} is still a Git LFS pointer. Run scripts/hydrate_paper1_lfs.sh first."
        )


def _decimal_comma_to_float(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="raise")
    return pd.to_numeric(series.astype(str).str.replace(",", ".", regex=False), errors="raise")


def _git_head() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return None


def _attach_design_and_validate_weights(
    person_days: pd.DataFrame,
    universe: pd.DataFrame,
    *,
    city: str,
    rtol: float = 1e-9,
    atol: float = 1e-10,
) -> pd.DataFrame:
    pdays = person_days.copy()
    pdays["person_id"] = pdays["person_id"].astype(str)
    meta_cols = ["person_id", "weight"]
    for optional in ["cluster", "stratum"]:
        if optional in universe.columns:
            meta_cols.append(optional)
    meta = universe[meta_cols].copy().rename(columns={"weight": "universe_weight"})
    meta["person_id"] = meta["person_id"].astype(str)

    out = pdays.merge(meta, on="person_id", how="left", validate="one_to_one")
    if out["universe_weight"].isna().any():
        missing = out.loc[out["universe_weight"].isna(), "person_id"].head(10).tolist()
        raise ValueError(f"{city}: travelling person absent from person universe; examples={missing}")
    matched = np.isclose(
        out["weight"].astype(float),
        out["universe_weight"].astype(float),
        rtol=rtol,
        atol=atol,
    )
    if not bool(np.all(matched)):
        sample = out.loc[~matched, ["person_id", "weight", "universe_weight"]].head(10)
        raise ValueError(
            f"{city}: trip-derived and person-universe weights disagree; examples="
            f"{sample.to_dict('records')}"
        )
    return out.drop(columns="universe_weight")


def _purpose_counts(selected: pd.DataFrame, city: str, purpose_col: str) -> pd.DataFrame:
    counts = (
        selected[purpose_col]
        .astype(str)
        .value_counts(dropna=False)
        .rename_axis("purpose")
        .reset_index(name="n_trips_raw")
    )
    counts.insert(0, "city", city)
    return counts


def _load_inputs() -> dict[str, pd.DataFrame]:
    for path in PATHS.values():
        _assert_hydrated(path)

    santiago_trips = pd.read_csv(PATHS["santiago_trips"], low_memory=False)
    santiago_persons = pd.read_csv(
        PATHS["santiago_persons"], sep=";", encoding="latin-1", low_memory=False
    )
    for col in [
        "Factor_LaboralNormal",
        "Factor_SabadoNormal",
        "Factor_DomingoNormal",
        "Factor_LaboralEstival",
        "Factor_FindesemanaEstival",
        "Factor",
    ]:
        if col in santiago_persons.columns:
            santiago_persons[col] = _decimal_comma_to_float(santiago_persons[col])

    mexico_trips = pd.read_csv(PATHS["mexico_trips"], low_memory=False)
    mexico_persons = pd.read_csv(PATHS["mexico_persons"], low_memory=False)

    bogota_trips = pd.read_csv(PATHS["bogota_trips"], low_memory=False)
    bogota_persons = pd.read_excel(PATHS["bogota_persons"], engine="openpyxl")
    if "PONDERADOR_CALIBRADO" in bogota_persons.columns:
        bogota_persons["PONDERADOR_CALIBRADO"] = _decimal_comma_to_float(
            bogota_persons["PONDERADOR_CALIBRADO"]
        )

    return {
        "santiago_trips": santiago_trips,
        "santiago_persons": santiago_persons,
        "mexico_trips": mexico_trips,
        "mexico_persons": mexico_persons,
        "bogota_trips": bogota_trips,
        "bogota_persons": bogota_persons,
    }


def run(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    data = _load_inputs()

    s_trips, s_adapter = prepare_santiago_2012(data["santiago_trips"])
    m_trips, m_adapter = prepare_mexico_2017(data["mexico_trips"])
    b_trips, b_adapter = prepare_bogota_2015(data["bogota_trips"])

    s_pd, _ = build_santiago_2012_person_days(data["santiago_trips"])
    m_pd, _ = build_mexico_2017_person_days(data["mexico_trips"])
    b_pd, _ = build_bogota_2015_person_days(data["bogota_trips"])

    s_univ, s_univ_audit = santiago_2012_person_universe(data["santiago_persons"], s_trips)
    m_univ, m_univ_audit = mexico_2017_person_universe(data["mexico_persons"], m_trips)
    b_univ, b_univ_audit = bogota_2015_person_universe(data["bogota_persons"], b_trips)

    s_pd = _attach_design_and_validate_weights(s_pd, s_univ, city="Santiago 2012")
    m_pd = _attach_design_and_validate_weights(m_pd, m_univ, city="Ciudad de México 2017")
    b_pd = _attach_design_and_validate_weights(b_pd, b_univ, city="Bogotá 2015")

    person_days = pd.concat([s_pd, m_pd, b_pd], ignore_index=True, sort=False)
    universes = pd.concat([s_univ, m_univ, b_univ], ignore_index=True, sort=False)

    adapter_audit = pd.DataFrame([asdict(x) for x in [s_adapter, m_adapter, b_adapter]])
    universe_audit = pd.DataFrame(
        [asdict(x) for x in [s_univ_audit, m_univ_audit, b_univ_audit]]
    )
    pday_qa = person_day_qa(person_days)
    support = support_diagnostics(person_days)
    curve_cells = estimate_time_participation_curve(person_days)
    purposes = pd.concat(
        [
            _purpose_counts(s_trips, "Santiago 2012", "proposito"),
            _purpose_counts(m_trips, "Ciudad de México 2017", "p5_13"),
            _purpose_counts(b_trips, "Bogotá 2015", "MOTIVOVIAJE"),
        ],
        ignore_index=True,
    )

    # Stage-1 outputs: descriptive/QA only. No B(H), delta, ranking or CM_B.
    person_days.to_csv(output_dir / "person_days_travellers.csv.gz", index=False, compression="gzip")
    universes.to_csv(output_dir / "person_universes.csv.gz", index=False, compression="gzip")
    adapter_audit.to_csv(output_dir / "adapter_audit.csv", index=False)
    universe_audit.to_csv(output_dir / "universe_audit.csv", index=False)
    pday_qa.to_csv(output_dir / "person_day_qa.csv", index=False)
    purposes.to_csv(output_dir / "purpose_counts.csv", index=False)
    support.to_csv(output_dir / "support_diagnostics.csv", index=False)
    curve_cells.to_csv(output_dir / "time_participation_cells_unfrozen.csv", index=False)

    metadata = {
        "stage": "paper1_stage1_reconstruction_only",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": _git_head(),
        "scalar_results_created": False,
        "support_frozen": False,
        "inputs": {key: str(path.relative_to(ROOT)) for key, path in PATHS.items()},
        "next_required_decision": (
            "Review support_diagnostics.csv and freeze estimable global P1 support before "
            "running scalar compressibility."
        ),
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Stage 1 complete: {output_dir}")
    print("No scalar-compressibility result was calculated.")
    print("Review support_diagnostics.csv before freezing P0^C.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs/paper1_stage1",
        help="Directory for local QA outputs (default: outputs/paper1_stage1)",
    )
    args = parser.parse_args()
    run(args.output_dir.resolve())


if __name__ == "__main__":
    main()
