"""WS3 step 5 prep tests: RQ4 chain-eligibility scope seam (n_versions >= 3,
ADR-0005). Kept minimal per the WS3 pre-reg."""
from __future__ import annotations

import sys
from pathlib import Path

import pyarrow as pa

sys.path.append(str(Path(__file__).resolve().parents[1]))
from extract_features_chains import CARRY_COLUMNS, select_scope  # noqa: E402


def _tiny_chains_table():
    # Chains of length 1/2/3/4: skill_id repeated n_versions times, n_versions
    # constant within each chain (mirrors the real table's invariant).
    return pa.table(
        {
            "skill_id": [
                "len1",
                "len2", "len2",
                "len3", "len3", "len3",
                "len4", "len4", "len4", "len4",
            ],
            "version_index": [0, 0, 1, 0, 1, 2, 0, 1, 2, 3],
            "commit_date": ["2026-01-01"] * 10,
            "after_sha": [f"sha{i}" for i in range(10)],
            "n_versions": [1, 2, 2, 3, 3, 3, 4, 4, 4, 4],
            "skill_cluster_id": ["c"] * 10,
            "is_canonical": [True] * 10,
            "repo": ["r"] * 10,
            "text": ["t"] * 10,
        }
    )


def test_only_chains_length_3_or_more_selected():
    t = _tiny_chains_table()
    mask = select_scope(t)
    selected_ids = set(t.filter(mask).column("skill_id").to_pylist())

    # Only len3 (3 rows) and len4 (4 rows) chains are RQ4-eligible.
    assert selected_ids == {"len3", "len4"}
    assert t.filter(mask).num_rows == 7


def test_len1_and_len2_chains_excluded():
    t = _tiny_chains_table()
    mask = select_scope(t)
    selected_ids = set(t.filter(mask).column("skill_id").to_pylist())

    assert "len1" not in selected_ids
    assert "len2" not in selected_ids


def test_carry_columns_present_in_table():
    t = _tiny_chains_table()
    for c in CARRY_COLUMNS:
        assert c in t.column_names
