"""Scalar compressibility utilities for the Mobility Coefficient programme.

The module treats m_c(r)=E[T|R=r,c] as the primary estimand and tests
whether pairwise comparisons remain invariant over a preregistered finite
set of reference distributions H_k. The convex hull of those references
is covered automatically because Delta_ab(H) is linear in H.
"""

from __future__ import annotations

from itertools import combinations
from typing import Iterable, Optional

import numpy as np
import pandas as pd


REQUIRED_CURVE_COLUMNS = {"city", "r", "m"}
REQUIRED_REFERENCE_COLUMNS = {"reference", "r", "weight"}


def _require_columns(df: pd.DataFrame, required: set[str], name: str) -> None:
    missing = sorted(required.difference(df.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def normalize_references(references: pd.DataFrame, atol: float = 1e-10) -> pd.DataFrame:
    """Return references with non-negative weights normalized within H_k."""
    _require_columns(references, REQUIRED_REFERENCE_COLUMNS, "references")
    out = references.copy()
    if out[["r", "weight"]].isna().any().any():
        raise ValueError("references contains missing r/weight values")
    if (out["weight"] < -atol).any():
        raise ValueError("reference weights must be non-negative")
    totals = out.groupby("reference", observed=True)["weight"].transform("sum")
    if (totals <= atol).any():
        raise ValueError("every reference must have positive total weight")
    out["weight"] = out["weight"] / totals
    return out


def common_support_grid(
    curves: pd.DataFrame,
    cities: Optional[Iterable[str]] = None,
) -> np.ndarray:
    """Return r values observed for every selected city.

    This deliberately avoids extrapolation. If curves are estimated on
    different grids, caller should interpolate *within* each observed support
    before using this function, and document that interpolation rule.
    """
    _require_columns(curves, REQUIRED_CURVE_COLUMNS, "curves")
    selected = list(cities) if cities is not None else sorted(curves["city"].unique())
    if len(selected) < 2:
        raise ValueError("at least two cities are required")
    supports = [
        set(curves.loc[curves["city"] == city, "r"].dropna().tolist())
        for city in selected
    ]
    if any(len(s) == 0 for s in supports):
        raise ValueError("one or more cities have empty support")
    common = set.intersection(*supports)
    if not common:
        raise ValueError("cities have no common r support")
    return np.array(sorted(common), dtype=float)


def scalarize_curves(
    curves: pd.DataFrame,
    references: pd.DataFrame,
    cities: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    """Compute B_c(H_k)=sum_r m_c(r) w_k(r) on exact common grid.

    References must put zero mass outside the exact common support of the
    selected cities. This is a confirmatory guard against hidden extrapolation.
    """
    _require_columns(curves, REQUIRED_CURVE_COLUMNS, "curves")
    refs = normalize_references(references)
    selected = list(cities) if cities is not None else sorted(curves["city"].unique())
    grid = common_support_grid(curves, selected)
    grid_set = set(grid.tolist())

    bad_ref = refs.loc[(refs["weight"] > 0) & (~refs["r"].isin(grid_set))]
    if not bad_ref.empty:
        sample = bad_ref[["reference", "r"]].drop_duplicates().head(10).to_dict("records")
        raise ValueError(
            "reference places positive mass outside common support; "
            f"examples: {sample}"
        )

    refs = refs.loc[refs["r"].isin(grid_set)].copy()
    refs = normalize_references(refs)

    sub = curves.loc[curves["city"].isin(selected) & curves["r"].isin(grid_set)].copy()
    if sub.duplicated(["city", "r"]).any():
        raise ValueError("curves must contain one m estimate per city-r pair")

    merged = sub.merge(refs, on="r", how="inner", validate="many_to_many")
    merged["weighted_m"] = merged["m"] * merged["weight"]
    out = (
        merged.groupby(["city", "reference"], observed=True, as_index=False)
        .agg(B=("weighted_m", "sum"))
    )

    expected = len(selected) * refs["reference"].nunique()
    if len(out) != expected:
        raise ValueError("incomplete city-reference scalarization")
    return out


def pairwise_deltas(scalars: pd.DataFrame) -> pd.DataFrame:
    """Compute Delta_ab(H)=B_a(H)-B_b(H) for all unordered city pairs."""
    _require_columns(scalars, {"city", "reference", "B"}, "scalars")
    wide = scalars.pivot(index="reference", columns="city", values="B")
    if wide.isna().any().any():
        raise ValueError("every reference must contain B for every city")

    records: list[dict] = []
    cities = sorted(wide.columns)
    for a, b in combinations(cities, 2):
        for reference, row in wide.iterrows():
            records.append(
                {
                    "city_a": a,
                    "city_b": b,
                    "reference": reference,
                    "B_a": float(row[a]),
                    "B_b": float(row[b]),
                    "delta": float(row[a] - row[b]),
                }
            )
    return pd.DataFrame.from_records(records)


def _point_status(delta_min: float, delta_max: float, delta_t: float) -> str:
    if delta_max < -delta_t:
        return "a_dominates_b"
    if delta_min >= -delta_t and delta_max <= delta_t:
        return "practical_equivalence"
    if delta_min > delta_t:
        return "b_dominates_a"
    return "structural_incomparability"


def _inferential_status(
    lower_min: float,
    upper_max: float,
    delta_t: float,
) -> str:
    if upper_max < -delta_t:
        return "a_dominates_b"
    if lower_min >= -delta_t and upper_max <= delta_t:
        return "practical_equivalence"
    if lower_min > delta_t:
        return "b_dominates_a"
    return "not_resolved"


def classify_deltas(
    deltas: pd.DataFrame,
    delta_t: float,
    ci_lower_col: Optional[str] = None,
    ci_upper_col: Optional[str] = None,
) -> pd.DataFrame:
    """Classify robust pairwise ordering over the convex hull of H_k.

    If CI columns are supplied, they must be pairwise Delta intervals for each
    extreme reference. The function reports whether unresolved inference is
    caused by point-level reference sensitivity, sampling uncertainty, or both.
    """
    _require_columns(deltas, {"city_a", "city_b", "reference", "delta"}, "deltas")
    if delta_t < 0:
        raise ValueError("delta_t must be non-negative")
    if (ci_lower_col is None) ^ (ci_upper_col is None):
        raise ValueError("both ci_lower_col and ci_upper_col are required together")
    if ci_lower_col:
        _require_columns(deltas, {ci_lower_col, ci_upper_col}, "deltas")
        if (deltas[ci_lower_col] > deltas[ci_upper_col]).any():
            raise ValueError("CI lower bound cannot exceed upper bound")

    records: list[dict] = []
    for (a, b), grp in deltas.groupby(["city_a", "city_b"], observed=True, sort=True):
        i_min = grp["delta"].idxmin()
        i_max = grp["delta"].idxmax()
        delta_min = float(grp.loc[i_min, "delta"])
        delta_max = float(grp.loc[i_max, "delta"])
        point = _point_status(delta_min, delta_max, delta_t)

        inferential: Optional[str] = None
        if ci_lower_col:
            lower_min = float(grp[ci_lower_col].min())
            upper_max = float(grp[ci_upper_col].max())
            inferential = _inferential_status(lower_min, upper_max, delta_t)
            if inferential == "not_resolved":
                diagnosis = (
                    "structural_incomparability_plus_sampling_uncertainty"
                    if point == "structural_incomparability"
                    else "sampling_indeterminacy"
                )
            else:
                diagnosis = "resolved"
        else:
            diagnosis = (
                "structural_incomparability"
                if point == "structural_incomparability"
                else "point_estimate_resolved"
            )

        records.append(
            {
                "city_a": a,
                "city_b": b,
                "point_status": point,
                "inferential_status": inferential,
                "diagnosis": diagnosis,
                "delta_min": delta_min,
                "delta_max": delta_max,
                "reference_at_min": str(grp.loc[i_min, "reference"]),
                "reference_at_max": str(grp.loc[i_max, "reference"]),
                "delta_t": float(delta_t),
            }
        )
    return pd.DataFrame.from_records(records)


def classify_from_scalar_ci(scalar_ci: pd.DataFrame, delta_t: float) -> pd.DataFrame:
    """Classify city-pair/reference estimates carrying pairwise Delta CIs.

    Expected columns are city_a, city_b, reference, delta, ci_lower, ci_upper.
    Pairwise bootstrap intervals are required: subtracting independent marginal
    city CIs is not a valid substitute when estimates share H or common draws.
    """
    return classify_deltas(
        scalar_ci,
        delta_t=delta_t,
        ci_lower_col="ci_lower",
        ci_upper_col="ci_upper",
    )


def dominance_edges(classification: pd.DataFrame) -> pd.DataFrame:
    """Return directed robust-dominance edges for graphing a partial order."""
    _require_columns(
        classification,
        {"city_a", "city_b", "point_status", "inferential_status"},
        "classification",
    )
    records = []
    for _, row in classification.iterrows():
        status = (
            row["inferential_status"]
            if pd.notna(row["inferential_status"])
            else row["point_status"]
        )
        if status == "a_dominates_b":
            records.append({"source": row["city_a"], "target": row["city_b"]})
        elif status == "b_dominates_a":
            records.append({"source": row["city_b"], "target": row["city_a"]})
    return pd.DataFrame.from_records(records, columns=["source", "target"])
