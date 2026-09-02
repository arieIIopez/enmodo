"""Reference-distribution utilities for scalar compressibility analyses.

Primary use case: R=P1, the discrete count of out-of-home activity episodes
per valid person-day. Confirmatory references are city-specific design-weighted
empirical distributions restricted to one global common support. A uniform
reference over the discrete P1 support is available only as a structural stress
test, not as the default population standard.
"""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd


def _validated_support(support: Iterable[float]) -> np.ndarray:
    values = np.asarray(list(support), dtype=float)
    if values.size == 0:
        raise ValueError("support must contain at least one value")
    if np.isnan(values).any():
        raise ValueError("support cannot contain missing values")
    values = np.unique(values)
    return np.sort(values)


def support_coverage(
    person_days: pd.DataFrame,
    support: Iterable[float],
    city_col: str = "city",
    r_col: str = "r",
    weight_col: str = "weight",
) -> pd.DataFrame:
    """Weighted coverage of a global R support in each city.

    Coverage is the share of the city's positive design weight whose observed R
    lies inside the common support. This quantity must be reported before a
    multi-city scalar comparison is interpreted.
    """
    grid = _validated_support(support)
    required = {city_col, r_col, weight_col}
    missing = required.difference(person_days.columns)
    if missing:
        raise ValueError(f"person_days is missing required columns: {sorted(missing)}")

    df = person_days[[city_col, r_col, weight_col]].copy()
    if df[[city_col, r_col, weight_col]].isna().any().any():
        raise ValueError("city, r and weight must be non-missing")
    if (df[weight_col] < 0).any():
        raise ValueError("design weights must be non-negative")

    df["in_support"] = df[r_col].astype(float).isin(set(grid.tolist()))
    total = df.groupby(city_col, observed=True)[weight_col].sum().rename("total_weight")
    inside = (
        df.loc[df["in_support"]]
        .groupby(city_col, observed=True)[weight_col]
        .sum()
        .rename("support_weight")
    )
    out = pd.concat([total, inside], axis=1).fillna({"support_weight": 0.0}).reset_index()
    if (out["total_weight"] <= 0).any():
        raise ValueError("every city must have positive total design weight")
    out["coverage"] = out["support_weight"] / out["total_weight"]

    observed_ranges = (
        df.groupby(city_col, observed=True)[r_col]
        .agg(observed_r_min="min", observed_r_max="max")
        .reset_index()
    )
    out = out.merge(observed_ranges, on=city_col, how="left", validate="one_to_one")
    out["support_r_min"] = float(grid.min())
    out["support_r_max"] = float(grid.max())
    out["excluded_weight"] = out["total_weight"] - out["support_weight"]
    return out


def observed_city_references(
    person_days: pd.DataFrame,
    support: Iterable[float],
    city_col: str = "city",
    r_col: str = "r",
    weight_col: str = "weight",
    reference_prefix: str = "observed",
) -> pd.DataFrame:
    """Build H_c^0 for every city on one common discrete support.

    Each city's design-weighted empirical distribution is restricted to the
    supplied support and renormalized. Returned columns match the scalar
    compressibility API: reference, r, weight.
    """
    grid = _validated_support(support)
    required = {city_col, r_col, weight_col}
    missing = required.difference(person_days.columns)
    if missing:
        raise ValueError(f"person_days is missing required columns: {sorted(missing)}")

    df = person_days[[city_col, r_col, weight_col]].copy()
    if df[[city_col, r_col, weight_col]].isna().any().any():
        raise ValueError("city, r and weight must be non-missing")
    if (df[weight_col] < 0).any():
        raise ValueError("design weights must be non-negative")

    df[r_col] = df[r_col].astype(float)
    df = df.loc[df[r_col].isin(set(grid.tolist()))].copy()
    if df.empty:
        raise ValueError("no observations fall inside support")

    cities = sorted(df[city_col].unique())
    table = (
        df.groupby([city_col, r_col], observed=True)[weight_col]
        .sum()
        .unstack(fill_value=0.0)
        .reindex(index=cities, columns=grid, fill_value=0.0)
    )
    totals = table.sum(axis=1)
    if (totals <= 0).any():
        bad = totals[totals <= 0].index.tolist()
        raise ValueError(f"cities with zero support mass: {bad}")
    table = table.div(totals, axis=0)

    records = []
    for city, row in table.iterrows():
        for r, weight in row.items():
            records.append(
                {
                    "reference": f"{reference_prefix}:{city}",
                    "r": float(r),
                    "weight": float(weight),
                    "source_city": city,
                    "reference_type": "observed_city",
                }
            )
    return pd.DataFrame.from_records(records)


def uniform_discrete_reference(
    support: Iterable[float],
    name: str = "stress:uniform_p1",
) -> pd.DataFrame:
    """Uniform reference over a discrete cardinal support.

    Intended for P1 (activity-episode count) as a stress test. Do not use this
    construction automatically for transformed, ordinal or arbitrary-index R.
    """
    grid = _validated_support(support)
    weight = 1.0 / len(grid)
    return pd.DataFrame(
        {
            "reference": name,
            "r": grid,
            "weight": weight,
            "source_city": pd.NA,
            "reference_type": "uniform_discrete_stress",
        }
    )


def equal_city_mixture(observed_references: pd.DataFrame, name: str = "descriptive:equal_city") -> pd.DataFrame:
    """Return the equal mixture of H_c^0 as a descriptive interior scenario.

    This mixture is not an additional extreme point of conv{H_c^0}; it is
    provided for interpretation and tables only.
    """
    required = {"reference", "r", "weight", "reference_type"}
    missing = required.difference(observed_references.columns)
    if missing:
        raise ValueError(f"observed_references is missing columns: {sorted(missing)}")
    obs = observed_references.loc[
        observed_references["reference_type"] == "observed_city"
    ].copy()
    if obs.empty:
        raise ValueError("no observed-city references found")

    n_refs = obs["reference"].nunique()
    mixture = (
        obs.groupby("r", observed=True, as_index=False)["weight"].sum()
        .assign(weight=lambda x: x["weight"] / n_refs)
    )
    mixture["reference"] = name
    mixture["source_city"] = pd.NA
    mixture["reference_type"] = "equal_city_mixture"
    return mixture[["reference", "r", "weight", "source_city", "reference_type"]]
