#!/usr/bin/env python3
"""Paper I direct-source stage 1 for Bogotá 2015.

Reads the preserved official survey XLSX files, reconstructs the separately
calibrated workday household universe and travelling person-days, and emits QA
and support diagnostics only. No scalar coefficient or cross-city ranking is
calculated at this stage.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mobility_function import estimate_time_participation_curve
from scripts.paper1_official_adapters import build_bogota_2015_from_official
from scripts.person_day import person_day_qa
from scripts.support_diagnostics import support_diagnostics


TRIPS = ROOT / "bogota/2015/source-xlsx/encuesta 2015 - viajes.xlsx"
PERSONS = ROOT / "bogota/2015/source-xlsx/encuesta 2015 - personas.xlsx"


def run(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if not TRIPS.exists() or not PERSONS.exists():
        raise FileNotFoundError("Bogotá 2015 source XLSX files are missing from the checkout")

    trips = pd.read_excel(TRIPS, engine="openpyxl")
    persons = pd.read_excel(PERSONS, engine="openpyxl")
    person_days, universe, adapter_audit, universe_audit = build_bogota_2015_from_official(
        trips, persons
    )

    pqa = person_day_qa(person_days)
    support = support_diagnostics(person_days)
    curve = estimate_time_participation_curve(person_days)

    total_weight = float(universe["weight"].sum())
    traveller_weight = float(universe.loc[universe["travelled"], "weight"].sum())
    nontraveller_weight = total_weight - traveller_weight
    universe_summary = pd.DataFrame(
        [
            {"city": "Bogotá 2015", "quantity": "workday_population", "expanded_weight": total_weight},
            {"city": "Bogotá 2015", "quantity": "workday_travellers", "expanded_weight": traveller_weight},
            {"city": "Bogotá 2015", "quantity": "workday_nontravellers", "expanded_weight": nontraveller_weight},
            {
                "city": "Bogotá 2015",
                "quantity": "weighted_traveller_share",
                "expanded_weight": traveller_weight / total_weight if total_weight > 0 else float("nan"),
            },
        ]
    )

    pd.DataFrame([asdict(adapter_audit)]).to_csv(output_dir / "adapter_audit.csv", index=False)
    pd.DataFrame([asdict(universe_audit)]).to_csv(output_dir / "universe_audit.csv", index=False)
    universe_summary.to_csv(output_dir / "workday_universe_summary.csv", index=False)
    pqa.to_csv(output_dir / "person_day_qa.csv", index=False)
    support.to_csv(output_dir / "support_diagnostics.csv", index=False)
    curve.to_csv(output_dir / "time_participation_cells.csv", index=False)

    metadata = {
        "city": "Bogotá 2015",
        "primary_geographic_domain": "official Bogotá + 17 municipalities EOD domain",
        "primary_day_domain": "separately calibrated workday household subsample",
        "source": "official source XLSX preserved in repository",
        "source_trips": str(TRIPS.relative_to(ROOT)),
        "source_persons": str(PERSONS.relative_to(ROOT)),
        "historical_processed_lfs_used": False,
        "workday_household_assignment": (
            "household belongs to workday universe when its observed trip flags identify DIA_HABIL; "
            "all household members are retained, including zero-trip persons"
        ),
        "external_city_core_benchmark_used_for_primary_qa": False,
        "cross_city_support_evaluated": False,
        "scalar_result_created": False,
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Bogotá official-source stage 1 complete: {output_dir}")
    print(universe_summary.to_string(index=False))
    print("No scalar-compressibility result was calculated.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs/bogota_2015_official_stage1",
    )
    args = parser.parse_args()
    run(args.output_dir.resolve())


if __name__ == "__main__":
    main()
