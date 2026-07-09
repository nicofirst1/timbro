"""WS3 step-3 robustness cut — the one new reusable seam.

Only `recluster_population` is new (everything else reuses `clustering.py` /
`step3_machine_projection.py` seams already tested). Verify it composes the step-3
pipeline end-to-end on a small synthetic population: the D2 gate branch (population
<= 100K -> full-population basis, no 50K sample), zero-variance drop, and that it returns
a coherent partition (every row assigned, cluster ids consistent) with the top-5 axis
table. Two well-separated blobs -> HDBSCAN should find structure (no fallback needed),
which also exercises the non-fallback path.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from step3_robustness import _name_axis, recluster_population  # noqa: E402


def _blob_population(n_per: int = 400, n_feats: int = 12, seed: int = 0) -> pd.DataFrame:
    """Three well-separated Gaussian blobs + one constant (zero-variance) column.

    Three (not two) so HDBSCAN clears the D3 ``< 3 clusters -> fallback`` trigger and the
    non-fallback path is exercised.
    """
    rng = np.random.default_rng(seed)
    a = rng.normal(0.0, 0.3, size=(n_per, n_feats))
    b = rng.normal(8.0, 0.3, size=(n_per, n_feats))
    c = rng.normal(-8.0, 0.3, size=(n_per, n_feats))
    X = np.vstack([a, b, c])
    cols = {f"feat_{i}": X[:, i] for i in range(n_feats)}
    cols["zero_var"] = np.zeros(3 * n_per)  # must be dropped before PCA
    df = pd.DataFrame(cols)
    # carry columns the seam's numeric_feature_columns must ignore
    df["skill_id"] = [f"s{i}" for i in range(len(df))]
    df["source"] = "skill_diffs"
    df["platform"] = (
        (["claude_skill"] * n_per) + (["opencode_skill"] * n_per) + (["openclaw_skill"] * n_per)
    )
    df["near_dup_cluster_id"] = df["skill_id"]
    df["is_canonical"] = "true"
    df["installs"] = None
    df["analyze_error"] = None
    df["frontmatter_json"] = "{}"
    df["dict_plain_replacements_json"] = "[]"
    return df


def test_recluster_population_small_pop_no_d2_and_partitions():
    pop = _blob_population()
    R = recluster_population(pop)

    # small population -> D2 does not fire (full population is the discovery basis)
    assert R["d2_fires"] is False
    assert len(R["sample_idx"]) == len(pop)

    # zero-variance column dropped before PCA; carry columns never in features
    assert "zero_var" in R["dropped_zero_var"]
    assert "skill_id" not in R["feats"]
    assert "platform" not in R["feats"]

    # every row assigned to a real cluster id; assignment length matches population
    assert len(R["full_cluster"]) == len(pop)
    assert set(R["full_cluster"]).issubset(set(R["cluster_ids"]))

    # PCA retained a sensible component count and hit the >=0.90 variance target
    assert 1 <= R["n_comp"] <= len(R["feats"])
    assert R["cum_var"] >= 0.90 - 1e-9

    # three clearly separated blobs -> HDBSCAN finds >=3 clusters, low noise, no fallback
    assert R["hdbscan_prefallback"]["n_clusters"] >= 3
    assert R["hdbscan_prefallback"]["noise_fraction"] < 0.5
    assert R["method"] == "hdbscan"

    # top-5 axis table: up to 5 axes, each 8 loadings
    assert 1 <= len(R["top5_axes"]) <= 5
    assert all(len(ax) == 8 for ax in R["top5_axes"])


def test_name_axis_reads_dominant_family():
    # structure-dominated loadings -> the label names the structure family first
    loadings = [
        ("struct_line_count", 0.6),
        ("struct_heading_count", 0.5),
        ("read_flesch_kincaid_grade", 0.2),
        ("desc_tokens", 0.1),
    ]
    name = _name_axis(loadings)
    assert "structure/formatting" in name
