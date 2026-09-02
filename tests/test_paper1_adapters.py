import pandas as pd
import pytest

from scripts.paper1_adapters import (
    build_bogota_2015_person_days,
    build_mexico_2017_person_days,
    build_santiago_2012_person_days,
)


def test_santiago_selects_normal_workday_and_uses_person_weight():
    trips = pd.DataFrame(
        {
            "Persona": [1, 1, 1, 2],
            "Viaje": [1, 2, 3, 1],
            "TiempoViaje": [20, 30, 10, 99],
            "proposito": ["Trabajo", "volver a casa", "Compras", "Trabajo"],
            "FactorLaboralNormal": [1.0, 1.0, 1.0, None],
            "Factor_LaboralNormal": [2.5, 2.5, 2.5, 4.0],
            "DIA_HABIL": ["Si", "Si", "Si", "Si"],
        }
    )
    out, audit = build_santiago_2012_person_days(trips)
    assert audit.selected_persons == 1
    row = out.iloc[0]
    assert row.t_minutes == 60
    assert row.r == 2
    assert row.weight == 2.5


def test_mexico_excludes_saturday_and_counts_regresar_al_hogar_as_return():
    trips = pd.DataFrame(
        {
            "id_soc": [1, 1, 1, 2],
            "id_via": [10, 11, 12, 20],
            "p5_3": [1, 1, 1, 2],
            "duracion_minutos": [15, 25, 20, 90],
            "p5_13": ["Ir al trabajo", "Ir de compras", "Regresar al hogar", "Ir al trabajo"],
            "factor_x": [3.0, 3.0, 3.0, 4.0],
            "factor_y": [3.0, 3.0, 3.0, 4.0],
            "DIA_HABIL": ["Si", "Si", "Si", "No"],
        }
    )
    out, audit = build_mexico_2017_person_days(trips)
    assert audit.selected_persons == 1
    row = out.iloc[0]
    assert row.t_minutes == 60
    assert row.r == 2
    assert row.n_home_returns == 1


def test_bogota_uses_workday_and_home_return_semantics():
    trips = pd.DataFrame(
        {
            "ID_PERSONA": [100, 100, 100, 200],
            "NUMERO_VIAJE": [1, 2, 3, 1],
            "duracion_minutos": [30, 15, 25, 100],
            "MOTIVOVIAJE": ["Trabajar", "Compras", "Volver a casa", "Trabajar"],
            "PONDERADOR_CALIBRADO": [5.0, 5.0, 5.0, 6.0],
            "DIA_HABIL": ["Si", "Si", "Si", "No"],
        }
    )
    out, audit = build_bogota_2015_person_days(trips)
    assert audit.selected_persons == 1
    row = out.iloc[0]
    assert row.t_minutes == 70
    assert row.r == 2


def test_bogota_duplicate_trip_within_person_raises():
    trips = pd.DataFrame(
        {
            "ID_PERSONA": [100, 100],
            "NUMERO_VIAJE": [1, 1],
            "duracion_minutos": [30, 40],
            "MOTIVOVIAJE": ["Trabajar", "Volver a casa"],
            "PONDERADOR_CALIBRADO": [5.0, 5.0],
            "DIA_HABIL": ["Si", "Si"],
        }
    )
    with pytest.raises(ValueError, match="duplicate person-trip"):
        build_bogota_2015_person_days(trips)
