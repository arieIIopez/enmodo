"""Direct adapters from official EOD source tables to Paper I person-days.

This module avoids historical ENMODO ``viajes_personas`` intermediates. Official
survey tables are joined and transformed explicitly, with historical notebooks
and dedicated audits used only to verify source semantics.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
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
    missing_day_flag_rows: int = 0
    workday_households: int = 0
    nonworkday_households: int = 0
    unassigned_households: int = 0
    workday_universe_persons: int = 0
    notes: str = ""


def _require(df: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{label}: missing required columns {missing}")


def _normalize_text(value: object) -> str:
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _normalize_id(series: pd.Series) -> pd.Series:
    if series.isna().any():
        raise ValueError("identifier contains missing values")
    return series.astype(str).str.strip().str.replace(r"\.0$", "", regex=True)


def _numeric_decimal_comma(series: pd.Series, label: str) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        out = pd.to_numeric(series, errors="coerce")
    else:
        cleaned = series.astype("string").str.strip().str.replace(",", ".", regex=False)
        out = pd.to_numeric(cleaned, errors="coerce")
    if out.isna().any() or (~np.isfinite(out)).any():
        raise ValueError(f"{label}: contains missing/non-numeric values after decimal conversion")
    return out.astype(float)


def _composite_key(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    parts = [_normalize_id(df[col]) for col in columns]
    key = parts[0]
    for part in parts[1:]:
        key = key + "::" + part
    return key


def _clock_minutes(series: pd.Series, label: str) -> pd.Series:
    """Parse survey clock fields to minutes from midnight.

    Exact 24:00[:00] is accepted as 1440 because the Bogotá delivery uses it to
    denote midnight at the end of the diary day. Other 24:xx values are invalid.
    """
    if series.isna().any():
        raise ValueError(f"{label}: contains missing clock values")

    values: list[float] = []
    clock_re = re.compile(r"(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}(?:\.\d+)?))?$")
    for value in series.tolist():
        if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
            x = float(value)
            if not np.isfinite(x):
                raise ValueError(f"{label}: non-finite clock value")
            if 0 <= x < 1:
                values.append(x * 1440.0)
                continue
            if 0 <= x <= 2400 and x.is_integer():
                hhmm = int(x)
                if hhmm == 2400:
                    values.append(1440.0)
                    continue
                hh, mm = divmod(hhmm, 100)
                if 0 <= hh <= 23 and 0 <= mm <= 59:
                    values.append(float(hh * 60 + mm))
                    continue
            raise ValueError(f"{label}: unsupported numeric clock value {value!r}")

        text = str(value).strip()
        match = clock_re.search(text)
        if not match:
            raise ValueError(f"{label}: unparseable clock value {value!r}")
        h = int(match.group("h"))
        m = int(match.group("m"))
        s = float(match.group("s")) if match.group("s") is not None else 0.0
        if h == 24 and m == 0 and s == 0:
            values.append(1440.0)
            continue
        if not (0 <= h <= 23 and 0 <= m <= 59 and 0 <= s < 60):
            raise ValueError(f"{label}: invalid clock value {value!r}")
        values.append(h * 60.0 + m + s / 60.0)
    return pd.Series(values, index=series.index, dtype=float)


def _binary_yes_mask(series: pd.Series, city: str, field: str) -> tuple[pd.Series, pd.Series]:
    """Decode an S/N-style survey flag without imputing missing values."""
    missing = series.isna() | series.astype("string").str.strip().eq("")
    norm = series.loc[~missing].map(_normalize_text)
    yes = {"s", "si", "1", "true"}
    no = {"n", "no", "0", "false"}
    unknown = sorted(set(norm.unique()).difference(yes | no))
    if unknown:
        raise ValueError(f"{city}: unsupported non-missing {field} values {unknown[:20]}")
    mask = pd.Series(False, index=series.index, dtype=bool)
    mask.loc[~missing] = norm.isin(yes)
    return mask, missing


def prepare_bogota_2015_official(
    trips: pd.DataFrame,
    persons: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, OfficialAdapterAudit]:
    """Build Bogotá 2015 workday trips and the matching person universe.

    The official delivery contains two separately calibrated household
    subsamples: weekday and non-weekday. The primary workday universe therefore
    consists of all persons in households assigned to the weekday subsample,
    including people with zero trips. A person from the non-weekday subsample
    must never be labelled a weekday non-traveller.

    Household assignment is reconstructed from the two explicit trip flags
    ``DIA_HABIL`` and ``DIA_NOHABIL``. Mixed or unassigned households fail
    loudly, so the production rule encodes the structure verified by the
    independent day-assignment audit rather than relying on a hidden assumption.
    """
    city = "Bogotá 2015"
    trip_required = [
        "ID_ENCUESTA", "NUMERO_PERSONA", "NUMERO_VIAJE", "MOTIVOVIAJE",
        "HORA_INICIO", "HORA_FIN", "DIA_HABIL", "DIA_NOHABIL",
    ]
    person_required = ["ID_ENCUESTA", "NUMERO_PERSONA", "PONDERADOR_CALIBRADO"]
    _require(trips, trip_required, f"{city} official trips")
    _require(persons, person_required, f"{city} official persons")

    p = persons.copy()
    p["_household_key"] = _normalize_id(p["ID_ENCUESTA"])
    p["_person_key"] = _composite_key(p, ["ID_ENCUESTA", "NUMERO_PERSONA"])
    if p.duplicated("_person_key").any():
        examples = p.loc[p.duplicated("_person_key", keep=False), "_person_key"].head(10).tolist()
        raise ValueError(f"{city}: duplicate person keys in official person table; examples={examples}")
    p["_paper1_weight"] = _numeric_decimal_comma(
        p["PONDERADOR_CALIBRADO"], f"{city} PONDERADOR_CALIBRADO"
    )
    if (p["_paper1_weight"] < 0).any():
        raise ValueError(f"{city}: person weights must be non-negative")

    workday_mask, workday_missing = _binary_yes_mask(trips["DIA_HABIL"], city, "DIA_HABIL")
    nonworkday_mask, nonworkday_missing = _binary_yes_mask(
        trips["DIA_NOHABIL"], city, "DIA_NOHABIL"
    )
    both_row_flags = workday_mask & nonworkday_mask
    if both_row_flags.any():
        raise ValueError(f"{city}: trip rows cannot be both DIA_HABIL and DIA_NOHABIL")

    trip_households = _normalize_id(trips["ID_ENCUESTA"])
    workday_households = set(trip_households.loc[workday_mask])
    nonworkday_households = set(trip_households.loc[nonworkday_mask])
    mixed = sorted(workday_households.intersection(nonworkday_households))
    if mixed:
        raise ValueError(
            f"{city}: households mix weekday and non-weekday day flags; examples={mixed[:10]}"
        )
    if not workday_households:
        raise ValueError(f"{city}: no households assigned to workday subsample")

    all_person_households = set(p["_household_key"])
    assigned_households = workday_households | nonworkday_households
    unassigned = sorted(all_person_households.difference(assigned_households))
    if unassigned:
        raise ValueError(
            f"{city}: person households lack any weekday/non-weekday trip assignment; examples={unassigned[:10]}"
        )

    t = trips.loc[workday_mask].copy()
    t["_person_key"] = _composite_key(t, ["ID_ENCUESTA", "NUMERO_PERSONA"])
    t["_start_minutes"] = _clock_minutes(t["HORA_INICIO"], f"{city} HORA_INICIO")
    t["_end_minutes"] = _clock_minutes(t["HORA_FIN"], f"{city} HORA_FIN")
    t["duration_minutes"] = t["_end_minutes"] - t["_start_minutes"]
    overnight = t["duration_minutes"] < 0
    t.loc[overnight, "duration_minutes"] += 1440.0
    if (t["duration_minutes"] < 0).any() or (~np.isfinite(t["duration_minutes"])).any():
        raise ValueError(f"{city}: invalid reconstructed trip durations")

    t = t.merge(
        p[["_person_key", "_paper1_weight"]],
        on="_person_key",
        how="left",
        validate="many_to_one",
    )
    if t["_paper1_weight"].isna().any():
        examples = t.loc[t["_paper1_weight"].isna(), "_person_key"].head(10).tolist()
        raise ValueError(f"{city}: workday travellers missing from person table; examples={examples}")

    if t["MOTIVOVIAJE"].isna().any():
        raise ValueError(f"{city}: missing MOTIVOVIAJE in selected workday trips")
    if not t["MOTIVOVIAJE"].map(_normalize_text).eq("volver a casa").any():
        raise ValueError(f"{city}: literal 'Volver a casa' absent; purpose semantics must be audited")

    canonical = pd.DataFrame(
        {
            "person_id": t["_person_key"].astype(str),
            "trip_id": _composite_key(t, ["ID_ENCUESTA", "NUMERO_PERSONA", "NUMERO_VIAJE"]),
            "duration_minutes": t["duration_minutes"].astype(float),
            "purpose": t["MOTIVOVIAJE"].astype(str).str.strip(),
            "person_weight": t["_paper1_weight"].astype(float),
            "ID_ENCUESTA": _normalize_id(t["ID_ENCUESTA"]),
            "NUMERO_PERSONA": _normalize_id(t["NUMERO_PERSONA"]),
            "NUMERO_VIAJE": t["NUMERO_VIAJE"],
        }
    )

    persons_for_universe = p.loc[p["_household_key"].isin(workday_households)].copy()
    if persons_for_universe.empty:
        raise ValueError(f"{city}: workday household universe is empty")
    persons_for_universe["PONDERADOR_CALIBRADO"] = persons_for_universe["_paper1_weight"]

    missing_both_flags = int((workday_missing & nonworkday_missing).sum())
    audit = OfficialAdapterAudit(
        city=city,
        source_trip_rows=int(len(trips)),
        selected_trip_rows=int(len(canonical)),
        source_person_rows=int(len(persons)),
        travelling_persons=int(canonical["person_id"].nunique()),
        missing_day_flag_rows=missing_both_flags,
        workday_households=int(len(workday_households)),
        nonworkday_households=int(len(nonworkday_households)),
        unassigned_households=int(len(unassigned)),
        workday_universe_persons=int(len(persons_for_universe)),
        notes=(
            "Direct official-source reconstruction. Workday universe is all persons in "
            "households identified by DIA_HABIL; separately calibrated DIA_NOHABIL households "
            "are excluded rather than treated as weekday non-travellers."
        ),
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

    selected_keys = canonical[["ID_ENCUESTA", "NUMERO_PERSONA"]].copy()
    universe_source = persons_for_universe.copy()
    universe_source["ID_ENCUESTA"] = _normalize_id(universe_source["ID_ENCUESTA"])
    universe_source["NUMERO_PERSONA"] = _normalize_id(universe_source["NUMERO_PERSONA"])
    universe, universe_audit = bogota_2015_person_universe(universe_source, selected_keys)
    return person_days, universe, audit, universe_audit
