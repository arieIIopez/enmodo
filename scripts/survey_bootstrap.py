"""Survey-aware joint bootstrap for scalar compressibility.

Confirmatory inference resamples every city in each replicate, re-estimates the
conditional time-participation function m_c(p), re-estimates the observed-city
reference distributions H_c^0, and then computes all pair/reference deltas.

This preserves dependence when a city supplies both one of the curves being
compared and the reference distribution. A diagnostic `reference_mode='fixed'`
keeps H_c^0 at its point estimate to isolate uncertainty in m_c(p); it is not
the default confirmatory interval.

The common support is supplied explicitly and is never changed inside the
bootstrap. A replicate missing a city-P1 support cell is recorded as failed;
there is no interpolation or silent support shrinkage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from scripts.mobility_function import estimate_time_participation_curve
from scripts.reference_distributions import observed_city_references
from scripts.scalar_compressibility import pairwise_deltas, scalarize_curves


@dataclass(frozen=True)
class SurveyDesign:
    cluster_col: str
    stratum_col: str | None = None


@dataclass(frozen=True)
class BootstrapDiagnostics:
    requested_replicates: int
    successful_replicates: int
    failed_replicates: int
    failure_rate: float
    reference_mode: str
    seed: int


def _require(df: pd.DataFrame, cols: Sequence[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise ValueError(f"{name}: missing required columns {missing}")


def resample_clusters(
    df: pd.DataFrame,
    *,
    design: SurveyDesign,
    rng: np.random.Generator,
) -> pd.DataFrame:
    """With-replacement cluster bootstrap, stratified when a stratum exists.

    The number of sampled clusters equals the observed number of clusters in
    each stratum. Rows from a selected cluster are copied as a block. Original
    analysis weights are retained; multiplicity is represented by duplicated
    cluster blocks.
    """
    required = [design.cluster_col]
    if design.stratum_col:
        required.append(design.stratum_col)
    _require(df, required, "bootstrap frame")
    if df[required].isna().any().any():
        raise ValueError("cluster/stratum identifiers must be non-missing")

    work = df.copy()
    if design.stratum_col is None:
        work["__bootstrap_stratum"] = "__all__"
        stratum_col = "__bootstrap_stratum"
    else:
        stratum_col = design.stratum_col

    pieces: list[pd.DataFrame] = []
    for stratum, group in work.groupby(stratum_col, observed=True, sort=False):
        clusters = pd.Index(group[design.cluster_col].drop_duplicates())
        if len(clusters) == 0:
            raise ValueError(f"empty cluster set in stratum {stratum!r}")
        draws = rng.choice(clusters.to_numpy(), size=len(clusters), replace=True)
        for draw_number, cluster in enumerate(draws):
            block = group.loc[group[design.cluster_col] == cluster].copy()
            # A selected cluster can occur multiple times. Give each copy a
            # unique replicate-block ID without altering the analysis cluster.
            block["__bootstrap_block"] = f"{stratum}::{cluster}::{draw_number}"
            pieces.append(block)

    if not pieces:
        raise ValueError("bootstrap produced no rows")
    out = pd.concat(pieces, ignore_index=True)
    if "__bootstrap_stratum" in out.columns:
        out = out.drop(columns="__bootstrap_stratum")
    return out


def _support_is_complete(curves: pd.DataFrame, cities: Sequence[str], support: Sequence[float]) -> bool:
    expected = {(str(city), float(r)) for city in cities for r in support}
    observed = {(str(row.city), float(row.r)) for row in curves.itertuples(index=False)}
    return expected.issubset(observed)


def point_estimates(
    person_days: pd.DataFrame,
    *,
    support: Sequence[float],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return curves, references, scalars and pairwise deltas on frozen support."""
    curves = estimate_time_participation_curve(person_days)
    cities = sorted(person_days["city"].astype(str).unique())
    if not _support_is_complete(curves, cities, support):
        raise ValueError("point-estimate data do not cover every city × frozen-support cell")
    curves = curves.loc[curves["r"].astype(float).isin(set(map(float, support)))].copy()
    refs = observed_city_references(person_days, support=support)
    scalars = scalarize_curves(curves, refs, cities=cities)
    deltas = pairwise_deltas(scalars)
    return curves, refs, scalars, deltas


