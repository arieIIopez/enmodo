import pandas as pd

from scripts.kitagawa_mobility import symmetric_kitagawa_decomposition


def _inputs():
    curves = pd.DataFrame(
        {
            "city": ["A", "A", "B", "B"],
            "r": [1, 2, 1, 2],
            "m": [10.0, 20.0, 20.0, 40.0],
        }
    )
    refs = pd.DataFrame(
        {
            "reference": ["observed:A", "observed:A", "observed:B", "observed:B"],
            "r": [1, 2, 1, 2],
            "weight": [0.75, 0.25, 0.25, 0.75],
            "source_city": ["A", "A", "B", "B"],
        }
    )
    return curves, refs


def test_symmetric_kitagawa_identity_is_exact():
    curves, refs = _inputs()
    row = symmetric_kitagawa_decomposition(curves, refs, support=[1, 2]).iloc[0]

    # Own-composition means: A=12.5, B=35.0, total difference=-22.5.
    assert row.mean_time_a_on_own_H == 12.5
    assert row.mean_time_b_on_own_H == 35.0
    assert row.total_difference == -22.5

    # Hbar=(0.5,0.5): conditional = .5*(-10)+.5*(-20)=-15.
    assert row.conditional_T_given_P1_component == -15.0
    # mbar=(15,30): composition = 15*(.5)+30*(-.5)=-7.5.
    assert row.participation_composition_component == -7.5
    assert abs(row.identity_residual) < 1e-12


def test_identical_participation_distributions_zero_composition_component():
    curves, refs = _inputs()
    refs.loc[refs.source_city == "B", "weight"] = [0.75, 0.25]
    row = symmetric_kitagawa_decomposition(curves, refs, support=[1, 2]).iloc[0]
    assert abs(row.participation_composition_component) < 1e-12
    assert abs(row.total_difference - row.conditional_T_given_P1_component) < 1e-12


def test_identical_conditional_curves_zero_conditional_component():
    curves, refs = _inputs()
    curves.loc[curves.city == "B", "m"] = [10.0, 20.0]
    row = symmetric_kitagawa_decomposition(curves, refs, support=[1, 2]).iloc[0]
    assert abs(row.conditional_T_given_P1_component) < 1e-12
    assert abs(row.total_difference - row.participation_composition_component) < 1e-12
