import pandas as pd

from scripts.mexico2017_official_adapter import build_mexico_2017_from_official


def _persons():
    return pd.DataFrame(
        {
            "id_soc": ["1", "2", "3"],
            "p5_4": ["02", "", "01"],
            "factor": ["10", "20", "30"],
            "upm_dis": ["001", "001", "002"],
            "est_dis": ["A", "A", "B"],
        }
    )


def test_mexico_adapter_excludes_bad_diary_but_keeps_person_in_universe():
    trips = pd.DataFrame(
        {
            "id_via": ["1", "2", "3"],
            "id_soc": ["1", "1", "3"],
            "p5_3": ["1", "1", "1"],
            "p5_9_1": ["08", "17", "99"],
            "p5_9_2": ["00", "00", "00"],
            "p5_10_1": ["08", "17", "10"],
            "p5_10_2": ["30", "30", "00"],
            "p5_11a": ["03", "01", "03"],
            "p5_13": ["02", "01", "02"],
            "factor": ["10", "10", "30"],
            "upm_dis": ["001", "001", "002"],
            "est_dis": ["A", "A", "B"],
        }
    )

    person_days, universe, exclusion, audit, universe_audit = build_mexico_2017_from_official(
        trips, _persons()
    )

    assert audit.weekday_travelling_persons == 2
    assert audit.analysis_persons == 1
    assert audit.excluded_invalid_time_persons == 1
    assert set(person_days.person_id) == {"1"}
    row = person_days.iloc[0]
    assert row.t_minutes == 60
    assert row.r == 1
    assert row.n_home_returns == 1

    # Person 3 remains a traveller in the population universe even though the
    # diary is excluded from T|P1 quality analysis.
    assert universe_audit.n_travellers == 2
    assert universe_audit.n_nontravellers == 1
    assert set(universe.loc[universe.travelled, "person_id"]) == {"1", "3"}
    assert int(exclusion.loc[exclusion.reason == "invalid_time", "n_persons"].iloc[0]) == 1


def test_mexico_adapter_handles_trip_crossing_midnight():
    trips = pd.DataFrame(
        {
            "id_via": ["1", "2"],
            "id_soc": ["1", "1"],
            "p5_3": ["1", "1"],
            "p5_9_1": ["23", "00"],
            "p5_9_2": ["50", "20"],
            "p5_10_1": ["00", "00"],
            "p5_10_2": ["10", "40"],
            "p5_11a": ["03", "01"],
            "p5_13": ["02", "01"],
            "factor": ["10", "10"],
            "upm_dis": ["001", "001"],
            "est_dis": ["A", "A"],
        }
    )
    persons = _persons().loc[_persons().id_soc == "1"].copy()
    person_days, *_ = build_mexico_2017_from_official(trips, persons)
    assert person_days.iloc[0].t_minutes == 40
