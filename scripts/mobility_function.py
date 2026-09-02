"""Primary estimator for the mobility time-participation function.

For the confirmatory specification R=P1 (number of observed out-of-home
activity episodes in a valid person-day), m_c(p)=E_w[T|P1=p,c] is estimated
nonparametrically as a design-weighted cell mean. This avoids imposing a
functional form on the primary estimand. Smoothers/frontiers remain secondary
robustness or descriptive analyses.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def estimate_time_participation_curve(
    person_days: pd.DataFrame,
    city_col: str = "city",
    participation_col: str = "r",
    time_col: str = "t_minutes",
    weight_col: str = "weight",
    require_positive_time: bool = True,
) -> pd.DataFrame:
    """Estimate m_c(p)=E_w[T|P1=p,c] with design-weighted cell means.

    Output columns `city`, `r`, `m` plug directly into
    `scalar_compressibility.scalarize_curves`. Additional diagnostics quantify
    cell support. Non-travellers (T=0) are excluded by default in accordance
    with the current base specification and must be reported separately.
    """
    required = {city_col, participation_col, time_col, weight_col}
    missing = required.difference(person_days.columns)
    if missing:
        raise ValueError(f"person_days is missing required columns: {sorted(missing)}")

    df = person_days[[city_col, participation_col, time_col, weight_col]].copy()
    if df[[city_col, participation_col, time_col, weight_col]].isna().any().any():
        raise ValueError("city, participation, time and weight must be non-missing")
    if (df[weight_col] < 0).any():
        raise ValueError("design weights must be non-negative")
    if (df[time_col] < 0).any():
        raise ValueError("daily mobility time cannot be negative")
    if (df[participation_col] < 0).any():
        raise ValueError("P1 cannot be negative")

    if require_positive_time:
        df = df.loc[df[time_col] > 0].copy()
    if df.empty:
        raise ValueError("no eligible person-days remain after filtering")

    df["weighted_t"] = df[weight_col] * df[time_col]
    df["weight_sq"] = df[weight_col] ** 2
    grouped = (
        df.groupby([city_col, participation_col], observed=True, as_index=False)
        .agg(
            weighted_t_sum=("weighted_t", "sum"),
            weight_sum=(weight_col, "sum"),
            weight_sq_sum=("weight_sq", "sum"),
            n_raw=(time_col, "size"),
        )
    )
    if (grouped["weight_sum"] <= 0).any():
        raise ValueError("every retained city-P1 cell must have positive design weight")

    grouped["m"] = grouped["weighted_t_sum"] / grouped["weight_sum"]
    grouped["n_eff_kish"] = np.where(
        grouped["weight_sq_sum"] > 0,
        grouped["weight_sum"] ** 2 / grouped["weight_sq_sum"],
        0.0,
    )
    grouped = grouped.rename(columns={city_col: "city", participation_col: "r"})
    return grouped[
        ["city", "r", "m", "n_raw", "weight_sum", "n_eff_kish"]
    ].sort_values(["city", "r"]).reset_index(drop=True)


def nontraveller_rate(
    person_days: pd.DataFrame,
    city_col: str = "city",
    time_col: str = "t_minutes",
    weight_col: str = "weight",
) -> pd.DataFrame:
    """Weighted T=0 share, reported separately from the base coefficient."""
    required = {city_col, time_col, weight_col}
    missing = required.difference(person_days.columns)
    if missing:
        raise ValueError(f"person_days is missing required columns: {sorted(missing)}")
    df = person_days[[city_col, time_col, weight_col]].copy()
    if df.isna().any().any():
        raise ValueError("city, time and weight must be non-missing")
    if (df[weight_col] < 0).any() or (df[time_col] < 0).any():
        raise ValueError("weights and time must be non-negative")

    df["nontraveller_weight"] = np.where(df[time_col] == 0, df[weight_col], 0.0)
    out = (
        df.groupby(city_col, observed=True, as_index=False)
        .agg(
            total_weight=(weight_col, "sum"),
            nontraveller_weight=("nontraveller_weight", "sum"),
        )
    )
    out["nontraveller_rate"] = out["nontraveller_weight"] / out["total_weight"]
    return out
