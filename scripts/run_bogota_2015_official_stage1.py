#!/usr/bin/env python3
"""Paper I direct-source stage 1 for Bogotá 2015.

This is the first real-data migration away from lost ENMODO LFS intermediates.
It reads the original official `viajes.xlsx` and `personas.xlsx` files already
preserved in the repository, reconstructs workday person-days, and emits only
QA/support outputs. No scalar coefficient or cross-city ranking is calculated.
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
from scripts.paper1_protocol import evaluate_preregistered_supports
from scripts.person_day import person_day_qa
from scripts.support_diagnostics import support_diagnostics


TRIPS = ROOT / "bogota/2015/source-xlsx/encuesta 2015 - viajes.xlsx"
PERSONS = ROOT / "bogota/2015/source-xlsx/encuesta 2015 - personas.xlsx"

# External benchmark from Bogotá Observatorio de Movilidad 2017, table 2.5,
# using EOD 2015: population age 5+ in Bogotá, workday including walking trips
# shorter than 15 min. It is QA context, not a calibration target.
OFFICIAL_BOGOTA_TRAVELLERS = 5_834_106.0
OFFICIAL_BOGOTA_NONTRAVELLERS = 1_505_273.0


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
    benchmark = pd.DataFrame(
        [
            {
                "city": "Bogotá 2015",
                "quantity": "travellers",
                "reconstructed_weight": traveller_weight,
                "official_benchmark": OFFICIAL_BOGOTA_TRAVELLERS,
                "difference": traveller_weight - OFFICIAL_BOGOTA_TRAVELLERS,
                "relative_difference": (traveller_weight / OFFICIAL_BOGOTA_TRAVELLERS) - 1,
            },
            {
                "city": "Bogotá 2015",
                "quantity": "nontravellers",
                "reconstructed_weight": nontraveller_weight,
                "official_benchmark": OFFICIAL_BOGOTA_NONTRAVELLERS,
                "difference": nontraveller_weight - OFFICIAL_BOGOTA_NONTRAVELLERS,
                "relative_difference": (nontraveller_weight / OFFICIAL_BOGOTA_NONTRAVELLERS) - 1,
            },
        ]
    )

    pd.DataFrame([asdict(adapter_audit)]).to_csv(output_dir / "adapter_audit.csv", index=False)
    pd.DataFrame([asdict(universe_audit)]).to_csv(output_dir / "universe_audit.csv", index=False)
    pqa.to_csv(output_dir / "person_day_qa.csv", index=False)
    support.to_csv(output_dir / "support_diagnostics.csv", index=False)
    curve.to_csv(output_dir / "time_participation_cells.csv", index=False)
    benchmark.to_csv(output_dir / "official_benchmark_comparison.csv", index=False)

    # Do not evaluate cross-city preregistered support on a one-city sample. It
    # becomes meaningful only after Santiago and México are reconstructed.
    metadata = {
        "city": "Bogotá 2015",
        "source": "official source XLSX preserved in repository",
        "source_trips": str(TRIPS.relative_to(ROOT)),
        "source_persons": str(PERSONS.relative_to(ROOT)),
        "historical_processed_lfs_used": False,
        "cross_city_support_evaluated": False,
        "scalar_result_created": False,
        "official_benchmark_scope": (
            "Bogotá population age 5+, workday, including walking trips under 15 min; "
            "benchmark used only as QA context"
        ),
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Bogotá official-source stage 1 complete: {output_dir}")
    print(benchmark.to_string(index=False))
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
