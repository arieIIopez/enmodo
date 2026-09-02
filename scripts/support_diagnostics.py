"""Diagnostics for estimable common participation support.

For the primary specification R=P1 (discrete activity-episode count), nominal
support is not enough: a P1 category can exist in every city but be supported by
very few effective observations in one of them. These utilities compute raw n,
design-weight mass, weighted share and Kish effective sample size by city-P1.
No default threshold is imposed: threshold choice must be calibrated and frozen
before confirmatory estimation.
"""

from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


def support_diagnostics(
    person_days: pd.DataFrame,
    city_col: str = "city",
    r_col: str = "r",
    weight_col: str = "weight",
) -> pd.DataFrame:
    """Return design-aware support diagnostics for each city x R cell."""
    required = {city_col, r_col, weight_col}
    missing = required.difference(person_days.columns)
    if missing:
        raise ValueError(f"person_days is missing required columns: {sorted(missing)}")

    df = person_days[[city_col, r_col, weight_col]].copy()
    if df[[city_col, r_col, weight_col]].isna().any().any():
        raise ValueError("city, r and weight must be non-missing")
    if (df[weight_col] < 0).any():
        raise ValueError("design weights must be non-negative")

    df["weight_sq"] = df[weight_col] ** 2
    cells = (
        df.groupby([city_col, r_col], observed=True, as_index=False)
        .agg(
            n_raw=(weight_col, "size"),
            weight_sum=(weight_col, "sum"),
            weight_sq_sum=("weight_sq", "sum"),
        )
    )
    cells["n_eff_kish"] = np.where(
        cells["weight_sq_sum"] > 0,
        cells["weight_sum"] ** 2 / cells["weight_sq_sum"],
        0.0,
    )
    city_total = cells.groupby(city_col, observed=True)["weight_sum"].transform("sum")
    cells["weighted_share"] = np.where(city_total > 0, cells["weight_sum"] / city_total, 0.0)
    return cells.sort_values([city_col, r_col]).reset_index(drop=True)


def estimable_global_support(
    diagnostics: pd.DataFrame,
    min_effective_n: Optional[float] = None,
    min_weighted_share: Optional[float] = None,
    city_col: str = "city",
    r_col: str = "r",
) -> pd.DataFrame:
    """Identify R categories passing declared thresholds in every city.

    At least one threshold must be supplied. This function intentionally has no
    default confirmatory cut-off: choosing one after inspecting the final result
    would undermine preregistration.
    """
    required = {city_col, r_col, "n_eff_kish", "weighted_share"}
    missing = required.difference(diagnostics.columns)
    if missing:
        raise ValueError(f"diagnostics is missing required columns: {sorted(missing)}")
    if min_effective_n is None and min_weighted_share is None:
        raise ValueError("declare min_effective_n and/or min_weighted_share")
    if min_effective_n is not None and min_effective_n < 0:
        raise ValueError("min_effective_n must be non-negative")
    if min_weighted_share is not None and not 0 <= min_weighted_share <= 1:
        raise ValueError("min_weighted_share must lie in [0,1]")

    df = diagnostics.copy()
    passed = pd.Series(True, index=df.index)
    if min_effective_n is not None:
        passed &= df["n_eff_kish"] >= min_effective_n
    if min_weighted_share is not None:
        passed &= df["weighted_share"] >= min_weighted_share
    df["cell_pass"] = passed

    n_cities = df[city_col].nunique()
    summary = (
        df.groupby(r_col, observed=True, as_index=False)
        .agg(
            cities_observed=(city_col, "nunique"),
            cities_passing=("cell_pass", "sum"),
            min_n_eff_kish=("n_eff_kish", "min"),
            min_weighted_share=("weighted_share", "min"),
        )
    )
    summary["global_support"] = (
        (summary["cities_observed"] == n_cities)
        & (summary["cities_passing"] == n_cities)
    )
    return summary.sort_values(r_col).reset_index(drop=True)
