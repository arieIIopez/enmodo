import pandas as pd

from scripts.person_universe import (
    bogota_2015_person_universe,
    mexico_2017_person_universe,
    santiago_2012_person_universe,
)


def test_santiago_nontravellers_are_people_without_selected_workday_trip():
    persons = pd.DataFrame(
        {
            "Persona": [1, 2, 3],
            "Hogar": [10, 10, 20],
            "Factor_LaboralNormal": [2.0, 3.0, 5.0],
        }
    )
    trips = pd.DataFrame({"Persona": [1, 3]})
    out, audit = santiago_2012_person_universe(persons, trips)
    assert audit.n_travellers == 2
    assert audit.n_nontravellers == 1
    # Traveller weighted mass = 2 + 5 out of 10.
    assert audit.weighted_traveller_share == 0.7
    assert set(out.loc[~out.travelled, "person_id"]) == {"2"}


def test_mexico_retains_official_design_columns():
    persons = pd.DataFrame(
        {
            "id_soc": [1, 2, 3],
            "factor": [1.0, 2.0, 3.0],
            "UPM_DIS": [100, 100, 200],
            "EST_DIS": ["A", "A", "B"],
        }
    )
    trips = pd.DataFrame({"id_soc": [1, 2]})
    out, audit = mexico_2017_person_universe(persons, trips)
    assert audit.cluster_variable == "UPM_DIS"
    assert audit.stratum_variable == "EST_DIS"
    assert {"cluster", "stratum"}.issubset(out.columns)
    assert audit.weighted_nontraveller_share == 0.5


def test_bogota_uses_explicit_composite_key_and_household_cluster():
    persons = pd.DataFrame(
        {
            "ID_ENCUESTA": [10, 10, 20],
            "NUMERO_PERSONA": [1, 2, 1],
            "PONDERADOR_CALIBRADO": [2.0, 2.0, 6.0],
        }
    )
    trips = pd.DataFrame(
        {
            "ID_ENCUESTA": [10, 20],
            "NUMERO_PERSONA": [1, 1],
        }
    )
    out, audit = bogota_2015_person_universe(persons, trips)
    assert set(out.person_id) == {"10::1", "10::2", "20::1"}
    assert audit.cluster_variable == "ID_ENCUESTA"
    assert set(out.loc[~out.travelled, "person_id"]) == {"10::2"}
