"""Pure-logic tests for dedup.py's clustering core.

Seam under test: assign_clusters(rows: list[dict]) -> list[dict]. Takes rows shaped
like {"skill_id", "source", "text", "n_revisions"} (a pooled subset of the 3 src_*
parquets) and returns one row per skill_id: {"skill_id", "near_dup_cluster_id",
"cluster_size", "is_canonical"}. No parquet/disk I/O — tiny synthetic fixtures only,
so this suite runs in well under a second and does not require paper/data/ to exist.

Expected values below are hand-computed, not asserted against the code's own output:
- 5-gram shingling: "a b c d e f" -> shingles {"a b c d e", "b c d e f"} (two 5-token
  windows over 6 tokens). Two docs sharing >=90% of shingles collapse; 0% overlap does
  not.
- MinHash/LSH is probabilistic in principle but deterministic for a fixed seed
  (num_perm=128, seed=42) and these fixtures are chosen with clear separation (either
  near-total shingle overlap or zero overlap) so the pass/fail is not flaky.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from dedup import assign_clusters, normalize_text, shingles  # noqa: E402

OUT_COLS = {"skill_id", "near_dup_cluster_id", "cluster_size", "is_canonical"}


def _by_id(out_rows):
    return {r["skill_id"]: r for r in out_rows}


# ---- normalize_text ----------------------------------------------------------

def test_normalize_lowercases_collapses_whitespace_and_strips():
    assert normalize_text("  Hello   World\n\nFoo\t\tBar  ") == "hello world foo bar"


def test_normalize_none_and_empty_become_empty_string():
    assert normalize_text(None) == ""
    assert normalize_text("") == ""
    assert normalize_text("   \n\t  ") == ""


# ---- shingles ------------------------------------------------------------------

def test_shingles_are_5_consecutive_token_windows():
    # "a b c d e f" -> 6 tokens -> 2 overlapping 5-grams.
    assert shingles("a b c d e f") == {"a b c d e", "b c d e f"}


def test_shingles_short_doc_is_single_whole_text_shingle():
    # Fewer than 5 tokens -> one shingle: the whole normalized text.
    assert shingles("a b c") == {"a b c"}


# ---- assign_clusters: exact dedup ------------------------------------------

def test_byte_identical_docs_collapse_to_one_exact_class_one_canonical():
    rows = [
        {"skill_id": "sd:1", "source": "skill_diffs", "text": "Same text here please", "n_revisions": "1"},
        {"skill_id": "sd:2", "source": "skill_diffs", "text": "Same text here please", "n_revisions": "1"},
    ]
    out = _by_id(assign_clusters(rows))
    assert out["sd:1"]["near_dup_cluster_id"] == out["sd:2"]["near_dup_cluster_id"]
    assert out["sd:1"]["cluster_size"] == "2"
    assert out["sd:2"]["cluster_size"] == "2"
    canon = [r for r in out.values() if r["is_canonical"] == "true"]
    assert len(canon) == 1


def test_docs_identical_after_normalization_collapse():
    # Same text modulo case + whitespace runs -> same exact class -> same cluster.
    rows = [
        {"skill_id": "sd:1", "source": "skill_diffs", "text": "Hello   World  Foo Bar Baz", "n_revisions": "1"},
        {"skill_id": "sd:2", "source": "skill_diffs", "text": "hello world foo bar baz", "n_revisions": "1"},
    ]
    out = _by_id(assign_clusters(rows))
    assert out["sd:1"]["near_dup_cluster_id"] == out["sd:2"]["near_dup_cluster_id"]
    assert out["sd:1"]["cluster_size"] == "2"


def test_empty_and_null_text_group_as_one_exact_class_but_are_counted():
    rows = [
        {"skill_id": "sd:1", "source": "skill_diffs", "text": "", "n_revisions": "0"},
        {"skill_id": "sd:2", "source": "skill_diffs", "text": None, "n_revisions": "0"},
        {"skill_id": "sd:3", "source": "skill_diffs", "text": "   ", "n_revisions": "0"},
    ]
    out = _by_id(assign_clusters(rows))
    cids = {out[i]["near_dup_cluster_id"] for i in ("sd:1", "sd:2", "sd:3")}
    assert len(cids) == 1
    assert out["sd:1"]["cluster_size"] == "3"
    assert len(out) == 3  # all three counted as rows, not dropped


# ---- assign_clusters: near-dup via MinHash ---------------------------------
#
# Jaccard math for word-5-gram shingles on N distinct tokens (N-4 shingles):
# changing the last k tail tokens flips exactly k shingles (the k windows ending
# at the tail), so shared = (N-4)-k, union = (N-4)+k, Jaccard = (N-4-k)/(N-4+k).
# The threshold is 0.9 on the MinHash Jaccard *estimate* (post-filtered, not LSH
# banding alone), so fixtures are chosen with a clear margin either side of 0.9:
#   N=45 (41 shingles), k=1 -> 40/42 = 0.952  (>= 0.9: MUST cluster)
#   N=45 (41 shingles), k=5 -> 36/46 = 0.783  (<  0.9: MUST stay separate)

# Base doc: 45 distinct tokens -> 41 five-gram shingles.
_BASE_TOKENS = [f"tok{i}" for i in range(45)]
_BASE_TEXT = " ".join(_BASE_TOKENS)


def _near_dup_text(n_changed_tail_tokens):
    """Return _BASE_TEXT with the last n tokens replaced by unique alt tokens."""
    toks = list(_BASE_TOKENS)
    for i in range(len(toks) - n_changed_tail_tokens, len(toks)):
        toks[i] = f"alt{i}"
    return " ".join(toks)


def test_above_threshold_docs_land_in_same_near_dup_cluster():
    # 1 changed tail token -> Jaccard 40/42 = 0.952 >= 0.9 -> same cluster.
    rows = [
        {"skill_id": "sd:1", "source": "skill_diffs", "text": _BASE_TEXT, "n_revisions": "1"},
        {"skill_id": "sd:2", "source": "skill_diffs", "text": _near_dup_text(1), "n_revisions": "1"},
    ]
    out = _by_id(assign_clusters(rows))
    assert out["sd:1"]["near_dup_cluster_id"] == out["sd:2"]["near_dup_cluster_id"]
    assert out["sd:1"]["cluster_size"] == "2"


def test_below_threshold_docs_stay_in_separate_clusters():
    # 5 changed tail tokens -> Jaccard 36/46 = 0.783 < 0.9 -> the post-filter must
    # reject the LSH candidate pair and keep them apart. Guards the 0.9 boundary:
    # without the jaccard() >= 0.9 post-filter, raw LSH banding could merge these.
    rows = [
        {"skill_id": "sd:1", "source": "skill_diffs", "text": _BASE_TEXT, "n_revisions": "1"},
        {"skill_id": "sd:2", "source": "skill_diffs", "text": _near_dup_text(5), "n_revisions": "1"},
    ]
    out = _by_id(assign_clusters(rows))
    assert out["sd:1"]["near_dup_cluster_id"] != out["sd:2"]["near_dup_cluster_id"]
    assert out["sd:1"]["cluster_size"] == "1"
    assert out["sd:2"]["cluster_size"] == "1"


def test_clearly_different_docs_land_in_different_clusters():
    text_a = "alpha beta gamma delta epsilon zeta eta theta iota kappa"
    text_b = "lorem ipsum dolor sit amet consectetur adipiscing elit sed do"
    rows = [
        {"skill_id": "sd:1", "source": "skill_diffs", "text": text_a, "n_revisions": "1"},
        {"skill_id": "sd:2", "source": "skill_diffs", "text": text_b, "n_revisions": "1"},
    ]
    out = _by_id(assign_clusters(rows))
    assert out["sd:1"]["near_dup_cluster_id"] != out["sd:2"]["near_dup_cluster_id"]
    assert out["sd:1"]["cluster_size"] == "1"
    assert out["sd:2"]["cluster_size"] == "1"


# ---- canonical selection ----------------------------------------------------

def test_canonical_prefers_skill_diffs_over_slop_stub_for_identical_pair():
    rows = [
        {"skill_id": "slop:z", "source": "slop_stub", "text": "Identical body content here", "n_revisions": None},
        {"skill_id": "sd:a", "source": "skill_diffs", "text": "Identical body content here", "n_revisions": None},
    ]
    out = _by_id(assign_clusters(rows))
    assert out["sd:a"]["is_canonical"] == "true"
    assert out["slop:z"]["is_canonical"] == "false"


def test_canonical_tiebreak_by_n_revisions_then_skill_id():
    # Same source (skill_diffs) -> tiebreak on n_revisions (numeric, null->0), then skill_id.
    rows = [
        {"skill_id": "sd:b", "source": "skill_diffs", "text": "Tiebreak content sample", "n_revisions": "3"},
        {"skill_id": "sd:a", "source": "skill_diffs", "text": "Tiebreak content sample", "n_revisions": "7"},
        {"skill_id": "sd:c", "source": "skill_diffs", "text": "Tiebreak content sample", "n_revisions": "7"},
    ]
    out = _by_id(assign_clusters(rows))
    # sd:a and sd:c tie on n_revisions=7 (highest); smallest skill_id wins -> sd:a.
    assert out["sd:a"]["is_canonical"] == "true"
    assert out["sd:b"]["is_canonical"] == "false"
    assert out["sd:c"]["is_canonical"] == "false"


# ---- output shape ------------------------------------------------------------

def test_output_has_exactly_the_4_columns():
    rows = [
        {"skill_id": "sd:1", "source": "skill_diffs", "text": "Some content words here", "n_revisions": "1"},
    ]
    out = assign_clusters(rows)
    assert len(out) == 1
    assert set(out[0].keys()) == OUT_COLS


def test_singletons_get_their_own_cluster():
    rows = [
        {"skill_id": "sd:1", "source": "skill_diffs", "text": "unique content number one", "n_revisions": "1"},
        {"skill_id": "sd:2", "source": "skill_diffs", "text": "totally other content two", "n_revisions": "1"},
    ]
    out = _by_id(assign_clusters(rows))
    assert out["sd:1"]["near_dup_cluster_id"] != out["sd:2"]["near_dup_cluster_id"]
    assert out["sd:1"]["cluster_size"] == "1"
    assert out["sd:2"]["cluster_size"] == "1"
    assert out["sd:1"]["is_canonical"] == "true"
    assert out["sd:2"]["is_canonical"] == "true"
