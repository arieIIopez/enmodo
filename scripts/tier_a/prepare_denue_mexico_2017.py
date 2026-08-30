#!/usr/bin/env python3
"""Prepare the pre-specified DENUE 03/2017 Tier A.1 opportunity layer.

The script deliberately does NOT download data. Input artifacts must already be present
locally and must match the SHA-256 values frozen in the research manifest. This keeps
acquisition/provenance separate from transformation and makes a wrong or silently updated
mirror artifact fail closed.

Tier A.1 uses external opportunity supply with geometry only. It is a development and
construct-validation layer; confirmatory transport accessibility requires the Tier A.2
historical network pipeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Iterable

EXPECTED = {
    "09": (
        "denue_201703_09.parquet",
        "c808122adbb8ba9360a6b175c2a8ad58d30daea594c055d889524b389a47d809",
    ),
    "13": (
        "denue_201703_13.parquet",
        "27b0937bddb6131d3c9bcc825489725bd73363366dc7868be40a3a58174aaf35",
    ),
    "15": (
        "denue_201703_15.parquet",
        "ad3ae1e3fe4353c3f7dbd01afbc2bfc66a6a17f412fc40bd283454daa44318e7",
    ),
}

PRIMARY_DOMAINS = {
    "education": ("61",),
    "health_social_assistance": ("62",),
    "arts_entertainment_recreation": ("71",),
}
SENSITIVITY_DOMAINS = {
    "expanded_social_leisure": ("71", "72"),
}


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def validate_inputs(input_dir: Path) -> dict[str, Path]:
    validated: dict[str, Path] = {}
    failures: list[str] = []
    for state, (name, expected_hash) in EXPECTED.items():
        path = input_dir / name
        if not path.exists():
            failures.append(f"missing {path}")
            continue
        actual = sha256(path)
        if actual != expected_hash:
            failures.append(
                f"SHA-256 mismatch for {name}: expected {expected_hash}, got {actual}"
            )
            continue
        validated[state] = path
    if failures:
        raise SystemExit("Input validation failed:\n- " + "\n- ".join(failures))
    return validated


def _prefix_mask(series, prefixes: Iterable[str]):
    text = series.astype("string").str.strip()
    mask = False
    for prefix in prefixes:
        mask = mask | text.str.startswith(prefix, na=False)
    return mask


def prepare(input_dir: Path, output_dir: Path, study_area: Path | None) -> None:
    try:
        import geopandas as gpd
        import pandas as pd
    except ImportError as exc:
        raise SystemExit(
            "geopandas and pandas are required for transformation; hash validation itself "
            "uses only the standard library."
        ) from exc

    inputs = validate_inputs(input_dir)
    frames = []
    audit = {
        "release": "2017-03",
        "source_states": sorted(inputs),
        "input_files": {},
        "rows_raw": 0,
        "rows_valid_geometry": 0,
        "rows_in_study_area": None,
        "domains": {},
        "warnings": [],
    }

    for state, path in inputs.items():
        gdf = gpd.read_parquet(path)
        audit["input_files"][state] = {
            "path": str(path),
            "sha256": sha256(path),
            "rows": int(len(gdf)),
        }
        frames.append(gdf)

    gdf = pd.concat(frames, ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=frames[0].crs)
    audit["rows_raw"] = int(len(gdf))

    valid = gdf.geometry.notna() & ~gdf.geometry.is_empty & gdf.geometry.is_valid
    audit["rows_valid_geometry"] = int(valid.sum())
    if int((~valid).sum()):
        audit["warnings"].append(
            f"{int((~valid).sum())} records excluded from spatial layer because geometry is null/empty/invalid."
        )
    gdf = gdf.loc[valid].copy()

    if study_area is not None:
        area = gpd.read_file(study_area)
        if area.empty:
            raise SystemExit("Study-area file is empty")
        if area.crs is None:
            raise SystemExit("Study-area CRS is undefined")
        if gdf.crs is None:
            raise SystemExit("DENUE GeoParquet CRS is undefined")
        area = area.to_crs(gdf.crs)
        union = area.geometry.union_all() if hasattr(area.geometry, "union_all") else area.unary_union
        gdf = gdf.loc[gdf.geometry.intersects(union)].copy()
        audit["rows_in_study_area"] = int(len(gdf))
    else:
        audit["warnings"].append(
            "No study-area polygon supplied. Output includes all establishments in states 09, 13 and 15 and MUST NOT be treated as a ZMVM accessibility layer."
        )

    # The 2016+ DENUE schema uses codigo_act in the mxcensus harmonized representation.
    if "codigo_act" not in gdf.columns:
        candidates = [c for c in gdf.columns if c.lower() == "codigo_act"]
        if not candidates:
            raise SystemExit("Expected DENUE activity field 'codigo_act' not found")
        gdf = gdf.rename(columns={candidates[0]: "codigo_act"})

    output_dir.mkdir(parents=True, exist_ok=True)
    keep_base = [
        c
        for c in [
            "id",
            "clee",
            "nom_estab",
            "codigo_act",
            "nombre_act",
            "per_ocu",
            "cve_ent",
            "cve_mun",
            "cve_loc",
            "geometry",
        ]
        if c in gdf.columns
    ]

    for domain, prefixes in {**PRIMARY_DOMAINS, **SENSITIVITY_DOMAINS}.items():
        layer = gdf.loc[_prefix_mask(gdf["codigo_act"], prefixes), keep_base].copy()
        path = output_dir / f"mexico_2017_denue_{domain}.parquet"
        layer.to_parquet(path, index=False)
        audit["domains"][domain] = {
            "scian_prefixes": list(prefixes),
            "establishments": int(len(layer)),
            "output": str(path),
        }

    with (output_dir / "mexico_2017_denue_tier_a1_audit.json").open("w", encoding="utf-8") as fh:
        json.dump(audit, fh, ensure_ascii=False, indent=2)

    print(json.dumps(audit, ensure_ascii=False, indent=2))


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser()
    p.add_argument("--input-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument(
        "--study-area",
        type=Path,
        default=None,
        help="Polygon layer defining the EOD 2017 study area. Strongly recommended.",
    )
    return p


if __name__ == "__main__":
    args = parser().parse_args()
    prepare(args.input_dir, args.output_dir, args.study_area)
