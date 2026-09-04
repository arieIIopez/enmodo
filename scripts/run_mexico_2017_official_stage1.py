#!/usr/bin/env python3
"""Paper I direct-source stage 1 for the 2017 ZMVM EOD.

Downloads the official INEGI CSV package, verifies its frozen SHA-256, rebuilds
weekday person-days directly from TVIAJE/TSDEM, and emits QA/support outputs.
No scalar coefficient, city ranking or cross-city support is calculated here.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from io import BytesIO
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mexico2017_official_adapter import build_mexico_2017_from_official
from scripts.mobility_function import estimate_time_participation_curve
from scripts.person_day import person_day_qa
from scripts.support_diagnostics import support_diagnostics

URL = "https://www.inegi.org.mx/contenidos/programas/eod/2017/datosabiertos/eod_2017_csv.zip"
EXPECTED_SHA256 = "120a43445039f5b9bbc7ff0c7365f8549e0bc1091ef828df7555e00cc4116a3a"
TVIAJE = "tviaje_eod2017/conjunto_de_datos/tviaje.csv"
TSDEM = "tsdem_eod2017/conjunto_de_datos/tsdem.csv"


def _load_official() -> tuple[pd.DataFrame, pd.DataFrame, str]:
    r = requests.get(
        URL,
        timeout=180,
        headers={"User-Agent": "ENMODO Paper I reproducibility audit"},
    )
    r.raise_for_status()
    digest = hashlib.sha256(r.content).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError(f"INEGI package SHA-256 changed: expected {EXPECTED_SHA256}, got {digest}")
    with zipfile.ZipFile(BytesIO(r.content)) as zf:
        trips = pd.read_csv(zf.open(TVIAJE), dtype=str, low_memory=False)
        persons = pd.read_csv(zf.open(TSDEM), dtype=str, low_memory=False)
    return trips, persons, digest


def run(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    trips, persons, digest = _load_official()
    person_days, universe, exclusions, adapter_audit, universe_audit = (
        build_mexico_2017_from_official(trips, persons)
    )

    pqa = person_day_qa(person_days)
    support = support_diagnostics(person_days)
    curve = estimate_time_participation_curve(person_days)

    total_weight = float(universe["weight"].sum())
    traveller_weight = float(universe.loc[universe["travelled"], "weight"].sum())
    nontraveller_weight = total_weight - traveller_weight

    # This is a direct source-total QA, not a target used to tune the adapter.
    weekday = trips.loc[trips["p5_3"].astype("string").str.strip().eq("1")].copy()
    weekday_factor = pd.to_numeric(weekday["factor"], errors="coerce")
    if weekday_factor.isna().any():
        raise ValueError("INEGI weekday trip factor contains non-numeric values")
    expanded_weekday_trips = float(weekday_factor.sum())

    universe_summary = pd.DataFrame(
        [
            {"quantity": "population_6plus_full_zmvm", "expanded_value": total_weight},
            {"quantity": "weekday_travellers", "expanded_value": traveller_weight},
            {"quantity": "weekday_nontravellers", "expanded_value": nontraveller_weight},
            {
                "quantity": "weighted_weekday_traveller_share",
                "expanded_value": traveller_weight / total_weight if total_weight > 0 else float("nan"),
            },
            {"quantity": "expanded_weekday_trip_rows", "expanded_value": expanded_weekday_trips},
        ]
    )

    pd.DataFrame([asdict(adapter_audit)]).to_csv(output_dir / "adapter_audit.csv", index=False)
    pd.DataFrame([asdict(universe_audit)]).to_csv(output_dir / "universe_audit.csv", index=False)
    exclusions.to_csv(output_dir / "diary_exclusions.csv", index=False)
    universe_summary.to_csv(output_dir / "weekday_universe_summary.csv", index=False)
    pqa.to_csv(output_dir / "person_day_qa.csv", index=False)
    support.to_csv(output_dir / "support_diagnostics.csv", index=False)
    curve.to_csv(output_dir / "time_participation_cells.csv", index=False)

    metadata = {
        "city_label_current": str(person_days["city"].iloc[0]),
        "primary_geographic_domain": "official full ZMVM EOD domain",
        "primary_population_domain": "residents aged 6+ represented by TSDEM",
        "primary_day_domain": "weekday p5_3=1 (Tuesday, Wednesday or Thursday survey day)",
        "source_url": URL,
        "source_sha256": digest,
        "source_tviaje_member": TVIAJE,
        "source_tsdem_member": TSDEM,
        "historical_processed_lfs_used": False,
        "diary_quality_rule": (
            "whole weekday diary excluded from T|P1 for invalid time, contradictory home semantics, "
            "unknown purpose or declared/observed trip-count mismatch; person remains in population universe"
        ),
        "external_benchmark_used_as_calibration_target": False,
        "cross_city_support_evaluated": False,
        "scalar_result_created": False,
    }
    (output_dir / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(f"Mexico/ZMVM official-source stage 1 complete: {output_dir}")
    print(universe_summary.to_string(index=False))
    print("\nDiary exclusions:")
    print(exclusions.to_string(index=False))
    print("No scalar-compressibility result was calculated.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs/mexico_2017_official_stage1",
    )
    args = parser.parse_args()
    run(args.output_dir.resolve())


if __name__ == "__main__":
    main()
