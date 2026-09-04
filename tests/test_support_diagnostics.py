import numpy as np
import pandas as pd
import pytest

from scripts.paper1_protocol import evaluate_preregistered_supports
from scripts.support_diagnostics import contiguous_estimable_support


def _diagnostics():
    rows = []
    for city, eff in {
        "A": {0: 500, 1: 300, 2: 180, 3: 120, 4: 80, 5: 140},
        "B": {0: 450, 1: 250, 2: 160, 3: 110, 4: 90, 5: 130},
        "C": {0: 400, 1: 220, 2: 150, 3: 105, 4: 70, 5: 120},
    }.items():
        for r, n_eff in eff.items():
            rows.append(
                {
                    "city": city,
                    "r": r,
                    "n_eff_kish": float(n_eff),
                    "weighted_share": 0.1,
                }
            )
    return pd.DataFrame(rows)


def test_contiguous_support_stops_at_first_failed_level():
    support = contiguous_estimable_support(
        _diagnostics(), min_effective_n=100, start_r=1
    )
    assert np.array_equal(support, np.array([1.0, 2.0, 3.0]))


def test_contiguous_support_does_not_reenter_after_gap():
    support = contiguous_estimable_support(
        _diagnostics(), min_effective_n=100, start_r=4
    )
    assert support.size == 0


def test_preregistered_thresholds_are_fixed_and_ordered():
    out = evaluate_preregistered_supports(_diagnostics())
    primary = out.loc[out.role == "primary"].iloc[0]
    loose = out.loc[out.role == "sensitivity_looser"].iloc[0]
    strict = out.loc[out.role == "sensitivity_stricter"].iloc[0]

    assert primary.min_effective_n == 100
    assert primary.support_values == "1;2;3"
    assert loose.min_effective_n == 50
    assert loose.support_values == "1;2;3;4;5"
    assert strict.min_effective_n == 200
    assert strict.support_values == "1"


def test_contiguous_support_rejects_noninteger_participation():
    bad = _diagnostics().copy()
    # Pandas 3.0 rejects assigning a non-integer value into an int64 column
    # before the validator under test can see it. Cast explicitly so this test
    # continues to exercise the intended semantic guard.
    bad["r"] = bad["r"].astype(float)
    bad.loc[bad.index[0], "r"] = 0.5
    with pytest.raises(ValueError, match="integer-valued"):
        contiguous_estimable_support(bad, min_effective_n=100, start_r=1)
