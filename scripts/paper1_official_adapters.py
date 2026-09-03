"""Direct adapters from official EOD source tables to Paper I person-days.

This module is the preferred architecture for Paper I. It avoids depending on
historical ENMODO `viajes_personas` intermediate files, several of whose Git LFS
objects are no longer available. Official survey tables are joined and
transformed explicitly, with historical notebooks used only to audit semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
import unicodedata

import numpy as np
import pandas as pd

from scripts.person_day import PersonDayColumns, build_person_days_from_trips
from scripts.person_universe import UniverseAudit, bogota_2015_person_universe


@dataclass(frozen=True)
class OfficialAdapterAudit:
    city: str
    source_trip_rows: int
    selected_trip_rows: int
    source_person_rows: int
    travelling_persons: int
    notes: str = ""


def _require(df: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{label}: missing required columns {missing}")


def _normalize_text(value: object) -> str:
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _numeric_decimal_comma(series: pd.Series, label: str) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        out = pd.to_numeric(series, errors="coerce")
    else:
        cleaned = (
            series.astype("string")
            .str.strip()
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False)
        )
        out = pd.to_numeric(cleaned, errors="coerce")
    if out.isna().any() or (~np.isfinite(out)).any():
        raise ValueError(f"{label}: contains missing/non-numeric values after decimal conversion")
    return out.astype(float)


def _composite_key(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    parts: list[pd.Series] = []
    for col in columns:
        if df[col].isna().any():
            raise ValueError(f"composite key column {col!r} contains missing values")
        # Excel often turns integer identifiers into floats. Preserve semantic
        # identity by stripping a terminal .0 when the numeric value is integral.
        s = df[col].astype(str).str.strip().str.replace(r"\.0$", "", regex=True)
        parts.append(s)
    key = parts[0]
    for part in parts[1:]:
        key = key + "::" + part
    return key


def _clock_minutes(series: pd.Series, label: str) -> pd.Series:
    """Parse survey clock fields to minutes from midnight.

    Accepts HH:MM[:SS], pandas/Excel time-like values, and numeric Excel-day
    fractions. It deliberately rejects missing or unparseable values rather
    than imputing durations.
    """
    if series.isna().any():
        raise ValueError(f"{label}: contains missing clock values")

    values: list[float] = []
    for value in series.tolist():
        if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
            x = float(value)
            if not np.isfinite(x):
                raise ValueError(f"{label}: non-finite clock value")
            # Excel stores pure times as fractions of one day.
            if 0 <= x < 1:
                values.append(x * 1440.0)
                continue
            # Numeric HHMM is common in survey exports; handle only valid forms.
            if 0 <= x <= 2359 and float(x).is_integer():
                hhmm = int(x)
                hh, mm = divmod(hhmm, 100)
                if 0 <= hh <= 23 and 0 <= mm <= 59:
                    values.append(float(hh * 60 + mm))
                    continue
            raise ValueError(f"{label}: unsupported numeric clock value {value!r}")

        text = str(value).strip()
        # Handle datetime/time string representations by taking the final clock.
        match = pd.Series([text]).str.extract(r"(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}(?:\.\d+)?))?$").iloc[0]
        if match.isna().all():
            raise ValueError(f"{label}: unparseable clock value {value!r}")
        h = int(match["h"])
        m = int(match["m"])
        s = float(match["s"]) if pd.notna(match["s"]) else 0.0
        if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s < 60):
            raise ValueError(f"{label}: invalid clock value {value!r}")
        values.append(h * 60.0 + m + s / 60.0)
    return pd.Series(values, index=series.index, dtype=float)


def _workday_mask(series: pd.Series, city: str) -> pd.Series:
    norm = series.map(_normalize_text)
    yes = {"s", "si", "1", "true"}
    no = {"n", "no", "0", "false"}
    unknown = sorted(set(norm.unique()).difference(yes | no))
    if unknown:
        raise ValueError(f"{city}: unsupported DIA_HABIL values {unknown[:20]}")
    return norm.isin(yes)


def prepare_bogota_2015_official(
    trips: pd.DataFrame,
    persons: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, OfficialAdapterAudit]:
    """Build a canonical workday trip table directly from official 2015 XLSX.

    Historical ENMODO semantics audited from the original notebook:
    - trip/person key: ID_ENCUESTA + NUMERO_PERSONA
    - trip order/id: NUMERO_VIAJE
    - purpose: MOTIVOVIAJE (including literal `Volver a casa`)
    - workday flag: DIA_HABIL
    - duration: HORA_FIN - HORA_INICIO, adding 24 h when end < start
    - primary person weight: PONDERADOR_CALIBRADO from the PERSON table

    Trip-level calibrated weights are retained neither as primary person weights
    nor as substitutes when the person join fails.
    """
    city = "Bogotá 2015"
    trip_required = [
        "ID_ENCUESTA",
        "NUMERO_PERSONA",
        "NUMERO_VIAJE",
        "MOTIVOVIAJE",
        "HORA_INICIO",
        "HORA_FIN",
        "DIA_HABIL",
    ]
    person_required = ["ID_ENCUESTA", "NUMERO_PERSONA", "PONDERADOR_CALIBRADO"]
    _require(trips, trip_required, f"{city} official trips")
    _require(persons, person_required, f"{city} official persons")

    p = persons.copy()
    p["_person_key"] = _composite_key(p, ["ID_ENCUESTA", "NUMERO_PERSONA"])
    if p.duplicated("_person_key").any():
        examples = p.loc[p.duplicated("_person_key", keep=False), "_person_key"].head(10).tolist()
        raise ValueError(f"{city}: duplicate person keys in official person table; examples={examples}")
    p["_paper1_weight"] = _numeric_decimal_comma(
        p["PONDERADOR_CALIBRADO"], f"{city} PONDERADOR_CALIBRADO"
    )
    if (p["_paper1_weight"] < 0).any():
        raise ValueError(f"{city}: person weights must be non-negative")

    t = trips.loc[_workday_mask(trips["DIA_HABIL"], city)].copy()
    if t.empty:
        raise ValueError(f"{city}: no official workday trips selected")
    t["_person_key"] = _composite_key(t, ["ID_ENCUESTA", "NUMERO_PERSONA"])
    t["_start_minutes"] = _clock_minutes(t["HORA_INICIO"], f"{city} HORA_INICIO")
    t["_end_minutes"] = _clock_minutes(t["HORA_FIN"], f"{city} HORA_FIN")
    t["duration_minutes"] = t["_end_minutes"] - t["_start_minutes"]
    overnight = t["duration_minutes"] < 0
    t.loc[overnight, "duration_minutes"] += 1440.0
    if (t["duration_minutes"] < 0).any() or (~np.isfinite(t["duration_minutes"])).any():
        raise ValueError(f"{city}: invalid reconstructed trip durations")

    meta = p[["_person_key", "_paper1_weight"]].copy()
    t = t.merge(meta, on="_person_key", how="left", validate="many_to_one")
    if t["_paper1_weight"].isna().any():
        examples = t.loc[t["_paper1_weight"].isna(), "_person_key"].head(10).tolist()
        raise ValueError(f"{city}: workday travellers missing from person table; examples={examples}")

    if t["MOTIVOVIAJE"].isna().any():
        raise ValueError(f"{city}: missing MOTIVOVIAJE in selected workday trips")
    purpose_norm = t["MOTIVOVIAJE"].map(_normalize_text)
    if not purpose_norm.eq("volver a casa").any():
        raise ValueError(f"{city}: literal 'Volver a casa' absent; purpose semantics must be audited")

    # Create a stable canonical trip table for the generic person-day builder.
    canonical = pd.DataFrame(
        {
            "person_id": t["_person_key"].astype(str),
            "trip_id": _composite_key(t, ["ID_ENCUESTA", "NUMERO_PERSONA", "NUMERO_VIAJE"]),
            "duration_minutes": t["duration_minutes"].astype(float),
            "purpose": t["MOTIVOVIAJE"].astype(str).str.strip(),
            "person_weight": t["_paper1_weight"].astype(float),
            "ID_ENCUESTA": t["ID_ENCUESTA"].astype(str).str.replace(r"\.0$", "", regex=True),
            "NUMERO_PERSONA": t["NUMERO_PERSONA"].astype(str).str.replace(r"\.0$", "", regex=True),
            "NUMERO_VIAJE": t["NUMERO_VIAJE"],
        }
    )

    # Person-universe function expects numeric calibrated weight; pass the
    # normalized copy, not a silently coerced duplicate.
    persons_for_universe = p.copy()
    persons_for_universe["PONDERADOR_CALIBRADO"] = persons_for_universe["_paper1_weight"]

    audit = OfficialAdapterAudit(
        city=city,
        source_trip_rows=int(len(trips)),
        selected_trip_rows=int(len(canonical)),
        source_person_rows=int(len(persons)),
        travelling_persons=int(canonical["person_id"].nunique()),
        notes="Direct official-source reconstruction; no historical viajes_personas dependency.",
    )
    return canonical, persons_for_universe, audit


def build_bogota_2015_from_official(
    trips: pd.DataFrame,
    persons: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, OfficialAdapterAudit, UniverseAudit]:
    canonical, persons_for_universe, audit = prepare_bogota_2015_official(trips, persons)
    person_days = build_person_days_from_trips(
        canonical,
        city="Bogotá 2015",
        columns=PersonDayColumns(
            person="person_id",
            trip="trip_id",
            time_minutes="duration_minutes",
            purpose="purpose",
            person_weight="person_weight",
        ),
        home_return_values=["Volver a casa"],
    )

    # Reconstruct a trip frame with official key columns for the existing
    # universe logic. Traveller status is determined by the same selected
    # workday universe as the person-day builder.
    selected_keys = canonical[["ID_ENCUESTA", "NUMERO_PERSONA"]].copy()
    universe_source = persons_for_universe.copy()
    universe_source["ID_ENCUESTA"] = universe_source["ID_ENCUESTA"].astype(str).str.replace(r"\.0$", "", regex=True)
    universe_source["NUMERO_PERSONA"] = universe_source["NUMERO_PERSONA"].astype(str).str.replace(r"\.0$", "", regex=True)
    universe, universe_audit = bogota_2015_person_universe(universe_source, selected_keys)
    return person_days, universe, audit, universe_audit
