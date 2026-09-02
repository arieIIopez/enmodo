"""Symmetric Kitagawa decomposition for mobility time and participation.

For two cities a and b on one common discrete support P0, let:

    m_c(p) = E[T | P1=p, c]
    H_c(p) = city c's participation distribution on P0

Then the difference in standardized observed means on that common support is
exactly decomposed as:

    T_a - T_b
      = sum_p Hbar(p) [m_a(p)-m_b(p)]
      + sum_p mbar(p) [H_a(p)-H_b(p)]

where Hbar=(H_a+H_b)/2 and mbar=(m_a+m_b)/2.

The first term is the conditional T|P1 component; the second is participation
composition. This is a descriptive identity, not causal attribution.
"""

from __future__ import annotations

from itertools import combinations
from typing import Iterable

import numpy as np
import pandas as pd


_CURVE_REQUIRED = {"city", "r", "m"}
_REF_REQUIRED = {"reference", "r", "weight", "source_city"}


def _require(df: pd.DataFrame, cols: set[str], name: str) -> None:
    missing = sorted(cols.difference(df.columns))
    if missing:
        raise ValueError(f"{name} is missing required columns: {missing}")


def _support(values: Iterable[float]) -> list[float]:
    out = sorted(set(float(v) for v in values))
    if not out or any(not np.isfinite(v) for v in out):
        raise ValueError("support must be finite and non-empty")
    return out


def symmetric_kitagawa_decomposition(
    curves: pd.DataFrame,
    observed_references: pd.DataFrame,
    *,
    support: Iterable[float] | None = None,
    atol: float = 1e-9,
) -> pd.DataFrame:
    """Decompose pairwise mean-time differences on one frozen support.

    Parameters
    ----------
    curves:
        One row per city × r with columns city, r, m.
    observed_references:
        Observed-city references with columns reference, r, weight, source_city.
        There must be exactly one reference associated with each city used.
    support:
        Frozen support. If omitted, the exact intersection of curve categories
        and reference categories is used, but confirmatory analyses should pass
        the preregistered support explicitly.
    atol:
        Numerical identity tolerance. A residual larger than atol raises.

    Returns
    -------
    One row per unordered city pair. Components sum exactly (within floating
    precision) to the total difference. Negative conditional component means
    city_a requires less time than city_b at a common participation composition.
    """
    _require(curves, _CURVE_REQUIRED, "curves")
    _require(observed_references, _REF_REQUIRED, "observed_references")

    c = curves[["city", "r", "m"]].copy()
    h = observed_references[["reference", "r", "weight", "source_city"]].copy()
    if c.isna().any().any() or h[["reference", "r", "weight", "source_city"]].isna().any().any():
        raise ValueError("curves and observed references must be non-missing")
    if (h["weight"] < 0).any():
        raise ValueError("reference weights must be non-negative")
    if c.duplicated(["city", "r"]).any():
        raise ValueError("curves must contain exactly one estimate per city-r cell")

    cities = sorted(c["city"].astype(str).unique())
    if len(cities) < 2:
        raise ValueError("at least two cities are required")

    refs_per_city = h.groupby("source_city", observed=True)["reference"].nunique()
    missing_ref = [city for city in cities if city not in refs_per_city.index]
    if missing_ref:
        raise ValueError(f"missing observed-city reference for: {missing_ref}")
    ambiguous = refs_per_city[refs_per_city != 1]
    if not ambiguous.empty:
        raise ValueError(f"each source city must map to one reference: {ambiguous.to_dict()}")

    if support is None:
        common = set(c["r"].astype(float)) & set(h["r"].astype(float))
        grid = _support(common)
    else:
        grid = _support(support)
    grid_set = set(grid)

    curve_wide = (
        c.loc[c["r"].astype(float).isin(grid_set)]
        .assign(r=lambda x: x["r"].astype(float), city=lambda x: x["city"].astype(str))
        .pivot(index="r", columns="city", values="m")
        .reindex(grid)
    )
    if any(city not in curve_wide.columns for city in cities) or curve_wide[cities].isna().any().any():
        raise ValueError("every city must have a curve estimate at every support value")

    city_reference_name = {
        str(city): str(
            h.loc[h["source_city"].astype(str) == str(city), "reference"].iloc[0]
        )
        for city in cities
    }
    ref_rows = []
    for city in cities:
        ref_name = city_reference_name[city]
        sub = h.loc[h["reference"].astype(str) == ref_name, ["r", "weight"]].copy()
        sub["r"] = sub["r"].astype(float)
        outside_mass = float(sub.loc[~sub["r"].isin(grid_set), "weight"].sum())
        if outside_mass > atol:
            raise ValueError(
                f"reference {ref_name} places positive mass outside supplied support"
            )
        sub = sub.loc[sub["r"].isin(grid_set)].groupby("r", as_index=False)["weight"].sum()
        sub = sub.set_index("r").reindex(grid, fill_value=0.0)
        total = float(sub["weight"].sum())
        if total <= 0:
            raise ValueError(f"reference {ref_name} has zero mass on supplied support")
        sub["weight"] = sub["weight"] / total
        sub["city"] = city
        ref_rows.append(sub.reset_index())

    ref_wide = pd.concat(ref_rows, ignore_index=True).pivot(index="r", columns="city", values="weight").reindex(grid)
    if ref_wide[cities].isna().any().any():
        raise ValueError("reference grid is incomplete")

    records = []
    for a, b in combinations(cities, 2):
        ma = curve_wide[a].to_numpy(dtype=float)
        mb = curve_wide[b].to_numpy(dtype=float)
        ha = ref_wide[a].to_numpy(dtype=float)
        hb = ref_wide[b].to_numpy(dtype=float)

        mean_a = float(np.sum(ha * ma))
        mean_b = float(np.sum(hb * mb))
        total_diff = mean_a - mean_b
        hbar = 0.5 * (ha + hb)
        mbar = 0.5 * (ma + mb)
        conditional = float(np.sum(hbar * (ma - mb)))
        composition = float(np.sum(mbar * (ha - hb)))
        residual = float(total_diff - conditional - composition)
        if abs(residual) > atol:
            raise RuntimeError(
                f"Kitagawa identity failed for {a} vs {b}: residual={residual}"
            )

        records.append(
            {
                "city_a": a,
                "city_b": b,
                "mean_time_a_on_own_H": mean_a,
                "mean_time_b_on_own_H": mean_b,
                "total_difference": total_diff,
                "conditional_T_given_P1_component": conditional,
                "participation_composition_component": composition,
                "identity_residual": residual,
            }
        )

    return pd.DataFrame.from_records(records)
