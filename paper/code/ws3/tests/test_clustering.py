"""WS3 step 3 tests: the pure seams of the RQ1 clustering pipeline.

Minimal per the PRE-REG — the population filter (string is_canonical + slop exclusion +
analyze_error drop), the confound-gate statistic (Cramer's V), the cluster-naming rule
(most-deviant standardized median), nearest-centroid assignment, and the D2 stratified
sampler's exact-size / determinism guarantees. No full pipeline run (that is the driver).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from clustering import (  # noqa: E402
    cluster_deviant_features,
    cramers_v,
    nearest_centroid_labels,
    numeric_feature_columns,
    organic_canonical,
    stratified_sample_idx,
)


def _tiny_df():
    # is_canonical is a STRING column ("true"/"false"). Row c is canonical slop with an
    # analyze_error (must drop); row g is canonical slop (must drop — RQ1 excludes slop);
    # rows e/f are non-canonical (RQ2 extras — drop).
    return pd.DataFrame(
        {
            "skill_id": ["a", "b", "c", "d", "e", "f", "g"],
            "source": [
                "skill_diffs",      # a: canonical organic -> KEEP
                "graph_of_skills",  # b: canonical organic -> KEEP
                "skill_diffs",      # c: canonical organic but analyze_error -> DROP
                "skill_diffs",      # d: canonical organic -> KEEP
                "skill_diffs",      # e: NON-canonical -> DROP (RQ2 extra)
                "slop_stub",        # f: NON-canonical slop -> DROP
                "slop_stub",        # g: canonical slop -> DROP (RQ1 excludes slop)
            ],
            "platform": ["p"] * 7,
            "near_dup_cluster_id": [str(i) for i in range(7)],
            "is_canonical": ["true", "true", "true", "true", "false", "false", "true"],
            "installs": [None] * 7,
            "analyze_error": [None, None, "TypeError: boom", None, None, None, None],
            "frontmatter_json": ["{}"] * 7,
            "dict_plain_replacements_json": ["[]"] * 7,
            "desc_tokens": [10, 20, 30, 40, 50, 60, 70],
            "dict_imperative_ratio": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7],
        }
    )


def test_organic_canonical_filters():
    keep = organic_canonical(_tiny_df())
    assert set(keep["skill_id"]) == {"a", "b", "d"}
    assert (keep["source"] != "slop_stub").all()
    assert keep["analyze_error"].isnull().all()


def test_numeric_feature_columns_excludes_carry():
    feats = numeric_feature_columns(_tiny_df())
    assert set(feats) == {"desc_tokens", "dict_imperative_ratio"}
    for carry in ("skill_id", "source", "is_canonical", "installs", "analyze_error"):
        assert carry not in feats


def test_cramers_v_perfect_association_is_one():
    # cluster maps 1:1 onto platform -> V ~ 1 (the "merely platform-driven" case).
    a = pd.Series([0, 0, 0, 1, 1, 1] * 20)
    b = pd.Series(["x", "x", "x", "y", "y", "y"] * 20)
    v, tab = cramers_v(a, b)
    assert v > 0.95
    assert tab.shape == (2, 2)


def test_cramers_v_independent_is_low():
    rng = np.random.default_rng(0)
    a = pd.Series(rng.integers(0, 3, size=3000))
    b = pd.Series(rng.integers(0, 3, size=3000))
    v, _ = cramers_v(a, b)
    assert v < 0.1


def test_cramers_v_drops_nulls_pairwise():
    a = pd.Series([0, 0, 1, 1, None])
    b = pd.Series(["x", "x", "y", "y", "z"])
    v, tab = cramers_v(a, b)
    # the null row is dropped; z column disappears -> 2x2 perfect table
    assert tab.shape == (2, 2)
    assert v > 0.95


def test_cluster_deviant_features_ranks_by_abs_median():
    z = pd.Series({"f_hi": 2.5, "f_neg": -1.8, "f_zero": 0.0, "f_small": 0.3})
    named = cluster_deviant_features(z, top_k=2)
    assert [f for f, _ in named] == ["f_hi", "f_neg"]
    assert named[0][1] == 2.5 and named[1][1] == -1.8  # signs preserved


def test_nearest_centroid_assignment():
    centroids = np.array([[0.0, 0.0], [10.0, 10.0]])
    pts = np.array([[0.1, 0.0], [9.5, 10.2], [0.0, -0.2]])
    labels, dist = nearest_centroid_labels(pts, centroids)
    assert list(labels) == [0, 1, 0]
    assert dist[0] < 1.0 and dist[1] < 1.0


def test_stratified_sample_exact_size_and_deterministic():
    # 3 platforms, imbalanced; sampler must hit exactly `size` and be seed-stable.
    platform = pd.Series(["a"] * 700 + ["b"] * 200 + [None] * 100)
    idx1 = stratified_sample_idx(platform, 200)
    idx2 = stratified_sample_idx(platform, 200)
    assert len(idx1) == 200
    assert np.array_equal(idx1, idx2)  # deterministic under seed 42
    # proportional-ish: platform "a" (70%) dominates the sample
    picked = platform.fillna("null").to_numpy()[idx1]
    assert (picked == "a").sum() >= (picked == "b").sum()
