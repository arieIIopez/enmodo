import pandas as pd

from scripts.scalar_compressibility import (
    classify_deltas,
    common_support_grid,
    pairwise_deltas,
    scalarize_curves,
)


def _synthetic_inputs():
    curves = pd.DataFrame(
        {
            "city": ["A"] * 3 + ["B"] * 3 + ["C"] * 3,
            "r": [1, 2, 3] * 3,
            "m": [10, 20, 30, 20, 30, 40, 5, 40, 45],
        }
    )
    references = pd.DataFrame(
        {
            "reference": ["low"] * 3 + ["high"] * 3,
            "r": [1, 2, 3] * 2,
            "weight": [0.8, 0.1, 0.1, 0.1, 0.1, 0.8],
        }
    )
    return curves, references


def test_common_support_without_extrapolation():
    curves, _ = _synthetic_inputs()
    assert common_support_grid(curves).tolist() == [1.0, 2.0, 3.0]


def test_stable_dominance_survives_reference_change():
    curves, references = _synthetic_inputs()
    scalars = scalarize_curves(curves, references)
    deltas = pairwise_deltas(scalars)
    out = classify_deltas(deltas, delta_t=2)

    ab = out[(out.city_a == "A") & (out.city_b == "B")].iloc[0]
    assert ab.point_status == "a_dominates_b"
    assert ab.delta_min == -10.0
    assert ab.delta_max == -10.0


def test_reference_sensitive_pair_is_not_forced_into_ranking():
    curves, references = _synthetic_inputs()
    scalars = scalarize_curves(curves, references)
    deltas = pairwise_deltas(scalars)
    out = classify_deltas(deltas, delta_t=2)

    bc = out[(out.city_a == "B") & (out.city_b == "C")].iloc[0]
    assert bc.point_status == "structural_incomparability"
    assert bc.delta_min < -2
    assert bc.delta_max > 2


def test_sampling_indeterminacy_is_distinct_from_structural_incomparability():
    delta_ci = pd.DataFrame(
        {
            "city_a": ["A", "A"],
            "city_b": ["B", "B"],
            "reference": ["low", "high"],
            "delta": [-8.0, -7.0],
            "ci_lower": [-12.0, -11.0],
            "ci_upper": [-1.0, -0.5],
        }
    )
    out = classify_deltas(
        delta_ci,
        delta_t=2,
        ci_lower_col="ci_lower",
        ci_upper_col="ci_upper",
    )
    row = out.iloc[0]
    assert row.point_status == "a_dominates_b"
    assert row.inferential_status == "not_resolved"
    assert row.diagnosis == "sampling_indeterminacy"