def joint_bootstrap_deltas(
    person_days: pd.DataFrame,
    *,
    support: Sequence[float],
    designs: Mapping[str, SurveyDesign],
    n_boot: int = 1000,
    seed: int = 20260901,
    reference_mode: str = "joint",
    alpha: float = 0.05,
) -> tuple[pd.DataFrame, pd.DataFrame, BootstrapDiagnostics]:
    """Bootstrap pair/reference deltas and attach percentile intervals.

    Parameters
    ----------
    reference_mode:
        `joint` re-estimates H_c^0 in each bootstrap replicate and is the
        confirmatory default. `fixed` uses the point-estimate references and is
        diagnostic only.

    Returns
    -------
    point_with_ci:
        Point pair/reference deltas with `ci_lower`, `ci_upper`, `boot_n`.
    bootstrap_draws:
        Successful replicate deltas with a `replicate` column.
    diagnostics:
        Counts of requested/successful/failed replicates. Any failures must be
        reported; they usually indicate support that is too thin for stable
        confirmatory inference.
    """
    if n_boot < 1:
        raise ValueError("n_boot must be >= 1")
    if not (0 < alpha < 1):
        raise ValueError("alpha must lie in (0,1)")
    if reference_mode not in {"joint", "fixed"}:
        raise ValueError("reference_mode must be 'joint' or 'fixed'")

    _require(person_days, ["city", "r", "t_minutes", "weight"], "person_days")
    cities = sorted(person_days["city"].astype(str).unique())
    if set(cities) != set(designs):
        raise ValueError("designs must contain exactly one SurveyDesign per city")

    point_curves, point_refs, _, point_deltas = point_estimates(person_days, support=support)
    del point_curves

    rng = np.random.default_rng(seed)
    draws: list[pd.DataFrame] = []
    failures = 0

    city_frames = {
        city: person_days.loc[person_days["city"].astype(str) == city].copy()
        for city in cities
    }

    for b in range(n_boot):
        sampled_parts = []
        for city in cities:
            sampled_parts.append(
                resample_clusters(city_frames[city], design=designs[city], rng=rng)
            )
        sampled = pd.concat(sampled_parts, ignore_index=True)

        curves = estimate_time_participation_curve(sampled)
        if not _support_is_complete(curves, cities, support):
            failures += 1
            continue
        curves = curves.loc[curves["r"].astype(float).isin(set(map(float, support)))].copy()

        refs = (
            observed_city_references(sampled, support=support)
            if reference_mode == "joint"
            else point_refs
        )
        try:
            scalars = scalarize_curves(curves, refs, cities=cities)
        except ValueError:
            failures += 1
            continue
        delta = pairwise_deltas(scalars)
        delta["replicate"] = b
        draws.append(delta)

    if not draws:
        raise RuntimeError("all bootstrap replicates failed frozen-support requirements")

    boot = pd.concat(draws, ignore_index=True)
    q_low = alpha / 2
    q_high = 1 - alpha / 2
    ci = (
        boot.groupby(["city_a", "city_b", "reference"], observed=True)["delta"]
        .agg(
            ci_lower=lambda x: float(x.quantile(q_low)),
            ci_upper=lambda x: float(x.quantile(q_high)),
            boot_n="size",
        )
        .reset_index()
    )
    point_with_ci = point_deltas.merge(
        ci,
        on=["city_a", "city_b", "reference"],
        how="left",
        validate="one_to_one",
    )
    if point_with_ci[["ci_lower", "ci_upper", "boot_n"]].isna().any().any():
        raise RuntimeError("bootstrap intervals are incomplete for one or more pair/reference cells")

    successful = n_boot - failures
    diagnostics = BootstrapDiagnostics(
        requested_replicates=int(n_boot),
        successful_replicates=int(successful),
        failed_replicates=int(failures),
        failure_rate=float(failures / n_boot),
        reference_mode=reference_mode,
        seed=int(seed),
    )
    return point_with_ci, boot, diagnostics
