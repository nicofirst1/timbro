"""WS3 step 5 prep — deterministic linguistic feature extraction over the RQ4
version-chain rows (temporal evolution analysis needs per-version feature vectors).

Reads `paper/data/skill_diffs_chains.parquet` (289,145 version-rows across
218,626 chains), scopes to **RQ4-eligible chains only** (chain length >= 3 per
ADR-0005 frozen chain mechanics), runs `timbro.analyze.analyze_text` on each
selected row, and writes a flat `paper/data/features_chains.parquet` + a
manifest via the WS1 provenance conventions.

Reuses `extract_features.py`'s per-doc analyze/table-building seams (no logic
duplication): `_analyze_one`, `_feature_keys`, `_worker_init`.

Not a hypothesis test: descriptive/corpus-construction step (see
paper/code/ws3/LEDGER.md PRE-REG — WS3 step 5 prep). Deterministic pipeline,
no seed.

Scope (pre-registered, derived from the chains table itself, not invented):
  chains table already carries a precomputed, verified-constant-per-chain
  `n_versions` column (one distinct value per skill_id, equal to that chain's
  row count -- checked empirically before freezing this script). RQ4-eligible
  = n_versions >= 3 (ADR-0005 chain definition: "chains require >= 3 versions").
  Eligible chains = 14,388 (matches the WS1 LEDGER); eligible version-rows =
  67,164 (this run's expected N).

Resumable: completed chunks are written as
`features_chains_parts/part-{i:05d}.parquet`; a rerun skips parts that already
exist and re-concats at the end.

Run (from repo root):
  uv run --with-requirements paper/code/ws1/requirements.txt \
      python paper/code/ws3/step1_extraction/extract_features_chains.py
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
sys.path.append(str(Path(__file__).resolve().parents[2] / "ws1"))
from _manifest import data_dir, sha256_file, write_manifest  # noqa: E402

# Reuse extract_features.py's analyze/table-building machinery (no duplication).
from extract_features import (  # noqa: E402
    _analyze_one,
    _feature_keys,
    _worker_init,
)

# Carried through from the chains table onto every feature row (identity/
# ordering/join columns present in skill_diffs_chains.parquet's own schema).
CARRY_COLUMNS = [
    "skill_id",
    "version_index",
    "commit_date",
    "after_sha",
    "n_versions",
    "skill_cluster_id",
    "is_canonical",
    "repo",
]
TEXT_COLUMN = "text"

CHUNK_SIZE = 2000  # docs per resumable part
PARTS_DIRNAME = "features_chains_parts"
OUTPUT_NAME = "features_chains.parquet"
INPUT_NAME = "skill_diffs_chains.parquet"

MIN_VERSIONS = 3  # ADR-0005: chains require >= 3 versions to be RQ4-eligible

SCOPE_RULE = (
    "n_versions >= 3 (ADR-0005 frozen chain-eligibility rule); n_versions is "
    "precomputed per-chain in skill_diffs_chains.parquet and verified constant "
    "per skill_id and equal to that chain's row count before this run"
)


def select_scope(table: pa.Table) -> pa.compute.Expression:
    """Boolean mask over `table`: RQ4-eligible version-rows (chain length >= 3)."""
    return pc.greater_equal(table.column("n_versions"), MIN_VERSIONS)


# --- driver -------------------------------------------------------------------


def _rows_to_table(results, feature_keys) -> pa.Table:
    """Assemble part results into a flat Arrow table with a stable column order."""
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
    parts_dir = ddir / PARTS_DIRNAME
    parts_dir.mkdir(parents=True, exist_ok=True)
    out_path = ddir / OUTPUT_NAME

    print(f"[ws3:extract_chains] reading {input_path}", flush=True)
    table = pq.read_table(input_path, columns=CARRY_COLUMNS + [TEXT_COLUMN])

    n_total_rows = table.num_rows
    n_total_chains = len(table.column("skill_id").unique())
    print(
        f"[ws3:extract_chains] input: {n_total_rows} version-rows / "
        f"{n_total_chains} chains",
        flush=True,
    )

    eligible = select_scope(table)
    n_selected = pc.sum(pc.cast(eligible, pa.int64())).as_py()
    selected = table.filter(eligible)
    n_eligible_chains = len(selected.column("skill_id").unique())

    print(
        f"[ws3:extract_chains] scope: n_versions>=3 -> {n_selected} version-rows "
        f"across {n_eligible_chains} eligible chains",
        flush=True,
    )

    # Pre-registered STOP: derived N drift is D7-style upstream change — do not
    # silently proceed; the LEDGER records this as a stop condition.
    assert n_eligible_chains == 14388, (
        f"eligible chain count {n_eligible_chains} != 14388 "
        "(chains-table drift — STOP, consult user)"
    )
    assert n_selected == 67164, (
        f"eligible version-row count {n_selected} != 67164 "
        "(chains-table drift — STOP, consult user)"
    )

    carry_cols = {c: selected.column(c).to_pylist() for c in CARRY_COLUMNS}
    texts = selected.column(TEXT_COLUMN).to_pylist()

    feature_keys = _feature_keys()

    n_parts = (n_selected + CHUNK_SIZE - 1) // CHUNK_SIZE
    n_workers = max(1, (os.cpu_count() or 1) - 5)
    print(
        f"[ws3:extract_chains] {n_selected} docs, {n_parts} parts x {CHUNK_SIZE}, "
        f"{n_workers} workers",
        flush=True,
    )

    total_failures = 0
    total_rows = 0
    ctx = mp.get_context("spawn")  # clean worker init; avoid fork+spaCy footguns

    for part_i in range(n_parts):
        part_path = parts_dir / f"part-{part_i:05d}.parquet"
        lo = part_i * CHUNK_SIZE
        hi = min(lo + CHUNK_SIZE, n_selected)

        if part_path.exists():
            existing = pq.read_table(part_path, columns=["analyze_error"])
            f = pc.sum(
                pc.cast(pc.is_valid(existing.column("analyze_error")), pa.int64())
            ).as_py()
            total_rows += existing.num_rows
            total_failures += f
            print(
                f"[ws3:extract_chains] part {part_i + 1}/{n_parts} skip (exists), "
                f"rows {existing.num_rows}, failures {f}",
                flush=True,
            )
            continue

        args = [
            (i, {c: carry_cols[c][i] for c in CARRY_COLUMNS}, texts[i])
            for i in range(lo, hi)
        ]
        with ctx.Pool(processes=n_workers, initializer=_worker_init) as pool:
            results = pool.map(_analyze_one, args, chunksize=25)

        part_table = _rows_to_table(results, feature_keys)
        pq.write_table(part_table, part_path)

        failures = pc.sum(
            pc.cast(pc.is_valid(part_table.column("analyze_error")), pa.int64())
        ).as_py()
        total_rows += part_table.num_rows
        total_failures += failures
        print(
            f"[ws3:extract_chains] part {part_i + 1}/{n_parts} done, "
            f"rows {part_table.num_rows}, failures {failures}",
            flush=True,
        )

    # Concat all parts -> features_chains.parquet.
    print(f"[ws3:extract_chains] concatenating {n_parts} parts -> {out_path}", flush=True)
    part_files = sorted(parts_dir.glob("part-*.parquet"))
    tables = [pq.read_table(p) for p in part_files]
    features = pa.concat_tables(tables, promote_options="permissive")
    pq.write_table(features, out_path)

    n_out = features.num_rows
    failures_final = pc.sum(
        pc.cast(pc.is_valid(features.column("analyze_error")), pa.int64())
    ).as_py()
    fail_rate = failures_final / n_out if n_out else 0.0
    print(
        f"[ws3:extract_chains] DONE rows {n_out}, failures {failures_final} "
        f"({fail_rate:.4%})",
        flush=True,
    )

    write_manifest(
        out_path,
        source="features_chains",
        inputs=[
            {"file": INPUT_NAME, "sha256": sha256_file(input_path)},
        ],
        n_rows=n_out,
        packages=("spacy", "en_core_web_sm", "pyarrow", "textdescriptives"),
        extra={
            "scope_rule": SCOPE_RULE,
            "n_total_rows": n_total_rows,
            "n_total_chains": n_total_chains,
            "n_eligible_chains": n_eligible_chains,
            "n_selected": n_selected,
            "n_analyze_failures": failures_final,
            "analyze_failure_rate": fail_rate,
            "n_feature_keys": len(feature_keys),
            "chunk_size": CHUNK_SIZE,
        },
    )
    print("[ws3:extract_chains] manifest written under paper/code/ws1/manifests/", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
