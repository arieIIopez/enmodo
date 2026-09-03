"""Frozen confirmatory protocol choices for Paper I.

These constants are intentionally separated from generic utilities so changes
are visible in version control. The primary support rule was fixed before
inspection of the canonical stage-1 support diagnostics generated on
2026-09-03.
"""

from __future__ import annotations

import pandas as pd

from scripts.support_diagnostics import contiguous_estimable_support


PRIMARY_SUPPORT_START_R = 1
PRIMARY_MIN_EFFECTIVE_N = 100.0
SENSITIVITY_MIN_EFFECTIVE_N = (50.0, 200.0)


def evaluate_preregistered_supports(diagnostics: pd.DataFrame) -> pd.DataFrame:
    """Evaluate primary and sensitivity support rules without changing them.

    Returns one row per preregistered Kish-effective-n threshold. The primary
    result uses n_eff >= 100 in every city for every consecutive P1 category
    from 1 through p*. Thresholds 50 and 200 are sensitivity analyses.
    """
    rows = []
    for threshold, role in [
        (PRIMARY_MIN_EFFECTIVE_N, "primary"),
        (SENSITIVITY_MIN_EFFECTIVE_N[0], "sensitivity_looser"),
        (SENSITIVITY_MIN_EFFECTIVE_N[1], "sensitivity_stricter"),
    ]:
        support = contiguous_estimable_support(
            diagnostics,
            min_effective_n=threshold,
            start_r=PRIMARY_SUPPORT_START_R,
        )
        rows.append(
            {
                "role": role,
                "min_effective_n": float(threshold),
                "start_r": int(PRIMARY_SUPPORT_START_R),
                "n_levels": int(len(support)),
                "p_star": int(support[-1]) if len(support) else pd.NA,
                "support_values": ";".join(str(int(x)) for x in support),
            }
        )
    return pd.DataFrame(rows)
