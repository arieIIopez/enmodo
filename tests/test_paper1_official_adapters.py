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


def test_bogota_official_reconstructs_daily_time_and_p1():
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
    assert len(person_days) == 1
    row = person_days.iloc[0]
    assert row.person_id == "10::1"
    assert row.t_minutes == 70
    assert row.r == 2
    assert row.n_home_returns == 1
    assert row.weight == 2.5

    assert len(universe) == 3
    assert universe.travelled.sum() == 1
    assert universe_audit.n_nontravellers == 2


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
