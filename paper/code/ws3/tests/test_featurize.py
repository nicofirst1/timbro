"""Pure-logic tests for featurize_rows — no parquet, no spaCy, sub-second.

A fake analyze() lets us assert the canonical filter, metadata carry-forward, and
feature overlay without loading timbro.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from featurize import featurize_rows  # noqa: E402


def _fake_analyze(text):
    return {"desc_tokens": len(text.split()), "frontmatter_json": "{}"}


def test_drops_non_canonical():
    rows = [
        {"skill_id": "a", "text": "one two", "is_canonical": True},
        {"skill_id": "b", "text": "x", "is_canonical": False},
    ]
    out = featurize_rows(rows, analyze=_fake_analyze)
    assert [r["skill_id"] for r in out] == ["a"]


def test_carries_metadata_and_overlays_features():
    rows = [{
        "skill_id": "a", "text": "one two three", "is_canonical": True,
        "platform": "claude", "installs": 42, "frontmatter_json": "from-corpus",
        "near_dup_cluster_id": 7,
    }]
    (row,) = featurize_rows(rows, analyze=_fake_analyze)
    assert row["platform"] == "claude"          # confound column carried
    assert row["installs"] == 42                # RQ2 outcome carried
    assert row["desc_tokens"] == 3              # feature computed
    assert row["frontmatter_json"] == "{}"      # analyze() wins the collision
    assert "text" not in row                    # source text dropped
    assert "near_dup_cluster_id" not in row     # dedup bookkeeping dropped


def test_missing_is_canonical_defaults_true():
    out = featurize_rows([{"skill_id": "a", "text": "hi"}], analyze=_fake_analyze)
    assert len(out) == 1
