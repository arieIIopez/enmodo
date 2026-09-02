import math

import pandas as pd

from scripts.time_composition_decomposition import decompose_pair


def test_symmetric_decomposition_closes_exactly():
    curves = pd.DataFrame(
        {
            "city": ["A", "A", "B", "B"],
            "r": [1, 2, 1, 2],
            "m": [30.0, 60.0, 40.0, 80.0],
        }
    )
    refs = pd.DataFrame(
        {
            "reference": ["observed:A", "observed:A", "observed:B", "observed:B"],
            "r": [1, 2, 1, 2],
            "weight": [0.75, 0.25, 0.25, 0.75],
            "source_city": ["A", "A", "B", "B"],
            "reference_type": ["observed_city"] * 4,
        }
    )

    out = decompose_pair(curves, refs, "A", "B")
    assert math.isclose(
        out["observed_difference"],
        out["conditional_time_structure"] + out["participation_composition"],
        abs_tol=1e-12,
    )
    assert math.isclose(out["identity_residual"], 0.0, abs_tol=1e-12)
