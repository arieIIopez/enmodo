import numpy as np
import pandas as pd
import pytest

from scripts.paper1_official_adapters import build_bogota_2015_from_official


def _persons():
    return pd.DataFrame(
        {
            "ID_ENCUESTA": [10, 10, 20],
            "NUMERO_PERSONA": [1, 2, 1],
            "PONDERADOR_CALIBRADO": ["2,5", "3.0", "4,0"],
        }
    )


def test_bogota_official_reconstructs_daily_time_and_workday_household_universe():
    trips = pd.DataFrame(
        {
            "ID_ENCUESTA": [10, 10, 10, 20],
            "NUMERO_PERSONA": [1, 1, 1, 1],
            "NUMERO_VIAJE": [1, 2, 3, 1],
            "MOTIVOVIAJE": ["Trabajar", "Compras", "Volver a casa", "Trabajar"],
            "HORA_INICIO": ["08:00", "12:00", "18:00", "09:00"],
            "HORA_FIN": ["08:30", "12:15", "18:25", "10:00"],
            "DIA_HABIL": ["S", "S", "S", "N"],
        }
    )
    person_days, universe, audit, universe_audit = build_bogota_2015_from_official(
        trips, _persons()
    )

    assert audit.selected_trip_rows == 3
    assert audit.travelling_persons == 1
    assert audit.missing_day_flag_rows == 0
    assert audit.workday_households == 1
    assert audit.nonworkday_households == 1
    assert audit.workday_universe_persons == 2
    assert len(person_days) == 1
    row = person_days.iloc[0]
    assert row.person_id == "10::1"
    assert row.t_minutes == 70
    assert row.r == 2
    assert row.n_home_returns == 1
    assert row.weight == 2.5

    # Household 20 belongs to the separately calibrated non-workday sample and
    # must not be counted as a weekday non-traveller.
    assert set(universe.person_id) == {"10::1", "10::2"}
    assert universe.travelled.sum() == 1
    assert universe_audit.n_nontravellers == 1
    assert universe_audit.weighted_traveller_share == 2.5 / 5.5


def test_bogota_official_excludes_missing_workday_flags_as_historical_sin_dato():
    trips = pd.DataFrame(
        {
            "ID_ENCUESTA": [10, 10, 10],
            "NUMERO_PERSONA": [1, 1, 2],
            "NUMERO_VIAJE": [1, 2, 1],
            "MOTIVOVIAJE": ["Trabajar", "Volver a casa", "Trabajar"],
            "HORA_INICIO": ["08:00", "18:00", "09:00"],
            "HORA_FIN": ["08:30", "18:30", "10:00"],
            "DIA_HABIL": ["S", "S", np.nan],
        }
    )
    person_days, universe, audit, _ = build_bogota_2015_from_official(trips, _persons())
    assert audit.missing_day_flag_rows == 1
    assert audit.selected_trip_rows == 2
    assert set(person_days.person_id) == {"10::1"}
    assert set(universe.person_id) == {"10::1", "10::2"}
    assert bool(universe.loc[universe.person_id == "10::2", "travelled"].iloc[0]) is False


def test_bogota_official_rejects_household_mixing_day_types():
    trips = pd.DataFrame(
        {
            "ID_ENCUESTA": [10, 10],
            "NUMERO_PERSONA": [1, 2],
            "NUMERO_VIAJE": [1, 1],
            "MOTIVOVIAJE": ["Volver a casa", "Trabajar"],
            "HORA_INICIO": ["18:00", "09:00"],
            "HORA_FIN": ["18:30", "10:00"],
            "DIA_HABIL": ["S", "N"],
        }
    )
    with pytest.raises(ValueError, match="households mix weekday and non-weekday"):
        build_bogota_2015_from_official(trips, _persons())


def test_bogota_official_handles_overnight_trip():
    trips = pd.DataFrame(
        {
            "ID_ENCUESTA": [10, 10],
            "NUMERO_PERSONA": [1, 1],
            "NUMERO_VIAJE": [1, 2],
            "MOTIVOVIAJE": ["Trabajar", "Volver a casa"],
            "HORA_INICIO": ["23:50", "00:20"],
            "HORA_FIN": ["00:10", "00:40"],
            "DIA_HABIL": ["Si", "Si"],
        }
    )
    person_days, *_ = build_bogota_2015_from_official(trips, _persons())
    assert person_days.iloc[0].t_minutes == 40
    assert person_days.iloc[0].r == 1


def test_bogota_official_accepts_24h_exact_midnight():
    trips = pd.DataFrame(
        {
            "ID_ENCUESTA": [10, 10],
            "NUMERO_PERSONA": [1, 1],
            "NUMERO_VIAJE": [1, 2],
            "MOTIVOVIAJE": ["Trabajar", "Volver a casa"],
            "HORA_INICIO": ["22:30", "23:30"],
            "HORA_FIN": ["23:00", "24:00:00"],
            "DIA_HABIL": ["S", "S"],
        }
    )
    person_days, *_ = build_bogota_2015_from_official(trips, _persons())
    assert person_days.iloc[0].t_minutes == 60
    assert person_days.iloc[0].r == 1


def test_bogota_official_fails_when_home_semantics_absent():
    trips = pd.DataFrame(
        {
            "ID_ENCUESTA": [10],
            "NUMERO_PERSONA": [1],
            "NUMERO_VIAJE": [1],
            "MOTIVOVIAJE": ["Trabajar"],
            "HORA_INICIO": ["08:00"],
            "HORA_FIN": ["08:30"],
            "DIA_HABIL": ["S"],
        }
    )
    with pytest.raises(ValueError, match="Volver a casa"):
        build_bogota_2015_from_official(trips, _persons())
