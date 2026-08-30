#!/usr/bin/env python3
"""Audit a historical GTFS ZIP before it is admitted into ENMODO accessibility analysis.

This utility intentionally performs no routing. It establishes whether a recovered
historical artifact is structurally usable and records the evidence needed to decide
whether it may serve as topology, schedule, and/or frequency input.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

CORE = ["agency.txt", "routes.txt", "stops.txt", "trips.txt", "stop_times.txt"]
OPTIONAL = [
    "calendar.txt",
    "calendar_dates.txt",
    "frequencies.txt",
    "shapes.txt",
    "feed_info.txt",
    "transfers.txt",
]


def sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        while chunk := fh.read(chunk_size):
            h.update(chunk)
    return h.hexdigest()


def _rows(zf: zipfile.ZipFile, name: str):
    with zf.open(name) as raw:
        text = (line.decode("utf-8-sig", errors="replace") for line in raw)
        yield from csv.DictReader(text)


def _date(value: str | None):
    if not value:
        return None
    value = value.strip()
    try:
        return datetime.strptime(value, "%Y%m%d").date().isoformat()
    except ValueError:
        return None


def audit(path: Path) -> dict:
    report = {
        "artifact": str(path),
        "sha256": sha256(path),
        "zip_size_bytes": path.stat().st_size,
        "members": {},
        "core_missing": [],
        "counts": {},
        "route_types": {},
        "service_dates": {"min": None, "max": None},
        "coordinate_quality": {},
        "relational_checks": {},
        "role_evidence": {
            "topology": "unknown",
            "schedule": "unknown",
            "frequency": "unknown",
        },
        "warnings": [],
    }

    with zipfile.ZipFile(path) as zf:
        names = {Path(n).name: n for n in zf.namelist() if not n.endswith("/")}
        for name in CORE + OPTIONAL:
            report["members"][name] = name in names
        report["core_missing"] = [x for x in CORE if x not in names]
        if report["core_missing"]:
            report["warnings"].append(
                "Missing GTFS core files: " + ", ".join(report["core_missing"])
            )

        for name in CORE + OPTIONAL:
            if name in names:
                report["counts"][name] = sum(1 for _ in _rows(zf, names[name]))

        routes = {}
        if "routes.txt" in names:
            types = Counter()
            for row in _rows(zf, names["routes.txt"]):
                rid = (row.get("route_id") or "").strip()
                if rid:
                    routes[rid] = row
                types[(row.get("route_type") or "").strip()] += 1
            report["route_types"] = dict(sorted(types.items()))

        stops = {}
        invalid_coords = 0
        outside_basic_metro_box = 0
        if "stops.txt" in names:
            for row in _rows(zf, names["stops.txt"]):
                sid = (row.get("stop_id") or "").strip()
                if sid:
                    stops[sid] = row
                try:
                    lat = float(row.get("stop_lat", ""))
                    lon = float(row.get("stop_lon", ""))
                    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                        invalid_coords += 1
                    # Broad sanity box only, NOT the EOD study-area clip.
                    if not (18.7 <= lat <= 20.3 and -100.2 <= lon <= -98.2):
                        outside_basic_metro_box += 1
                except (TypeError, ValueError):
                    invalid_coords += 1
            report["coordinate_quality"] = {
                "stops": len(stops),
                "invalid_or_missing": invalid_coords,
                "outside_broad_sanity_box": outside_basic_metro_box,
            }

        trips = {}
        if "trips.txt" in names:
            missing_route = 0
            for row in _rows(zf, names["trips.txt"]):
                tid = (row.get("trip_id") or "").strip()
                if tid:
                    trips[tid] = row
                rid = (row.get("route_id") or "").strip()
                if routes and rid not in routes:
                    missing_route += 1
            report["relational_checks"]["trips_with_missing_route"] = missing_route

        if "stop_times.txt" in names:
            missing_trip = 0
            missing_stop = 0
            rows = 0
            for row in _rows(zf, names["stop_times.txt"]):
                rows += 1
                if trips and (row.get("trip_id") or "").strip() not in trips:
                    missing_trip += 1
                if stops and (row.get("stop_id") or "").strip() not in stops:
                    missing_stop += 1
            report["relational_checks"].update(
                {
                    "stop_times_rows": rows,
                    "stop_times_with_missing_trip": missing_trip,
                    "stop_times_with_missing_stop": missing_stop,
                }
            )

        dates = []
        if "calendar.txt" in names:
            for row in _rows(zf, names["calendar.txt"]):
                for field in ("start_date", "end_date"):
                    d = _date(row.get(field))
                    if d:
                        dates.append(d)
        if "calendar_dates.txt" in names:
            for row in _rows(zf, names["calendar_dates.txt"]):
                d = _date(row.get("date"))
                if d:
                    dates.append(d)
        if dates:
            report["service_dates"] = {"min": min(dates), "max": max(dates)}

        topology_ok = not report["core_missing"] and bool(routes) and bool(stops) and bool(trips)
        schedule_ok = topology_ok and "stop_times.txt" in names and (
            "calendar.txt" in names or "calendar_dates.txt" in names
        )
        frequency_present = "frequencies.txt" in names and report["counts"].get("frequencies.txt", 0) > 0
        report["role_evidence"] = {
            "topology": "structurally_supported" if topology_ok else "not_supported",
            "schedule": "structurally_supported" if schedule_ok else "not_supported",
            "frequency": "explicit_frequencies_present" if frequency_present else "not_explicit",
        }

    return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("zip", type=Path)
    p.add_argument("--expected-sha256")
    p.add_argument("--output", type=Path)
    args = p.parse_args()

    if not args.zip.exists():
        raise SystemExit(f"GTFS artifact not found: {args.zip}")

    actual = sha256(args.zip)
    if args.expected_sha256 and actual != args.expected_sha256.lower():
        raise SystemExit(
            f"SHA-256 mismatch: expected {args.expected_sha256.lower()}, got {actual}"
        )

    report = audit(args.zip)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
