"""WS3 step 1 tests: scope filter (string is_canonical + installs union) and an
analyze_text feature-key smoke. Kept minimal per the WS3 pre-reg."""
from __future__ import annotations

import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc

sys.path.append(str(Path(__file__).resolve().parents[1]))
from extract_features import CARRY_COLUMNS, select_scope  # noqa: E402


def _tiny_table():
    # is_canonical is a STRING column with literal "true"/"false" — the whole point.
    return pa.table(
        {
            "skill_id": ["a", "b", "c", "d", "e"],
            "source": ["s"] * 5,
            "platform": ["p"] * 5,
            "near_dup_cluster_id": ["0", "1", "2", "3", "4"],
            "is_canonical": ["true", "false", "false", "true", "false"],
            "installs": [None, "123", "", "45", None],
            "text": ["t"] * 5,
        }
    )


def _mask_ids(table, mask):
    filtered = table.filter(mask)
    return set(filtered.column("skill_id").to_pylist())


def test_scope_string_true_false_and_installs_union():
    t = _tiny_table()
    canonical, labeled = select_scope(t)
    union = pc.or_(canonical, labeled)

    # canonical is the literal string "true", NOT truthiness of "false".
    assert _mask_ids(t, canonical) == {"a", "d"}
    # labeled = installs valid AND non-empty ("" and None both excluded).
    assert _mask_ids(t, labeled) == {"b", "d"}
    # union: canonical OR labeled -> a (canon), b (labeled-only), d (both).
    assert _mask_ids(t, union) == {"a", "b", "d"}
    # empty-string installs ("c") and null-installs non-canonical ("e") are dropped.
    assert "c" not in _mask_ids(t, union)
    assert "e" not in _mask_ids(t, union)


def test_labeled_only_excludes_canonical():
    t = _tiny_table()
    canonical, labeled = select_scope(t)
    labeled_only = pc.and_(labeled, pc.invert(canonical))
    # d is labeled but canonical -> only b is labeled-only.
    assert _mask_ids(t, labeled_only) == {"b"}


def test_carry_columns_present_in_table():
    t = _tiny_table()
    for c in CARRY_COLUMNS:
        assert c in t.column_names


def test_analyze_text_smoke_feature_keys():
    from timbro.analyze import analyze_text

    doc = (
        "---\nname: demo-skill\ndescription: Use this when you need a demo.\n---\n"
        "# Heading\n\nThis is a short document. It has a couple of sentences.\n"
        "Always be careful here.\n\n- item one\n- item two\n"
    )
    feats = analyze_text(doc)
    # A representative slice from each feature family must be present.
    for key in (
        "desc_tokens",
        "read_flesch_reading_ease",
        "syn_mean_dependency_distance",
        "struct_heading_count",
        "dict_imperative_ratio",
        "lex_mtld",
        "posdep_pos_NOUN",
        "coh_first_order_coherence",
        "frontmatter_json",
    ):
        assert key in feats, f"missing feature key: {key}"
    # analyze_text returns no `path` key (that's analyze_file's job).
    assert "path" not in feats
