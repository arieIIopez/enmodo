import pandas as pd
import pytest

from scripts.person_day import PersonDayColumns, build_person_days_from_trips


COLUMNS = PersonDayColumns(
    person="Persona",
    trip="Viaje",
    time_minutes="duracion_minutos",
    purpose="proposito",
    person_weight="PONDERADOR_CALIBRADO",
)


def _trips():
    return pd.DataFrame(
        {
            "Persona": [1, 1, 1, 2, 2],
            "Viaje": [11, 12, 13, 21, 22],
            "duracion_minutos": [30, 10, 20, 40, 30],
            "proposito": ["Trabajo", "Compras", "Volver a casa", "Estudio", "volver a casa"],
            "PONDERADOR_CALIBRADO": [2.0, 2.0, 2.0, 3.0, 3.0],
        }
    )


def test_daily_time_is_sum_and_home_return_does_not_increment_p1():
    out = build_person_days_from_trips(
        _trips(),
        city="Santiago 2012",
        columns=COLUMNS,
        home_return_values=["volver a casa"],
    ).set_index("person_id")

    assert out.loc[1, "t_minutes"] == 60
    assert out.loc[1, "r"] == 2
    assert out.loc[1, "n_home_returns"] == 1
    assert out.loc[2, "t_minutes"] == 70
    assert out.loc[2, "r"] == 1


def test_home_return_matching_is_case_and_accent_insensitive():
    trips = _trips().copy()
    trips.loc[2, "proposito"] = "VOLVER A CÁSA"
    out = build_person_days_from_trips(
        trips,
        city="X",
        columns=COLUMNS,
        home_return_values=["volver a casa"],
    ).set_index("person_id")
    assert out.loc[1, "r"] == 2


def test_duplicate_person_trip_raises():
    trips = pd.concat([_trips(), _trips().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="duplicate person-trip"):
        build_person_days_from_trips(
            trips,
            city="X",
            columns=COLUMNS,
            home_return_values=["volver a casa"],
        )


def test_person_weight_must_be_constant_within_person():
    trips = _trips().copy()
    trips.loc[1, "PONDERADOR_CALIBRADO"] = 99
    with pytest.raises(ValueError, match="weight varies"):
        build_person_days_from_trips(
            trips,
            city="X",
            columns=COLUMNS,
            home_return_values=["volver a casa"],
        )


def test_legacy_150_minute_filter_is_not_implicit():
    trips = _trips().copy()
    trips.loc[0, "duracion_minutos"] = 180
    untrimmed = build_person_days_from_trips(
        trips,
        city="X",
        columns=COLUMNS,
        home_return_values=["volver a casa"],
    ).set_index("person_id")
    assert untrimmed.loc[1, "t_minutes"] == 210

    trimmed = build_person_days_from_trips(
        trips,
        city="X",
        columns=COLUMNS,
        home_return_values=["volver a casa"],
        max_trip_minutes=150,
    ).set_index("person_id")
    assert trimmed.loc[1, "t_minutes"] == 30
