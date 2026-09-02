import pandas as pd

from scripts.survey_bootstrap import SurveyDesign, joint_bootstrap_deltas, resample_clusters


def _person_days():
    rows = []
    # Four clusters per city, each cluster contains both support categories so
    # every cluster bootstrap replicate retains r={1,2}.
    for city, base in [("A", 10), ("B", 20)]:
        for cluster in range(4):
            rows.append(
                {
                    "city": city,
                    "person_id": f"{city}-{cluster}-1",
                    "r": 1,
                    "t_minutes": base + cluster,
                    "weight": 1.0,
                    "cluster": f"{city}-{cluster}",
                    "stratum": "S",
                }
            )
            rows.append(
                {
                    "city": city,
                    "person_id": f"{city}-{cluster}-2",
                    "r": 2,
                    "t_minutes": base + 10 + cluster,
                    "weight": 1.0,
                    "cluster": f"{city}-{cluster}",
                    "stratum": "S",
                }
            )
    return pd.DataFrame(rows)


def test_cluster_resampling_keeps_cluster_blocks():
    df = _person_days().query("city == 'A'")
    design = SurveyDesign(cluster_col="cluster", stratum_col="stratum")
    import numpy as np

    out = resample_clusters(df, design=design, rng=np.random.default_rng(7))
    # Same number of clusters drawn as observed; each selected block has 2 rows.
    assert len(out) == len(df)
    assert "__bootstrap_block" in out.columns
    assert (out.groupby("__bootstrap_block").size() == 2).all()


def test_joint_bootstrap_produces_pairwise_delta_intervals():
    df = _person_days()
    designs = {
        "A": SurveyDesign("cluster", "stratum"),
        "B": SurveyDesign("cluster", "stratum"),
    }
    point, draws, diag = joint_bootstrap_deltas(
        df,
        support=[1, 2],
        designs=designs,
        n_boot=30,
        seed=123,
        reference_mode="joint",
    )
    assert diag.successful_replicates == 30
    assert diag.failed_replicates == 0
    assert {"ci_lower", "ci_upper", "boot_n"}.issubset(point.columns)
    assert point["boot_n"].eq(30).all()
    assert draws["replicate"].nunique() == 30
    # B always needs 10 more minutes than A at the same participation in this fixture.
    assert point["delta"].eq(-10.0).all()


def test_fixed_reference_mode_is_available_only_as_explicit_diagnostic():
    df = _person_days()
    designs = {
        "A": SurveyDesign("cluster", "stratum"),
        "B": SurveyDesign("cluster", "stratum"),
    }
    _, _, diag = joint_bootstrap_deltas(
        df,
        support=[1, 2],
        designs=designs,
        n_boot=10,
        seed=321,
        reference_mode="fixed",
    )
    assert diag.reference_mode == "fixed"
