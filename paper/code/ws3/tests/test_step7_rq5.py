"""Pure-seam unit tests for WS3 step 7 — RQ5 audience contrast (ADR-0008 D10)."""
import numpy as np
import pandas as pd
import pytest

import step7_rq5 as m


# --------------------------------------------------------------------- is_true (ledger gotcha)


def test_is_true_string_column_not_naive_truthiness():
    # features.parquet ships is_canonical as the STRING "true"/"false".
    s = pd.Series(["true", "false", "true", None])
    out = m.is_true(s)
    assert out.tolist() == [True, False, True, False]


def test_is_true_bool_column():
    s = pd.Series([True, False, True])
    assert m.is_true(s).tolist() == [True, False, True]


# --------------------------------------------------------------------- BH (D6)


def test_benjamini_hochberg_monotone_and_bounded():
    p = np.array([0.001, 0.04, 0.03, 0.5, 0.2])
    adj = m.benjamini_hochberg(p, 0.10)
    assert adj.shape == p.shape
    assert np.all((adj >= 0) & (adj <= 1))
    # smallest raw p gets the smallest adjusted p
    assert np.argmin(adj) == np.argmin(p)


def test_benjamini_hochberg_all_null():
    p = np.array([0.9, 0.8, 0.95])
    adj = m.benjamini_hochberg(p, 0.10)
    assert np.all(adj > 0.10)


# --------------------------------------------------------------------- dedup_cell_canonical (D1)


def test_dedup_cell_canonical_collapses_exact_duplicates():
    # Two exact-duplicate docs collapse to one canonical (smallest doc_id kept).
    df = pd.DataFrame({
        "doc_id": ["d2", "d1", "d3"],
        "text": ["the quick brown fox jumps over", "the quick brown fox jumps over",
                 "an entirely different sentence about cats and dogs running"],
    })
    canon = m.dedup_cell_canonical(df)
    # d1/d2 are exact dups -> one survives (smallest id d1); d3 is distinct -> survives.
    assert canon == {"d1", "d3"}


def test_dedup_cell_canonical_keeps_distinct_docs():
    df = pd.DataFrame({
        "doc_id": ["a", "b"],
        "text": ["completely unrelated alpha text about mountains",
                 "totally separate beta text concerning oceans"],
    })
    assert m.dedup_cell_canonical(df) == {"a", "b"}


# --------------------------------------------------------------------- median_impute


def test_median_impute_fills_nans_and_counts():
    df = pd.DataFrame({"f1": [1.0, 2.0, np.nan, 4.0], "f2": [10.0, np.nan, np.nan, 40.0]})
    out, n_imp = m.median_impute(df, ["f1", "f2"])
    assert n_imp == {"f1": 1, "f2": 2}
    assert not out[["f1", "f2"]].isna().any().any()
    # f1 median over [1,2,4] = 2.0 fills the NaN
    assert out["f1"].tolist() == [1.0, 2.0, 2.0, 4.0]


def test_median_impute_no_rows_dropped():
    df = pd.DataFrame({"f1": [1.0, np.nan, 3.0]})
    out, _ = m.median_impute(df, ["f1"])
    assert len(out) == len(df)


# --------------------------------------------------------------------- cohens_d


def test_cohens_d_sign_and_zero():
    # mean(a) > mean(b) -> positive d.
    a = np.array([2.0, 3.0, 4.0, 3.0])
    b = np.array([0.0, 1.0, 2.0, 1.0])
    d, lo, hi = m.cohens_d(a, b)
    assert d > 0
    assert lo < d < hi
    # identical distributions -> d ~ 0.
    d0, _, _ = m.cohens_d(a, a.copy())
    assert abs(d0) < 1e-9


def test_cohens_d_degenerate_pooled_sd():
    # zero within-group variance in both -> pooled SD 0 -> guarded 0.0.
    a = np.array([5.0, 5.0, 5.0])
    b = np.array([3.0, 3.0, 3.0])
    d, lo, hi = m.cohens_d(a, b)
    assert (d, lo, hi) == (0.0, 0.0, 0.0)


# --------------------------------------------------------------------- fit_feature (integration seam)


def test_fit_feature_c2_reference_gives_all_contrasts():
    rng = np.random.default_rng(42)
    n = 200
    # three cells with a genuine C3 offset on the feature.
    frames = []
    for cell, offset in ((m.CELL_C1, 0.0), (m.CELL_C2, 0.2), (m.CELL_C3, 1.0)):
        frames.append(pd.DataFrame({
            "cell": cell,
            "dict_imperative_ratio": offset + rng.normal(0, 1, n),
            "log_tokens": rng.normal(5, 1, n),
        }))
    frame = pd.concat(frames, ignore_index=True)
    r = m.fit_feature(frame, "dict_imperative_ratio")
    # all three contrasts present with coef/CI/p/d.
    for key in ("c3_vs_c2", "c3_vs_c1", "c2_vs_c1"):
        for field in ("coef", "ci_low", "ci_high", "p_raw", "d", "d_lo", "d_hi"):
            assert field in r[key]
    # C3 is well above both human cells -> positive C3-C2 and C3-C1 coefficients.
    assert r["c3_vs_c2"]["coef"] > 0
    assert r["c3_vs_c1"]["coef"] > 0
    assert r["n"] == 3 * n


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
