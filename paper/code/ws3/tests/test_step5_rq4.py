"""WS3 step 5 (RQ4) tests: the pure seams that back the confirmatory H4a/H4b analysis.

Load-bearing seams: (1) ``is_true`` — ``is_canonical`` truthiness robust to the corpus
STRING/bool split (the ledger gotcha; this parquet ships bool); (2) the frozen RQ1
z-transform (fit on the RQ1 population, applied unchanged to chain rows so the reference
geometry cannot leak chain structure) and the nearest-centroid distance that IS zdist5;
(3) the within-chain OLS slope descriptive; (4) BH over the {H4a, H4b} family. A silent
break in any of these corrupts the population, the H4b construct, or the effect summary.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "step5_rq4"))
from step5_rq4 import (  # noqa: E402
    apply_ztransform,
    benjamini_hochberg,
    freeze_ztransform,
    is_true,
    nearest_centroid_distance,
    within_chain_slope,
)

FEATS = ["f1", "f2"]


def test_is_true_handles_bool_column():
    # features_chains.parquet ships is_canonical as genuine bool.
    s = pd.Series([True, False, True])
    assert is_true(s).tolist() == [True, False, True]


def test_is_true_handles_string_true_false():
    # the corpus-wide gotcha: STRING "true"/"false", not bool. Naive truthiness keeps all.
    s = pd.Series(["true", "false", "TRUE", "", None])
    assert is_true(s).tolist() == [True, False, True, False, False]


def test_freeze_and_apply_ztransform_are_frozen():
    # transform is FIT on the train frame and APPLIED unchanged — a new frame with a
    # different mean must be standardized by the TRAIN mean/sd, not its own.
    train = pd.DataFrame({"f1": [0.0, 2.0, 4.0], "f2": [10.0, 10.0, 10.0]})
    params = freeze_ztransform(train, FEATS)
    assert abs(params["f1"]["mean"] - 2.0) < 1e-9
    assert params["f2"]["sd"] == 0.0  # constant feature -> sd 0, z stays 0
    # a test row equal to the train mean maps to 0 on f1; constant f2 always 0.
    Z = apply_ztransform(pd.DataFrame({"f1": [2.0], "f2": [999.0]}), FEATS, params)
    assert abs(Z[0, 0]) < 1e-9
    assert Z[0, 1] == 0.0


def test_apply_ztransform_median_imputes_nan():
    train = pd.DataFrame({"f1": [1.0, 3.0], "f2": [0.0, 4.0]})
    params = freeze_ztransform(train, FEATS)
    # NaN in the applied frame is imputed with the TRAIN median (not dropped, not crash).
    Z = apply_ztransform(pd.DataFrame({"f1": [np.nan], "f2": [np.nan]}), FEATS, params)
    assert np.isfinite(Z).all()


def test_nearest_centroid_distance_picks_closest():
    centroids = np.array([[0.0, 0.0], [10.0, 10.0]])
    Z = np.array([[0.1, 0.0], [9.0, 10.0]])
    d = nearest_centroid_distance(Z, centroids)
    # row 0 nearest to centroid 0 (dist 0.1); row 1 nearest to centroid 1 (dist 1.0)
    assert abs(d[0] - 0.1) < 1e-9
    assert abs(d[1] - 1.0) < 1e-9


def test_within_chain_slope_direction_and_exact():
    v = np.array([0, 1, 2, 3])
    assert within_chain_slope(v, np.array([1.0, 2.0, 3.0, 4.0])) > 0
    assert within_chain_slope(v, np.array([5.0, 5.0, 5.0, 5.0])) == 0.0
    assert within_chain_slope(v, np.array([4.0, 3.0, 2.0, 1.0])) < 0
    assert within_chain_slope(v, 2.0 * v + 3.0) == 2.0  # y=2x+3 -> slope 2


def test_within_chain_slope_degenerate_returns_none():
    assert within_chain_slope(np.array([0]), np.array([1.0])) is None
    assert within_chain_slope(np.array([2, 2, 2]), np.array([1.0, 2.0, 3.0])) is None
    assert within_chain_slope(np.array([0, 1]), np.array([np.nan, 1.0])) is None


def test_benjamini_hochberg_over_two_family():
    # D6-style over {H4a, H4b}. Monotone step-up, order preserved, in [0,1].
    p = np.array([0.001, 0.20])
    adj = benjamini_hochberg(p, 0.10)
    assert adj.shape == (2,)
    assert np.all((adj >= 0) & (adj <= 1))
    order = np.argsort(p)
    assert np.all(np.diff(adj[order]) >= -1e-12)
    assert benjamini_hochberg(np.array([]), 0.10).size == 0
