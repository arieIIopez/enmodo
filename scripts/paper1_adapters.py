"""City-specific adapters for the confirmatory Paper I pilot.

The adapters encode only transformations that can be traced to the historical
ENMODO notebooks or official survey metadata. They deliberately avoid fuzzy
column-name inference. Each adapter first selects the primary comparable day
universe, then maps the source trip table to `person_day.build_person_days...`.

Primary pilot universe
----------------------
- Santiago 2012: normal working day (`FactorLaboralNormal` observed), excluding
  the separate summer-working-day factor.
- Mexico City 2017: weekday travel (`p5_3 == 1` in the ENMODO notebook; the
  official EOD metadata distinguishes Tue/Wed/Thu from Saturday).
- Bogota 2015: records explicitly marked `DIA_HABIL == 'Si'`.

This is a type-of-day harmonisation, not a claim of identical survey seasons.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from scripts.person_day import PersonDayColumns, build_person_days_from_trips


@dataclass(frozen=True)
class AdapterAudit:
    city: str
    input_rows: int
    selected_rows: int
    selected_persons: int
    notes: str = ""


def _require(df: pd.DataFrame, columns: list[str], city: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"{city}: missing required columns {missing}")


def _audit(city: str, before: pd.DataFrame, after: pd.DataFrame, person_col: str, notes: str = "") -> AdapterAudit:
    return AdapterAudit(
        city=city,
        input_rows=int(len(before)),
        selected_rows=int(len(after)),
        selected_persons=int(after[person_col].nunique()),
        notes=notes,
    )


def prepare_santiago_2012(trips: pd.DataFrame) -> tuple[pd.DataFrame, AdapterAudit]:
    """Select Santiago normal working-day trips and map source semantics.

    Traceability from the historical notebook:
    - person: `Persona`
    - trip: `Viaje`
    - duration: `TiempoViaje` (already minutes in source workflow)
    - purpose: transformed `proposito`
    - normal working-day trip factor: `FactorLaboralNormal`
    - normal working-day person factor: `Factor_LaboralNormal`

    `DIA_HABIL` combines normal and summer working-day records in the old
    notebook, so it is not sufficient for the confirmatory primary universe.
    """
    city = "Santiago 2012"
    required = [
        "Persona",
        "Viaje",
        "TiempoViaje",
        "proposito",
        "FactorLaboralNormal",
        "Factor_LaboralNormal",
    ]
    _require(trips, required, city)
    selected = trips.loc[trips["FactorLaboralNormal"].notna()].copy()
    if selected.empty:
        raise ValueError(f"{city}: no normal working-day trips selected")
    if selected["Factor_LaboralNormal"].isna().any():
        raise ValueError(f"{city}: selected trips contain missing person working-day weights")

    # If the legacy day label is present, use it only as a consistency check.
    if "DIA_HABIL" in selected.columns:
        inconsistent = ~selected["DIA_HABIL"].astype(str).str.casefold().isin(["si", "sí"])
        if inconsistent.any():
            raise ValueError(f"{city}: FactorLaboralNormal conflicts with DIA_HABIL")

    audit = _audit(
        city,
        trips,
        selected,
        "Persona",
        notes="Primary universe: normal working day; summer-working-day records excluded.",
    )
    return selected, audit


def build_santiago_2012_person_days(trips: pd.DataFrame) -> tuple[pd.DataFrame, AdapterAudit]:
    selected, audit = prepare_santiago_2012(trips)
    person_days = build_person_days_from_trips(
        selected,
        city=audit.city,
        columns=PersonDayColumns(
            person="Persona",
            trip="Viaje",
            time_minutes="TiempoViaje",
            purpose="proposito",
            person_weight="Factor_LaboralNormal",
        ),
        home_return_values=["volver a casa"],
    )
    return person_days, audit


def prepare_mexico_2017(trips: pd.DataFrame) -> tuple[pd.DataFrame, AdapterAudit]:
    """Select Mexico City weekday trips (`p5_3 == 1`).

    The ENMODO notebook merges TVIAJE and TSDEM on `id_soc`; because both
    contain `factor`, pandas creates `factor_x` (trip side) and `factor_y`
    (person side). The historical person-level G6 query itself used `factor_y`.
    The confirmatory adapter therefore uses `factor_y` as person weight and
    reports disagreement with `factor_x` as QA rather than substituting it.
    """
    city = "Ciudad de México 2017"
    required = [
        "id_soc",
        "id_via",
        "p5_3",
        "duracion_minutos",
        "p5_13",
        "factor_y",
    ]
    _require(trips, required, city)
    selected = trips.loc[pd.to_numeric(trips["p5_3"], errors="coerce") == 1].copy()
    if selected.empty:
        raise ValueError(f"{city}: no weekday trips selected with p5_3 == 1")
    if selected["factor_y"].isna().any():
        raise ValueError(f"{city}: weekday trips contain missing person weights")

    notes = "Primary universe: weekday (Tue/Wed/Thu), excluding Saturday."
    if "DIA_HABIL" in selected.columns:
        inconsistent = ~selected["DIA_HABIL"].astype(str).str.casefold().isin(["si", "sí"])
        if inconsistent.any():
            raise ValueError(f"{city}: p5_3 == 1 conflicts with DIA_HABIL")

    if "factor_x" in selected.columns:
        a = pd.to_numeric(selected["factor_x"], errors="coerce")
        b = pd.to_numeric(selected["factor_y"], errors="coerce")
        comparable = a.notna() & b.notna()
        if comparable.any():
            mismatch = ~np.isclose(a[comparable], b[comparable], rtol=1e-9, atol=1e-12)
            mismatch_rate = float(mismatch.mean())
            notes += f" trip/person factor mismatch rate={mismatch_rate:.6f}; factor_y retained."

    audit = _audit(city, trips, selected, "id_soc", notes=notes)
    return selected, audit


def build_mexico_2017_person_days(trips: pd.DataFrame) -> tuple[pd.DataFrame, AdapterAudit]:
    selected, audit = prepare_mexico_2017(trips)
    person_days = build_person_days_from_trips(
        selected,
        city=audit.city,
        columns=PersonDayColumns(
            person="id_soc",
            trip="id_via",
            time_minutes="duracion_minutos",
            purpose="p5_13",
            person_weight="factor_y",
        ),
        # Official INEGI EOD 2017 terminology.
        home_return_values=["Regresar al hogar"],
    )
    return person_days, audit


def prepare_bogota_2015(trips: pd.DataFrame) -> tuple[pd.DataFrame, AdapterAudit]:
    """Select Bogota 2015 working-day trips from the historical ENMODO output."""
    city = "Bogotá 2015"
    required = [
        "ID_PERSONA",
        "NUMERO_VIAJE",
        "duracion_minutos",
        "MOTIVOVIAJE",
        "PONDERADOR_CALIBRADO",
        "DIA_HABIL",
    ]
    _require(trips, required, city)
    day = trips["DIA_HABIL"].astype(str).str.casefold()
    selected = trips.loc[day.isin(["si", "sí"])].copy()
    if selected.empty:
        raise ValueError(f"{city}: no working-day trips selected")
    if selected["PONDERADOR_CALIBRADO"].isna().any():
        raise ValueError(f"{city}: working-day trips contain missing person weights")

    audit = _audit(
        city,
        trips,
        selected,
        "ID_PERSONA",
        notes="Primary universe: source records explicitly labelled DIA_HABIL=Si.",
    )
    return selected, audit


def build_bogota_2015_person_days(trips: pd.DataFrame) -> tuple[pd.DataFrame, AdapterAudit]:
    selected, audit = prepare_bogota_2015(trips)
    person_days = build_person_days_from_trips(
        selected,
        city=audit.city,
        columns=PersonDayColumns(
            person="ID_PERSONA",
            trip="NUMERO_VIAJE",
            time_minutes="duracion_minutos",
            purpose="MOTIVOVIAJE",
            person_weight="PONDERADOR_CALIBRADO",
        ),
        home_return_values=["Volver a casa"],
    )
    return person_days, audit


PILOT_BUILDERS: dict[str, Callable[[pd.DataFrame], tuple[pd.DataFrame, AdapterAudit]]] = {
    "santiago_2012": build_santiago_2012_person_days,
    "mexico_2017": build_mexico_2017_person_days,
    "bogota_2015": build_bogota_2015_person_days,
}
