"""WS3 step 7 prep tests: the human-baseline extraction seam — ALL-rows scope
(no canonical/install filter, unlike step 1) and its carry columns. Kept minimal
per the WS3 pre-reg (extraction-only; dedup deferred to step 7's analysis)."""
from __future__ import annotations

import sys
from pathlib import Path

import pyarrow as pa

sys.path.append(str(Path(__file__).resolve().parents[1]))
from extract_features_human import (  # noqa: E402
    CARRY_COLUMNS,
    EXPECTED_N,
    TEXT_COLUMN,
    _rows_to_table,
)


def _tiny_table():
    return pa.table(
        {
            "doc_id": ["a", "b", "c"],
            "audience": ["human", "human", "human"],
            "era": ["pre", "post", "pre"],
            "repo": ["r1", "r2", "r3"],
            "source_detail": ["the-stack", "github", "the-stack"],
            "text": ["# README\n\nHello.\n"] * 3,
        }
    )


def test_scope_is_all_rows_no_canonical_filter():
    # Unlike extract_features.py's select_scope, this table has no is_canonical /
    # installs columns at all -- the human-baseline table is standalone and the
    # scope is unconditionally every row.
    t = _tiny_table()
    assert t.num_rows == 3
    assert "is_canonical" not in t.column_names
    assert "installs" not in t.column_names


def test_carry_columns_present_in_table():
    t = _tiny_table()
    for c in CARRY_COLUMNS:
        assert c in t.column_names
    assert TEXT_COLUMN in t.column_names


def test_carry_columns_exact_set():
    # Pins the exact carry-column contract from the LEDGER pre-reg.
    assert CARRY_COLUMNS == ["doc_id", "audience", "era", "repo", "source_detail"]


def test_expected_n_matches_manifest():
    # Pins the pre-registered N from human_baseline.parquet.manifest.json.
    assert EXPECTED_N == 20137


def test_rows_to_table_assembles_carry_and_feature_columns():
    feature_keys = ["desc_tokens", "read_flesch_reading_ease"]
    carry = {
        "doc_id": "a",
        "audience": "human",
        "era": "pre",
        "repo": "r1",
        "source_detail": "the-stack",
    }
    results = [
        (0, carry, {"desc_tokens": 5, "read_flesch_reading_ease": 80.0}, None),
        (1, {**carry, "doc_id": "b"}, None, "ValueError: boom"),
    ]
    table = _rows_to_table(results, feature_keys)

    assert table.num_rows == 2
    for c in CARRY_COLUMNS:
        assert c in table.column_names
    assert "desc_tokens" in table.column_names
    assert "analyze_error" in table.column_names

    doc_ids = table.column("doc_id").to_pylist()
    assert doc_ids == ["a", "b"]

    errors = table.column("analyze_error").to_pylist()
    assert errors == [None, "ValueError: boom"]

    tokens = table.column("desc_tokens").to_pylist()
    assert tokens == [5, None]
