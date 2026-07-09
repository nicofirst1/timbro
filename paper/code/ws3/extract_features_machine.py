"""WS3 machine-cell feature extraction (ADR-0009 exploratory prep, not RQ1/2/4).

Reads the standalone `paper/data/src_machine_cell.parquet` table (587 rows, the
machine-authored SKILL.md cell — never merged into corpus.parquet, ADR-0009) and
runs `timbro.analyze.analyze_text` on every row, reusing `extract_features.py`'s
per-doc analyze + table-building seams (no logic duplication). Writes a flat
`paper/data/features_machine.parquet` + a manifest via the WS1 provenance
conventions.

Not a hypothesis test: descriptive prep only (see paper/code/ws3/LEDGER.md
PRE-REG — WS3 machine-cell feature extraction).

Scope: ALL 587 rows — the cell is standalone, so no canonical/install filter
applies (unlike step 1's corpus.parquet scope rule).

Run (from repo root):
  uv run --with-requirements paper/code/ws1/requirements.txt \
      python paper/code/ws3/extract_features_machine.py
"""
from __future__ import annotations

import multiprocessing as mp
import os
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

# WS1 provenance helpers (data_dir, write_manifest, sha256, git, versions).
sys.path.append(str(Path(__file__).resolve().parents[1] / "ws1"))
from _manifest import data_dir, sha256_file, write_manifest  # noqa: E402

# Reuse extract_features.py's analyze/table-building machinery (no duplication).
from extract_features import (  # noqa: E402
    _analyze_one,
    _feature_keys,
    _worker_init,
)

CARRY_COLUMNS = ["skill_id", "source", "generator_model", "domain", "task_family"]
TEXT_COLUMN = "text"

INPUT_NAME = "src_machine_cell.parquet"
OUTPUT_NAME = "features_machine.parquet"
EXPECTED_N = 587


def _rows_to_table(results, feature_keys) -> pa.Table:
    """Assemble results into a flat Arrow table (machine-cell carry columns)."""
    cols = {c: [] for c in CARRY_COLUMNS}
    for k in feature_keys:
        cols[k] = []
    cols["analyze_error"] = []

    for _idx, carry, feats, err in results:
        for c in CARRY_COLUMNS:
            cols[c].append(carry[c])
        if feats is None:
            for k in feature_keys:
                cols[k].append(None)
        else:
            for k in feature_keys:
                cols[k].append(feats.get(k))
        cols["analyze_error"].append(err)

    order = CARRY_COLUMNS + feature_keys + ["analyze_error"]
    arrays = {c: cols[c] for c in order}
    arrays["analyze_error"] = pa.array(arrays["analyze_error"], type=pa.string())
    return pa.table(arrays)


def main() -> int:
    ddir = data_dir()
    input_path = ddir / INPUT_NAME
    out_path = ddir / OUTPUT_NAME

    print(f"[ws3:extract_machine] reading {input_path}", flush=True)
    table = pq.read_table(input_path, columns=CARRY_COLUMNS + [TEXT_COLUMN])

    n_rows = table.num_rows
    print(f"[ws3:extract_machine] scope: all rows, n={n_rows}", flush=True)
    assert n_rows == EXPECTED_N, (
        f"row count {n_rows} != {EXPECTED_N} (machine-cell drift — STOP, consult user)"
    )

    carry_cols = {c: table.column(c).to_pylist() for c in CARRY_COLUMNS}
    texts = table.column(TEXT_COLUMN).to_pylist()

    feature_keys = _feature_keys()

    n_workers = max(1, (os.cpu_count() or 1) - 3)
    args = [
        (i, {c: carry_cols[c][i] for c in CARRY_COLUMNS}, texts[i])
        for i in range(n_rows)
    ]
    print(
        f"[ws3:extract_machine] {n_rows} docs, {n_workers} workers",
        flush=True,
    )

    ctx = mp.get_context("spawn")  # clean worker init; avoid fork+spaCy footguns
    with ctx.Pool(processes=n_workers, initializer=_worker_init) as pool:
        results = pool.map(_analyze_one, args, chunksize=25)

    features = _rows_to_table(results, feature_keys)
    pq.write_table(features, out_path)

    n_out = features.num_rows
    failures_final = pc.sum(
        pc.cast(pc.is_valid(features.column("analyze_error")), pa.int64())
    ).as_py()
    fail_rate = failures_final / n_out if n_out else 0.0
    print(
        f"[ws3:extract_machine] DONE rows {n_out}, failures {failures_final} "
        f"({fail_rate:.4%})",
        flush=True,
    )

    write_manifest(
        out_path,
        source="features_machine",
        inputs=[
            {"file": INPUT_NAME, "sha256": sha256_file(input_path)},
        ],
        n_rows=n_out,
        packages=("spacy", "en_core_web_sm", "pyarrow", "textdescriptives"),
        extra={
            "scope_rule": "ALL rows (standalone table, ADR-0009 — no canonical filter)",
            "n_analyze_failures": failures_final,
            "analyze_failure_rate": fail_rate,
            "n_feature_keys": len(feature_keys),
        },
    )
    print("[ws3:extract_machine] manifest written under paper/code/ws1/manifests/", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
