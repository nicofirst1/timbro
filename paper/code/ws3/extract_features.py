"""WS3 step 1 — deterministic linguistic feature extraction over the WS1 corpus.

Reads ``paper/data/corpus.parquet``, selects the pre-registered extraction scope
(canonical docs UNION install-labeled RQ2 representatives), runs
``timbro.analyze.analyze_text`` on each selected doc, and writes a flat
``paper/data/features.parquet`` + a manifest via the WS1 provenance conventions.

Not a hypothesis test: the "results" are counts, coverage, and failure rates
(see paper/code/ws3/LEDGER.md PRE-REG). Deterministic pipeline, no seed —
``analyze_text`` is a fixed spaCy + textdescriptives + lexicon computation.

Scope (pre-registered, corpus.parquet columns are ALL string):
  - rows where ``is_canonical == "true"``  (STRING column; naive truthiness of the
    literal "false" would keep every row — must compare to the string "true")
  - UNION rows where ``installs`` is non-null / non-empty (ADR-0010 entry-level RQ2
    representatives, not always canonical).

Resumable: completed chunks are written as ``features_parts/part-{i:05d}.parquet``;
a rerun skips parts that already exist and re-concats at the end.

Run (from repo root, detached — leaves ~2 cores free for concurrent WS1 jobs):
  nohup env PYTHONUNBUFFERED=1 uv run --with-requirements paper/code/ws1/requirements.txt \
      python paper/code/ws3/extract_features.py > <log> 2>&1 &
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
# __file__ = paper/code/ws3/extract_features.py -> parents[1] = paper/code
sys.path.append(str(Path(__file__).resolve().parents[1] / "ws1"))
from _manifest import data_dir, sha256_file, write_manifest  # noqa: E402

# --- scope + layout constants -------------------------------------------------

# Carried through from the corpus onto every feature row (identity/join columns).
CARRY_COLUMNS = [
    "skill_id",
    "source",
    "platform",
    "near_dup_cluster_id",
    "is_canonical",
    "installs",
]
TEXT_COLUMN = "text"

CHUNK_SIZE = 2000  # docs per resumable part
PARTS_DIRNAME = "features_parts"
OUTPUT_NAME = "features.parquet"
CORPUS_NAME = "corpus.parquet"

SCOPE_RULE = (
    'is_canonical == "true"  (STRING column, compared to the literal "true")  '
    "UNION  installs non-null/non-empty (ADR-0010 entry-level RQ2 representatives)"
)


def select_scope(table: pa.Table) -> pa.compute.Expression:
    """Boolean mask over `table`: canonical (string "true") UNION install-labeled.

    installs is a STRING column: "non-empty" means valid AND not the empty string.
    """
    canonical = pc.equal(table.column("is_canonical"), "true")
    installs = table.column("installs")
    labeled = pc.and_(
        pc.is_valid(installs),
        pc.not_equal(pc.if_else(pc.is_valid(installs), installs, pa.scalar("")), ""),
    )
    return canonical, labeled


# --- per-worker analysis ------------------------------------------------------

_ANALYZE = None


def _worker_init():
    """Load spaCy + warm the analyze pipeline once per worker process.

    ``timbro.analyze`` lazily builds a per-process lru_cached nlp object; calling
    analyze_text once here forces the load in the worker (never pickled from the
    parent — spaCy Language objects don't round-trip cleanly).
    """
    global _ANALYZE
    from timbro.analyze import analyze_text

    _ANALYZE = analyze_text
    # Warm the model + lexicons so the first real doc isn't paying the load cost.
    _ANALYZE("# warmup\n\nWarm the pipeline.\n")


def _analyze_one(args):
    """Return (carry_dict, feature_dict, error_or_None) for one row. Never raises."""
    idx, carry, text = args
    try:
        feats = _ANALYZE(text if isinstance(text, str) else "")
        return idx, carry, feats, None
    except Exception as exc:  # noqa: BLE001 — one bad doc must not kill the run
        return idx, carry, None, f"{type(exc).__name__}: {exc}"


# --- driver -------------------------------------------------------------------

def _feature_keys() -> list[str]:
    """The exact analyze_text key set (order fixed by a reference call)."""
    from timbro.analyze import analyze_text

    return list(analyze_text("# ref\n\nReference document for keys.\n").keys())


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
    corpus_path = ddir / CORPUS_NAME
    parts_dir = ddir / PARTS_DIRNAME
    parts_dir.mkdir(parents=True, exist_ok=True)
    out_path = ddir / OUTPUT_NAME

    print(f"[ws3:extract] reading {corpus_path}", flush=True)
    table = pq.read_table(corpus_path, columns=CARRY_COLUMNS + [TEXT_COLUMN])

    canonical, labeled = select_scope(table)
    union = pc.or_(canonical, labeled)
    labeled_only = pc.and_(labeled, pc.invert(canonical))

    n_canonical = pc.sum(pc.cast(canonical, pa.int64())).as_py()
    n_labeled = pc.sum(pc.cast(labeled, pa.int64())).as_py()
    n_labeled_only = pc.sum(pc.cast(labeled_only, pa.int64())).as_py()
    n_union = pc.sum(pc.cast(union, pa.int64())).as_py()

    print(
        f"[ws3:extract] scope: canonical={n_canonical} labeled={n_labeled} "
        f"labeled_only={n_labeled_only} union={n_union}",
        flush=True,
    )
    # Pre-registered STOP: canonical drift is D7-style upstream change — do not
    # silently proceed; the LEDGER records this as a stop condition.
    assert n_canonical == 227407, (
        f"canonical count {n_canonical} != 227407 (corpus drift / D7 — STOP, consult user)"
    )

    selected = table.filter(union)
    n_selected = selected.num_rows
    assert n_selected == n_union

    carry_cols = {c: selected.column(c).to_pylist() for c in CARRY_COLUMNS}
    texts = selected.column(TEXT_COLUMN).to_pylist()

    feature_keys = _feature_keys()

    n_parts = (n_selected + CHUNK_SIZE - 1) // CHUNK_SIZE
    n_workers = max(1, (os.cpu_count() or 1) - 3)
    print(
        f"[ws3:extract] {n_selected} docs, {n_parts} parts x {CHUNK_SIZE}, "
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
                f"[ws3:extract] part {part_i + 1}/{n_parts} skip (exists), "
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
            f"[ws3:extract] part {part_i + 1}/{n_parts} done, rows {part_table.num_rows}, "
            f"failures {failures}",
            flush=True,
        )

    # Concat all parts -> features.parquet.
    print(f"[ws3:extract] concatenating {n_parts} parts -> {out_path}", flush=True)
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
        f"[ws3:extract] DONE rows {n_out}, failures {failures_final} "
        f"({fail_rate:.4%})",
        flush=True,
    )

    write_manifest(
        out_path,
        source="features",
        inputs=[
            {"file": CORPUS_NAME, "sha256": sha256_file(corpus_path)},
        ],
        n_rows=n_out,
        packages=("spacy", "en_core_web_sm", "pyarrow", "textdescriptives"),
        extra={
            "scope_rule": SCOPE_RULE,
            "n_canonical": n_canonical,
            "n_labeled": n_labeled,
            "n_labeled_only": n_labeled_only,
            "n_union": n_union,
            "n_selected": n_selected,
            "n_analyze_failures": failures_final,
            "analyze_failure_rate": fail_rate,
            "n_feature_keys": len(feature_keys),
            "chunk_size": CHUNK_SIZE,
        },
    )
    print("[ws3:extract] manifest written under paper/code/ws1/manifests/", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
