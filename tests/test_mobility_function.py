import pandas as pd

from scripts.mobility_function import (
    estimate_time_participation_curve,
    nontraveller_rate,
)
from scripts.support_diagnostics import estimable_global_support, support_diagnostics


def _person_days():
    return pd.DataFrame(
        {
            "city": ["A", "A", "A", "A", "B", "B", "B", "B"],
            "r": [0, 1, 1, 2, 0, 1, 1, 2],
            "t_minutes": [0, 30, 60, 90, 0, 45, 75, 120],
            "weight": [2.0, 1.0, 3.0, 2.0, 1.0, 2.0, 2.0, 4.0],
        }
    )


def test_primary_curve_is_weighted_cell_mean_and_excludes_t0_by_default():
    curve = estimate_time_participation_curve(_person_days())
    assert set(curve.r) == {1, 2}

    a1 = curve[(curve.city == "A") & (curve.r == 1)].iloc[0]
    b1 = curve[(curve.city == "B") & (curve.r == 1)].iloc[0]
    assert a1.m == (30 * 1 + 60 * 3) / 4
    assert b1.m == (45 * 2 + 75 * 2) / 4


def test_nontravellers_are_reported_separately():
    rates = nontraveller_rate(_person_days()).set_index("city")
    assert rates.loc["A", "nontraveller_rate"] == 2 / 8
    assert rates.loc["B", "nontraveller_rate"] == 1 / 9


def test_support_threshold_has_no_implicit_default():
    diag = support_diagnostics(
        _person_days().query("t_minutes > 0"),
        city_col="city",
        r_col="r",
        weight_col="weight",
    )
    out = estimable_global_support(diag, min_effective_n=1.0)
    assert out.global_support.all()
