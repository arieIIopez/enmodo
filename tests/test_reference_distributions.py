import pandas as pd

from scripts.reference_distributions import (
    equal_city_mixture,
    observed_city_references,
    support_coverage,
    uniform_discrete_reference,
)


def _person_days():
    return pd.DataFrame(
        {
            "city": ["A", "A", "A", "B", "B", "B"],
            "r": [1, 2, 4, 1, 2, 3],
            "weight": [1.0, 3.0, 2.0, 2.0, 2.0, 4.0],
        }
    )


def test_support_coverage_reports_excluded_weight():
    out = support_coverage(_person_days(), support=[1, 2])
    a = out[out.city == "A"].iloc[0]
    b = out[out.city == "B"].iloc[0]

    assert a.coverage == 4.0 / 6.0
    assert b.coverage == 4.0 / 8.0
    assert a.excluded_weight == 2.0
    assert b.excluded_weight == 4.0


def test_observed_city_references_are_normalized_on_global_support():
    refs = observed_city_references(_person_days(), support=[1, 2])
    sums = refs.groupby("reference").weight.sum()
    assert all(abs(value - 1.0) < 1e-12 for value in sums)

    a = refs[refs.reference == "observed:A"].set_index("r").weight
    b = refs[refs.reference == "observed:B"].set_index("r").weight
    assert a.loc[1.0] == 0.25
    assert a.loc[2.0] == 0.75
    assert b.loc[1.0] == 0.50
    assert b.loc[2.0] == 0.50


def test_uniform_reference_is_stress_test_and_normalized():
    ref = uniform_discrete_reference([1, 2, 3])
    assert abs(ref.weight.sum() - 1.0) < 1e-12
    assert set(ref.reference_type) == {"uniform_discrete_stress"}
    assert set(ref.weight) == {1.0 / 3.0}


def test_equal_city_mixture_is_average_of_observed_extremes():
    refs = observed_city_references(_person_days(), support=[1, 2])
    mix = equal_city_mixture(refs).set_index("r").weight
    assert mix.loc[1.0] == (0.25 + 0.50) / 2
    assert mix.loc[2.0] == (0.75 + 0.50) / 2
