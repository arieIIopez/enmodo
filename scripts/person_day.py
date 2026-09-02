"""Reconstruct person-day records for the Mobility Coefficient programme.

The historical ENMODO `viajes_personas` files contain one row per observed trip
plus person attributes. This module reconstructs the confirmatory person-day
variables without reusing the legacy G6 aggregation:

    T_i  = sum_j t_ij
    P1_i = number of observed out-of-home activity episodes

Return-home trips contribute to T_i but do not increment P1_i.

Important: a trip table cannot recover non-travellers because people with zero
trips have no rows. Non-traveller rates must therefore come from the person
universe of each EOD, not from this module alone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import unicodedata

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PersonDayColumns:
    person: str
    trip: str
    time_minutes: str
    purpose: str
    person_weight: str


def _normalize_text(value: object) -> str:
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


EXPLICIT_MISSING_PURPOSE_LABELS = {
    "",
    "sin informacion",
    "sin info",
    "no informado",
    "no informa",
    "no sabe",
    "ns/nr",
    "n/a",
    "na",
    "none",
    "nan",
}


def _validate_required(df: pd.DataFrame, columns: PersonDayColumns) -> None:
    required = {
        columns.person,
        columns.trip,
        columns.time_minutes,
        columns.purpose,
        columns.person_weight,
    }
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"trip table is missing required columns: {missing}")


def build_person_days_from_trips(
    trips: pd.DataFrame,
    *,
    city: str,
    columns: PersonDayColumns,
    home_return_values: Sequence[str],
    max_trip_minutes: float | None = None,
    require_home_return_observed: bool = True,
) -> pd.DataFrame:
    """Aggregate a harmonised trip table to travelling person-days.

    Parameters
    ----------
    trips:
        One row per observed trip. If a source has stages, they must be reduced
        to trips before calling this function.
    city:
        City-year label written to the output.
    columns:
        Explicit source-column mapping. No semantic column guessing is done.
    home_return_values:
        Explicit purpose labels meaning return/home destination. Matching is
        case- and accent-insensitive after whitespace trimming.
    max_trip_minutes:
        Optional explicit sensitivity filter. None means no upper-duration
        trimming. The historical `<150 min` rule is intentionally NOT a default.
    require_home_return_observed:
        Fail if none of the declared home-return labels is observed. This is a
        guard against using an undecoded or wrongly mapped purpose column.

    Returns
    -------
    DataFrame with one row per travelling person-day and columns:
    city, person_id, t_minutes, r, weight, n_trips, n_home_returns,
    max_trip_minutes, p1_zero_with_travel.

    Notes
    -----
    - Person weights must be constant within person. Inconsistency raises.
    - Duplicate person-trip IDs raise; silent de-duplication is prohibited.
    - Missing or explicitly undecoded purpose labels raise.
    - This function does not infer diary validity beyond these checks.
    """
    _validate_required(trips, columns)
    if not city or not str(city).strip():
        raise ValueError("city must be a non-empty label")
    if not home_return_values:
        raise ValueError("home_return_values must be specified explicitly")
    if max_trip_minutes is not None and max_trip_minutes <= 0:
        raise ValueError("max_trip_minutes must be positive when supplied")

    df = trips[
        [
            columns.person,
            columns.trip,
            columns.time_minutes,
            columns.purpose,
            columns.person_weight,
        ]
    ].copy()

    if df[[columns.person, columns.trip]].isna().any().any():
        raise ValueError("person and trip identifiers must be non-missing")
    if df.duplicated([columns.person, columns.trip]).any():
        dup = (
            df.loc[df.duplicated([columns.person, columns.trip], keep=False),
                   [columns.person, columns.trip]]
            .drop_duplicates()
            .head(10)
            .to_dict("records")
        )
        raise ValueError(f"duplicate person-trip identifiers found; examples: {dup}")

    df["_time"] = pd.to_numeric(df[columns.time_minutes], errors="coerce")
    df["_weight"] = pd.to_numeric(df[columns.person_weight], errors="coerce")
    if df["_time"].isna().any():
        raise ValueError("trip duration contains missing or non-numeric values")
    if (~np.isfinite(df["_time"])).any() or (df["_time"] < 0).any():
        raise ValueError("trip duration must be finite and non-negative")
    if df["_weight"].isna().any():
        raise ValueError("person weight contains missing or non-numeric values")
    if (~np.isfinite(df["_weight"])).any() or (df["_weight"] < 0).any():
        raise ValueError("person weight must be finite and non-negative")
    if df[columns.purpose].isna().any():
        raise ValueError("purpose contains missing values; map them before aggregation")

    weight_nunique = df.groupby(columns.person, observed=True)["_weight"].nunique(dropna=False)
    bad_weight = weight_nunique[weight_nunique > 1]
    if not bad_weight.empty:
        raise ValueError(
            "person weight varies across trips for the same person; "
            f"examples: {bad_weight.index[:10].tolist()}"
        )

    if max_trip_minutes is not None:
        df = df.loc[df["_time"] <= float(max_trip_minutes)].copy()
        if df.empty:
            raise ValueError("no trips remain after max_trip_minutes filtering")

    home_set = {_normalize_text(v) for v in home_return_values}
    df["_purpose_norm"] = df[columns.purpose].map(_normalize_text)
    bad_purpose = df["_purpose_norm"].isin(EXPLICIT_MISSING_PURPOSE_LABELS)
    if bad_purpose.any():
        values = sorted(df.loc[bad_purpose, columns.purpose].astype(str).unique())[:10]
        raise ValueError(f"purpose contains explicit missing/unmapped labels: {values}")

    df["_home_return"] = df["_purpose_norm"].isin(home_set)
    if require_home_return_observed and not bool(df["_home_return"].any()):
        observed = sorted(df[columns.purpose].astype(str).unique())[:20]
        raise ValueError(
            "none of the declared home-return labels was observed; purpose may be "
            f"undecoded or mis-mapped. observed examples: {observed}"
        )
    df["_activity_episode"] = (~df["_home_return"]).astype(int)

    grouped = (
        df.groupby(columns.person, observed=True, sort=False)
        .agg(
            t_minutes=("_time", "sum"),
            r=("_activity_episode", "sum"),
            weight=("_weight", "first"),
            n_trips=(columns.trip, "size"),
            n_home_returns=("_home_return", "sum"),
            max_trip_minutes=("_time", "max"),
        )
        .reset_index()
        .rename(columns={columns.person: "person_id"})
    )
    grouped.insert(0, "city", str(city))
    grouped["r"] = grouped["r"].astype(int)
    grouped["n_trips"] = grouped["n_trips"].astype(int)
    grouped["n_home_returns"] = grouped["n_home_returns"].astype(int)
    grouped["p1_zero_with_travel"] = (grouped["t_minutes"] > 0) & (grouped["r"] == 0)

    return grouped[
        [
            "city",
            "person_id",
            "t_minutes",
            "r",
            "weight",
            "n_trips",
            "n_home_returns",
            "max_trip_minutes",
            "p1_zero_with_travel",
        ]
    ]


def person_day_qa(person_days: pd.DataFrame) -> pd.DataFrame:
    """Compact QA summary for a reconstructed travelling-person sample."""
    required = {
        "city",
        "person_id",
        "t_minutes",
        "r",
        "weight",
        "n_trips",
        "n_home_returns",
        "p1_zero_with_travel",
    }
    missing = sorted(required.difference(person_days.columns))
    if missing:
        raise ValueError(f"person_days is missing required columns: {missing}")

    out = []
    for city, grp in person_days.groupby("city", observed=True, sort=True):
        w = grp["weight"].astype(float)
        wsum = float(w.sum())
        w2 = float((w ** 2).sum())
        out.append(
            {
                "city": city,
                "n_person_days": int(len(grp)),
                "expanded_weight": wsum,
                "n_eff_kish": (wsum ** 2 / w2) if w2 > 0 else 0.0,
                "t_mean_unweighted": float(grp["t_minutes"].mean()),
                "t_median_unweighted": float(grp["t_minutes"].median()),
                "p1_mean_unweighted": float(grp["r"].mean()),
                "p1_zero_with_travel_n": int(grp["p1_zero_with_travel"].sum()),
                "max_trip_count": int(grp["n_trips"].max()),
            }
        )
    return pd.DataFrame(out)
