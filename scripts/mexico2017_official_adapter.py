"""Direct INEGI EOD 2017 adapter for Paper I.

The adapter reads official TVIAJE/TSDEM tables, selects the weekday diary
(p5_3=1), reconstructs trip durations, excludes entire inconsistent diaries
from T|P1, and keeps the full TSDEM population universe for traveller/non-
traveller inference. No legacy ENMODO processed file is used.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd

from scripts.person_day import PersonDayColumns, build_person_days_from_trips
from scripts.person_universe import UniverseAudit, mexico_2017_person_universe


@dataclass(frozen=True)
class MexicoOfficialAdapterAudit:
    city: str
    source_trip_rows: int
    weekday_trip_rows: int
    source_person_rows: int
    weekday_travelling_persons: int
    analysis_trip_rows: int
    analysis_persons: int
    excluded_invalid_time_persons: int
    excluded_home_conflict_persons: int
    excluded_unknown_purpose_persons: int
    excluded_tripcount_mismatch_persons: int
    excluded_any_quality_persons: int
    notes: str = ""


def _require(df: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{label}: missing required columns {missing}")


def _clean(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for col in out.columns:
        out[col] = out[col].astype("string").str.strip()
    return out


def _clock_component(series: pd.Series, *, maximum: int, label: str) -> tuple[pd.Series, pd.Series]:
    numeric = pd.to_numeric(series, errors="coerce")
    invalid = series.isna() | series.isin(["", "99"]) | numeric.isna() | (numeric < 0) | (numeric > maximum)
    return numeric, invalid


def prepare_mexico_2017_official(
    trips: pd.DataFrame,
    persons: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, MexicoOfficialAdapterAudit]:
    """Prepare a canonical weekday trip table from official INEGI EOD 2017.

    Quality rule for the confirmatory T|P1 sample:
    - if any weekday trip for a person has an invalid HH/MM field, exclude that
      person's entire weekday diary;
    - if destination-home (p5_11a=01) and purpose-home (p5_13=01) disagree on
      any trip, exclude the entire diary;
    - if purpose is blank/99 on any weekday trip, exclude the entire diary;
    - if TSDEM p5_4 does not equal the number of weekday TVIAJE rows, exclude
      the entire diary.

    Excluded diaries remain in the population universe and retain their observed
    traveller status. The adapter never repairs a diary silently.
    """
    city = "Ciudad de México 2017"
    trip_required = [
        "id_via", "id_soc", "p5_3", "p5_9_1", "p5_9_2", "p5_10_1", "p5_10_2",
        "p5_11a", "p5_13", "factor", "upm_dis", "est_dis",
    ]
    person_required = ["id_soc", "p5_4", "factor", "upm_dis", "est_dis"]
    _require(trips, trip_required, f"{city} official TVIAJE")
    _require(persons, person_required, f"{city} official TSDEM")

    t_all = _clean(trips)
    p = _clean(persons)
    if p["id_soc"].isna().any() or p["id_soc"].eq("").any():
        raise ValueError(f"{city}: TSDEM id_soc contains missing values")
    if p.duplicated("id_soc").any():
        raise ValueError(f"{city}: TSDEM must contain one row per id_soc")

    weekday = t_all.loc[t_all["p5_3"] == "1"].copy()
    if weekday.empty:
        raise ValueError(f"{city}: no p5_3=1 weekday trips found")
    if weekday["id_via"].isna().any() or weekday["id_soc"].isna().any():
        raise ValueError(f"{city}: missing trip/person identifiers in weekday TVIAJE")
    if weekday.duplicated("id_via").any():
        raise ValueError(f"{city}: duplicate id_via values in weekday TVIAJE")

    # Person weight/design variables must be internally constant in weekday trips.
    for col in ["factor", "upm_dis", "est_dis"]:
        variation = weekday.groupby("id_soc", observed=True)[col].nunique(dropna=False)
        if (variation > 1).any():
            examples = variation[variation > 1].index[:10].tolist()
            raise ValueError(f"{city}: {col} varies within person; examples={examples}")

    factor = pd.to_numeric(weekday["factor"], errors="coerce")
    if factor.isna().any() or (~np.isfinite(factor)).any() or (factor <= 0).any():
        raise ValueError(f"{city}: invalid weekday factor values")
    weekday["_factor"] = factor.astype(float)

    # TSDEM declared weekday trips vs observed TVIAJE rows.
    observed = weekday.groupby("id_soc", observed=True).size().rename("observed")
    declared = pd.to_numeric(p.set_index("id_soc")["p5_4"], errors="coerce").rename("declared")
    compare = declared.to_frame().join(observed, how="outer")
    compare["observed"] = compare["observed"].fillna(0).astype(int)
    # Blank p5_4 is the no-weekday-trip state; only positive observed rows with
    # blank declaration are a mismatch.
    declared_for_compare = compare["declared"].fillna(0).astype(float)
    mismatch_ids = set(compare.index[declared_for_compare != compare["observed"].astype(float)].astype(str))

    sh, bad_sh = _clock_component(weekday["p5_9_1"], maximum=23, label="p5_9_1")
    sm, bad_sm = _clock_component(weekday["p5_9_2"], maximum=59, label="p5_9_2")
    eh, bad_eh = _clock_component(weekday["p5_10_1"], maximum=23, label="p5_10_1")
    em, bad_em = _clock_component(weekday["p5_10_2"], maximum=59, label="p5_10_2")
    bad_time = bad_sh | bad_sm | bad_eh | bad_em
    invalid_time_ids = set(weekday.loc[bad_time, "id_soc"].astype(str))

    dest_home = weekday["p5_11a"] == "01"
    purpose_home = weekday["p5_13"] == "01"
    home_conflict_ids = set(weekday.loc[dest_home != purpose_home, "id_soc"].astype(str))
    unknown_purpose = weekday["p5_13"].isna() | weekday["p5_13"].isin(["", "99"])
    unknown_purpose_ids = set(weekday.loc[unknown_purpose, "id_soc"].astype(str))

    excluded_ids = invalid_time_ids | home_conflict_ids | unknown_purpose_ids | mismatch_ids
    analysis = weekday.loc[~weekday["id_soc"].isin(excluded_ids)].copy()
    if analysis.empty:
        raise ValueError(f"{city}: no weekday trips remain after diary-level QA")

    # Recalculate times on the quality-retained rows. Since all components were
    # validated above, conversion cannot introduce missing values here.
    start_minutes = pd.to_numeric(analysis["p5_9_1"]) * 60 + pd.to_numeric(analysis["p5_9_2"])
    end_minutes = pd.to_numeric(analysis["p5_10_1"]) * 60 + pd.to_numeric(analysis["p5_10_2"])
    duration = end_minutes - start_minutes
    duration.loc[duration < 0] += 1440
    if (duration < 0).any() or (duration > 1440).any():
        raise ValueError(f"{city}: invalid reconstructed weekday durations")

    canonical = pd.DataFrame(
        {
            "person_id": analysis["id_soc"].astype(str),
            "trip_id": analysis["id_via"].astype(str),
            "duration_minutes": duration.astype(float),
            "purpose": analysis["p5_13"].astype(str),
            "person_weight": analysis["_factor"].astype(float),
            "id_soc": analysis["id_soc"].astype(str),
        }
    )

    exclusion = pd.DataFrame(
        [
            {"reason": "invalid_time", "n_persons": len(invalid_time_ids)},
            {"reason": "home_semantics_conflict", "n_persons": len(home_conflict_ids)},
            {"reason": "unknown_purpose", "n_persons": len(unknown_purpose_ids)},
            {"reason": "tripcount_mismatch", "n_persons": len(mismatch_ids)},
            {"reason": "any_quality_exclusion", "n_persons": len(excluded_ids)},
        ]
    )

    audit = MexicoOfficialAdapterAudit(
        city=city,
        source_trip_rows=int(len(t_all)),
        weekday_trip_rows=int(len(weekday)),
        source_person_rows=int(len(p)),
        weekday_travelling_persons=int(weekday["id_soc"].nunique()),
        analysis_trip_rows=int(len(canonical)),
        analysis_persons=int(canonical["person_id"].nunique()),
        excluded_invalid_time_persons=int(len(invalid_time_ids)),
        excluded_home_conflict_persons=int(len(home_conflict_ids)),
        excluded_unknown_purpose_persons=int(len(unknown_purpose_ids)),
        excluded_tripcount_mismatch_persons=int(len(mismatch_ids)),
        excluded_any_quality_persons=int(len(excluded_ids)),
        notes=(
            "Direct official INEGI reconstruction. Primary domain is the full ZMVM population "
            "aged 6+ represented by TSDEM. Diary QA excludes whole inconsistent weekday diaries "
            "from T|P1 but not from the population universe."
        ),
    )
    return canonical, p, exclusion, audit


def build_mexico_2017_from_official(
    trips: pd.DataFrame,
    persons: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, MexicoOfficialAdapterAudit, UniverseAudit]:
    canonical, persons_clean, exclusion, audit = prepare_mexico_2017_official(trips, persons)

    person_days = build_person_days_from_trips(
        canonical,
        city="Ciudad de México 2017",
        columns=PersonDayColumns(
            person="person_id",
            trip="trip_id",
            time_minutes="duration_minutes",
            purpose="purpose",
            person_weight="person_weight",
        ),
        home_return_values=["01"],
    )

    # Traveller status uses all official weekday trips, not only QA-retained
    # diaries. This keeps diary quality separate from the population estimand.
    all_weekday = _clean(trips)
    all_weekday = all_weekday.loc[all_weekday["p5_3"] == "1", ["id_soc"]].copy()
    universe, universe_audit = mexico_2017_person_universe(persons_clean, all_weekday)
    return person_days, universe, exclusion, audit, universe_audit
