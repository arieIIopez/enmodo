"""Person-universe reconstruction and non-traveller diagnostics for Paper I.

Trip tables cannot identify people with zero trips. This module reconstructs a
person universe from each survey's person file and marks whether each person has
at least one trip in the SAME primary day universe used by the city adapter.

The output deliberately remains separate from the travelling person-day table.
No population-level Mobility Coefficient is constructed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class UniverseAudit:
    city: str
    n_persons: int
    n_travellers: int
    n_nontravellers: int
    weighted_traveller_share: float
    weighted_nontraveller_share: float
    cluster_variable: str | None
    stratum_variable: str | None
    notes: str = ""


def _require(df: pd.DataFrame, cols: Iterable[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: missing required columns {missing}")


def _composite_key(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    parts = []
    for col in columns:
        if df[col].isna().any():
            raise ValueError(f"composite key column {col!r} contains missing values")
        parts.append(df[col].astype(str).str.strip())
    key = parts[0]
    for part in parts[1:]:
        key = key + "::" + part
    return key


def _resolve_explicit_variant(df: pd.DataFrame, variants: list[str]) -> str | None:
    present = [c for c in variants if c in df.columns]
    if len(present) > 1:
        # Permit case-only duplicates only if identical; otherwise ambiguous.
        first = df[present[0]]
        if not all(first.equals(df[c]) for c in present[1:]):
            raise ValueError(f"ambiguous design-variable variants present: {present}")
    return present[0] if present else None


def _finalize(
    frame: pd.DataFrame,
    *,
    city: str,
    person_col: str,
    weight_col: str,
    traveller_ids: set[str],
    cluster_col: str | None = None,
    stratum_col: str | None = None,
    notes: str = "",
) -> tuple[pd.DataFrame, UniverseAudit]:
    _require(frame, [person_col, weight_col], city)
    df = frame.copy()
    if df[person_col].isna().any():
        raise ValueError(f"{city}: person identifiers contain missing values")
    if df.duplicated(person_col).any():
        raise ValueError(f"{city}: person universe must contain one row per person")

    weight = pd.to_numeric(df[weight_col], errors="coerce")
    if weight.isna().any() or (~np.isfinite(weight)).any() or (weight < 0).any():
        raise ValueError(f"{city}: invalid person weights")
    df["weight"] = weight.astype(float)
    df["person_id"] = df[person_col].astype(str)
    df["travelled"] = df["person_id"].isin(traveller_ids)

    keep = ["person_id", "weight", "travelled"]
    if cluster_col:
        if df[cluster_col].isna().any():
            raise ValueError(f"{city}: cluster variable {cluster_col} contains missing values")
        df["cluster"] = df[cluster_col].astype(str)
        keep.append("cluster")
    if stratum_col:
        if df[stratum_col].isna().any():
            raise ValueError(f"{city}: stratum variable {stratum_col} contains missing values")
        df["stratum"] = df[stratum_col].astype(str)
        keep.append("stratum")

    out = df[keep].copy()
    out.insert(0, "city", city)
    total_w = float(out["weight"].sum())
    travel_w = float(out.loc[out["travelled"], "weight"].sum())
    share = travel_w / total_w if total_w > 0 else np.nan
    audit = UniverseAudit(
        city=city,
        n_persons=int(len(out)),
        n_travellers=int(out["travelled"].sum()),
        n_nontravellers=int((~out["travelled"]).sum()),
        weighted_traveller_share=float(share),
        weighted_nontraveller_share=float(1 - share),
        cluster_variable=cluster_col,
        stratum_variable=stratum_col,
        notes=notes,
    )
    return out, audit


def santiago_2012_person_universe(
    persons: pd.DataFrame,
    selected_workday_trips: pd.DataFrame,
) -> tuple[pd.DataFrame, UniverseAudit]:
    """Normal-working-day universe for Santiago 2012.

    `Factor_LaboralNormal` is the person weight for the primary universe.
    Household is retained as the minimum defensible resampling cluster when a
    higher official PSU is not present in the processed inputs.
    """
    city = "Santiago 2012"
    _require(persons, ["Persona", "Hogar", "Factor_LaboralNormal"], city)
    _require(selected_workday_trips, ["Persona"], f"{city} trips")
    universe = persons.loc[persons["Factor_LaboralNormal"].notna()].copy()
    traveller_ids = set(selected_workday_trips["Persona"].astype(str).unique())
    return _finalize(
        universe,
        city=city,
        person_col="Persona",
        weight_col="Factor_LaboralNormal",
        traveller_ids=traveller_ids,
        cluster_col="Hogar",
        notes="Household retained as minimum cluster; higher design PSU still to be audited.",
    )


def mexico_2017_person_universe(
    persons: pd.DataFrame,
    selected_weekday_trips: pd.DataFrame,
) -> tuple[pd.DataFrame, UniverseAudit]:
    """Weekday person universe for Mexico City 2017 from TSDEM.

    Official INEGI metadata documents `UPM_DIS` and `EST_DIS`. The repository
    has historically used lowercase names for several TSDEM variables, so only
    the two explicit case variants are accepted here; no fuzzy matching occurs.
    """
    city = "Ciudad de México 2017"
    _require(persons, ["id_soc", "factor"], city)
    _require(selected_weekday_trips, ["id_soc"], f"{city} trips")
    cluster = _resolve_explicit_variant(persons, ["UPM_DIS", "upm_dis"])
    stratum = _resolve_explicit_variant(persons, ["EST_DIS", "est_dis"])
    if cluster is None or stratum is None:
        raise ValueError(f"{city}: official UPM_DIS/EST_DIS design variables are required")
    traveller_ids = set(selected_weekday_trips["id_soc"].astype(str).unique())
    return _finalize(
        persons,
        city=city,
        person_col="id_soc",
        weight_col="factor",
        traveller_ids=traveller_ids,
        cluster_col=cluster,
        stratum_col=stratum,
        notes="Official INEGI UPM and design stratum retained for survey-design bootstrap.",
    )


def bogota_2015_person_universe(
    persons: pd.DataFrame,
    selected_workday_trips: pd.DataFrame,
) -> tuple[pd.DataFrame, UniverseAudit]:
    """Bogota 2015 person universe with explicit survey-person composite key."""
    city = "Bogotá 2015"
    _require(persons, ["ID_ENCUESTA", "NUMERO_PERSONA", "PONDERADOR_CALIBRADO"], city)
    _require(selected_workday_trips, ["ID_ENCUESTA", "NUMERO_PERSONA"], f"{city} trips")
    universe = persons.copy()
    universe["_person_key"] = _composite_key(universe, ["ID_ENCUESTA", "NUMERO_PERSONA"])
    trips = selected_workday_trips.copy()
    trips["_person_key"] = _composite_key(trips, ["ID_ENCUESTA", "NUMERO_PERSONA"])
    traveller_ids = set(trips["_person_key"].astype(str).unique())
    return _finalize(
        universe,
        city=city,
        person_col="_person_key",
        weight_col="PONDERADOR_CALIBRADO",
        traveller_ids=traveller_ids,
        cluster_col="ID_ENCUESTA",
        notes="ID_ENCUESTA retained as household/survey cluster; no unsupported design stratum imposed.",
    )
