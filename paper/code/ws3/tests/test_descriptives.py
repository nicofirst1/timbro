"""WS3 step 2 tests: class-split logic (string is_canonical + source -> label) and a
smoke on the CV AUC harness with synthetic separable data. Minimal per the PRE-REG."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
from descriptives import (  # noqa: E402
    cv_auc,
    numeric_feature_columns,
    split_classes,
)


def _tiny_df():
    # is_canonical is a STRING column ("true"/"false") — the whole point of the filter.
    # One canonical slop row carries an analyze_error and must be dropped.
    return pd.DataFrame(
        {
            "skill_id": ["a", "b", "c", "d", "e", "f"],
            "source": [
                "slop_stub",       # a: canonical slop -> keep, y=1
                "skill_diffs",     # b: canonical organic -> keep, y=0
                "slop_stub",       # c: canonical slop but analyze_error -> DROP
                "graph_of_skills", # d: canonical organic -> keep, y=0
                "skill_diffs",     # e: NON-canonical -> drop (RQ2 extra)
                "slop_stub",       # f: NON-canonical -> drop
            ],
            "platform": ["p"] * 6,
            "near_dup_cluster_id": ["0", "1", "2", "3", "4", "5"],
            "is_canonical": ["true", "true", "true", "true", "false", "false"],
            "installs": [None, None, None, None, "10", "20"],
            "analyze_error": [None, None, "TypeError: boom", None, None, None],
            "frontmatter_json": ["{}"] * 6,
            "dict_plain_replacements_json": ["[]"] * 6,
            "desc_tokens": [10, 20, 30, 40, 50, 60],
            "dict_imperative_ratio": [0.1, 0.2, 0.3, 0.4, 0.5, 0.6],
        }
    )


def test_split_classes_string_canonical_and_error_drop():
    df = _tiny_df()
    canonical, y = split_classes(df)
    # Kept: a (slop), b (organic), d (organic). Dropped: c (error), e/f (non-canonical).
    assert set(canonical["skill_id"]) == {"a", "b", "d"}
    # Label: slop_stub -> 1, organic -> 0.
    label = dict(zip(canonical["skill_id"], y))
    assert label == {"a": 1, "b": 0, "d": 0}


def test_numeric_feature_columns_excludes_carry_and_json():
    df = _tiny_df()
    feats = numeric_feature_columns(df)
    # Only the two numeric feature columns; carry/JSON/string columns excluded.
    assert set(feats) == {"desc_tokens", "dict_imperative_ratio"}
    assert "is_canonical" not in feats
    assert "frontmatter_json" not in feats
    assert "installs" not in feats


def test_cv_auc_smoke_on_separable_data():
    # Two well-separated Gaussian blobs -> AUC should be near 1; harness must return
    # (mean, sd, per_fold) with N_FOLDS fold scores, deterministically (seed 42).
    rng = np.random.default_rng(0)
    n = 200
    X_pos = rng.normal(loc=3.0, scale=1.0, size=(n, 4))
    X_neg = rng.normal(loc=-3.0, scale=1.0, size=(n, 4))
    X = np.vstack([X_pos, X_neg])
    y = np.array([1] * n + [0] * n)
    mean, sd, folds = cv_auc(X, y)
    assert len(folds) == 5
    assert 0.0 <= mean <= 1.0
    assert mean > 0.95  # clearly separable
    # Determinism: same seed -> identical result.
    mean2, _, _ = cv_auc(X, y)
    assert mean == mean2
