"""Kitagawa-style decomposition for mobility time and participation composition.

Within one declared common support, the difference in support-restricted mean
daily mobility time between cities a and b is decomposed exactly into:

1) a conditional T|P1 structure component; and
2) a realized-participation composition component.

This is descriptive, not causal.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
import pandas as pd


def decompose_pair(
    curves: pd.DataFrame,
    observed_references: pd.DataFrame,
    city_a: str,
    city_b: str,
) -> dict:
    """Symmetric two-component decomposition on a common P1 support."""
    curve_required = {"city", "r", "m"}
    ref_required = {"reference", "r", "weight", "source_city", "reference_type"}
    missing_curve = curve_required.difference(curves.columns)
    missing_ref = ref_required.difference(observed_references.columns)
    if missing_curve:
        raise ValueError(f"curves is missing columns: {sorted(missing_curve)}")
    if missing_ref:
        raise ValueError(f"observed_references is missing columns: {sorted(missing_ref)}")
    if city_a == city_b:
        raise ValueError("city_a and city_b must differ")

    ca = curves.loc[curves["city"] == city_a, ["r", "m"]].rename(columns={"m": "m_a"})
    cb = curves.loc[curves["city"] == city_b, ["r", "m"]].rename(columns={"m": "m_b"})

    refs = observed_references.loc[
        observed_references["reference_type"] == "observed_city"
    ].copy()
    ha = refs.loc[refs["source_city"] == city_a, ["r", "weight"]].rename(
        columns={"weight": "h_a"}
    )
    hb = refs.loc[refs["source_city"] == city_b, ["r", "weight"]].rename(
        columns={"weight": "h_b"}
    )

    if ca.empty or cb.empty or ha.empty or hb.empty:
        raise ValueError("missing curve or observed reference for one or both cities")

    table = ca.merge(cb, on="r", how="inner", validate="one_to_one")
    table = table.merge(ha, on="r", how="inner", validate="one_to_one")
    table = table.merge(hb, on="r", how="inner", validate="one_to_one")
    if table.empty:
        raise ValueError("pair has no common support")

    if not np.isclose(table["h_a"].sum(), 1.0) or not np.isclose(table["h_b"].sum(), 1.0):
        raise ValueError("observed references must be normalized on the same support")

    table["h_bar"] = 0.5 * (table["h_a"] + table["h_b"])
    table["m_bar"] = 0.5 * (table["m_a"] + table["m_b"])
    table["conditional_contribution"] = table["h_bar"] * (table["m_a"] - table["m_b"])
    table["composition_contribution"] = table["m_bar"] * (table["h_a"] - table["h_b"])

    mean_a = float((table["h_a"] * table["m_a"]).sum())
    mean_b = float((table["h_b"] * table["m_b"]).sum())
    observed_difference = mean_a - mean_b
    conditional = float(table["conditional_contribution"].sum())
    composition = float(table["composition_contribution"].sum())
    residual = observed_difference - conditional - composition

    return {
        "city_a": city_a,
        "city_b": city_b,
        "support_restricted_mean_a": mean_a,
        "support_restricted_mean_b": mean_b,
        "observed_difference": observed_difference,
        "conditional_time_structure": conditional,
        "participation_composition": composition,
        "identity_residual": residual,
        "n_support_levels": int(len(table)),
    }


def decompose_all_pairs(
    curves: pd.DataFrame,
    observed_references: pd.DataFrame,
) -> pd.DataFrame:
    """Apply the symmetric decomposition to every city pair."""
    cities = sorted(curves["city"].dropna().unique())
    records = [
        decompose_pair(curves, observed_references, a, b)
        for a, b in combinations(cities, 2)
    ]
    return pd.DataFrame.from_records(records)
