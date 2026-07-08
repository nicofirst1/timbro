#!/usr/bin/env python3
"""Build the anchor corpus from HF shl0ms/skill-diffs.

Default mode (no flags): PROBE ONLY. Lists the repo's files, downloads only the
small repos.parquet in full, and reads the schema + row count of the remaining
frozen files via HTTP range requests against their parquet footers (no full
download). Asserts every row count against `_schema.SKILL_DIFFS_EXPECTED` — a
mismatch is a D7 spec/reality conflict and the script stops rather than
fabricating.

`--full` mode does the real ~5.5GB extract (see EXTRACT_FILES below — diffs.parquet
is NOT needed and is skipped) and writes:
  (a) paper/data/src_skill_diffs.parquet   -- cross-sectional, CORPUS_COLUMNS + sibling cols
  (b) paper/data/skill_diffs_chains.parquet -- per-version chain table for RQ4

Both are gated behind `--full` and are NOT invoked by the probe. See
paper/README.md §4 WS1 step 1 and §8b + addendum for the frozen chain mechanics.
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from huggingface_hub import HfApi, HfFileSystem, hf_hub_download

from _manifest import data_dir, sha256_file, write_manifest
from _schema import CORPUS_COLUMNS, SKILL_DIFFS_EXPECTED, SOURCE_SKILL_DIFFS
from _text import extract_frontmatter

REPO_ID = "shl0ms/skill-diffs"
REPO_TYPE = "dataset"

# Tables actually consumed by the --full extract. diffs.parquet (986,515-row raw
# commit-level superset) is NOT needed: per README §8b addendum, chain roots come
# from skills_initial.parquet and pairs from diffs_clean.parquet. Skipping it saves
# ~2.2GB of the naive "download everything" estimate.
EXTRACT_FILES = ["skills_initial.parquet", "diffs_clean.parquet", "repos.parquet", "bundled.parquet"]
ALL_FROZEN_FILES = list(SKILL_DIFFS_EXPECTED)  # the 5 files frozen in §8b

SIBLING_COLUMNS = [
    "n_sibling_files",
    "has_scripts_dir",
    "has_references_dir",
    "has_assets_dir",
    "has_readme_in_folder",
]

def _hf_path(filename: str) -> str:
    return f"datasets/{REPO_ID}/{filename}"


# --------------------------------------------------------------------------- #
# PART A: probe (default mode, run now)
# --------------------------------------------------------------------------- #


def run_probe() -> None:
    api = HfApi()

    print(f"[probe] listing files in {REPO_ID} ...")
    files = api.list_repo_files(REPO_ID, repo_type=REPO_TYPE)
    for fn in sorted(files):
        print(f"  {fn}")

    print("\n[probe] fetching size metadata via dataset_info (no download) ...")
    info = api.dataset_info(REPO_ID, files_metadata=True)
    sizes = {s.rfilename: s.size for s in info.siblings}
    for fn in ALL_FROZEN_FILES:
        print(f"  {fn}: {sizes.get(fn, 0) / 1e9:.3f} GB")

    # --- repos.parquet: small, full download, hard assert ---
    print("\n[probe] downloading repos.parquet (small, full download) ...")
    repos_path = hf_hub_download(repo_id=REPO_ID, filename="repos.parquet", repo_type=REPO_TYPE)
    repos_table = pq.read_table(repos_path)
    n = repos_table.num_rows
    expected = SKILL_DIFFS_EXPECTED["repos.parquet"]
    status = "OK" if n == expected else "MISMATCH"
    print(f"[probe] repos.parquet: {n} rows (expected {expected}) [{status}]")
    if n != expected:
        print(f"D7 SPEC/REALITY CONFLICT: repos.parquet has {n} rows, expected {expected}. Stopping.")
        sys.exit(1)
    print(f"[probe] repos.parquet columns ({len(repos_table.schema.names)}): {repos_table.schema.names}")

    # --- remaining files: schema + row count via footer-only range reads ---
    fs = HfFileSystem()
    remaining = ["skills_initial.parquet", "diffs.parquet", "diffs_clean.parquet", "bundled.parquet"]
    for fn in remaining:
        print(f"\n[probe] reading schema+row count of {fn} via HTTP range requests "
              f"(footer only, no full download) ...")
        try:
            with fs.open(_hf_path(fn), "rb") as f:
                pf = pq.ParquetFile(f)
                n = pf.metadata.num_rows
                cols = pf.schema_arrow.names
            expected = SKILL_DIFFS_EXPECTED[fn]
            status = "OK" if n == expected else "MISMATCH"
            print(f"[probe] {fn}: {n} rows (expected {expected}) [{status}]")
            print(f"[probe] {fn} columns ({len(cols)}): {cols}")
            if n != expected:
                print(f"D7 SPEC/REALITY CONFLICT: {fn} has {n} rows, expected {expected}. Stopping.")
                sys.exit(1)
        except Exception as e:  # pragma: no cover - defensive fallback
            size_mb = sizes.get(fn, 0) / 1e6
            print(f"[probe] could not cheaply read schema for {fn} ({size_mb:.0f} MB): {e!r}")

    total_all = sum(sizes.get(fn, 0) for fn in ALL_FROZEN_FILES)
    total_extract = sum(sizes.get(fn, 0) for fn in EXTRACT_FILES)
    skipped = sizes.get("diffs.parquet", 0)
    print(f"\n[probe] total size of all 5 frozen files: {total_all / 1e9:.2f} GB")
    print(f"[probe] size needed for --full extract ({', '.join(EXTRACT_FILES)}): {total_extract / 1e9:.2f} GB")
    print(f"[probe] diffs.parquet ({skipped / 1e9:.2f} GB) is skipped by --full -- not consumed "
          f"by the chain-building logic (§8b addendum).")
    print("\n[probe] done. Re-run with --full to perform the real extract (not run here).")


# --------------------------------------------------------------------------- #
# PART B: full extract (guarded behind --full, NOT run by this invocation)
# --------------------------------------------------------------------------- #

INITIAL_COLS = [
    "skill_id",
    "repo",
    "skill_path",
    "platform",
    "after_sha",
    "after_content",
    "commit_date",
    "intent_class",
    "intent_confidence",
    "quality_score",
    "skill_cluster_id",
    "is_canonical",
]
CLEAN_COLS = INITIAL_COLS + ["before_sha"]


def _download_projected(fs: HfFileSystem, filename: str, columns: list[str]) -> pa.Table:
    """Read only the given (leaf) columns of a remote parquet file via HTTP range
    requests. Column pruning happens at the parquet layer, so unused columns
    (notably the large `content`/`before_content` text blobs) are never fetched.
    """
    with fs.open(_hf_path(filename), "rb") as f:
        pf = pq.ParquetFile(f)
        return pf.read(columns=columns)


def _load_repos_index(repos_path: Path) -> dict:
    t = pq.read_table(repos_path, columns=["repo", "stars", "license_spdx", "platform"])
    repos = t.column("repo").to_pylist()
    stars = t.column("stars").to_pylist()
    license_spdx = t.column("license_spdx").to_pylist()
    platform = t.column("platform").to_pylist()
    return {
        r: {"stars": s, "license_spdx": lic, "platform": p}
        for r, s, lic, p in zip(repos, stars, license_spdx, platform)
    }


def _load_bundled_index(fs: HfFileSystem) -> dict:
    """skill_id -> sibling-file feature dict, from bundled.parquet.

    Only `bundled_count` and the sibling *paths* are projected -- the `content`,
    `size`, and `binary_or_oversize` leaves (the bulk of bundled.parquet's 3.4GB)
    are never fetched.

    Note on the README's assumption: bundled.parquet is NOT one-row-per-sibling-file
    (630,119 rows would then mean 630,119 sibling files); reality is one row per
    *skill* (630,119 = every skill scanned at HEAD, including those with zero
    siblings), with a nested `bundled_files` list column per skill. Join key is the
    shared `skill_id` alone (repo is implied), not a skill+repo composite.
    """
    cols = ["skill_id", "bundled_count", "bundled_files.list.element.path"]
    t = _download_projected(fs, "bundled.parquet", cols)
    skill_ids = t.column("skill_id").to_pylist()
    counts = t.column("bundled_count").to_pylist()
    files_col = t.column("bundled_files").to_pylist()  # list[list[{"path": str}]]

    idx = {}
    for sid, cnt, files in zip(skill_ids, counts, files_col):
        paths = [d["path"] for d in (files or []) if d and d.get("path")]
        idx[sid] = {
            "n_sibling_files": cnt,
            "has_scripts_dir": any(p.startswith("scripts/") for p in paths),
            "has_references_dir": any(p.startswith("references/") for p in paths),
            "has_assets_dir": any(p.startswith("assets/") for p in paths),
            # basename match, case-insensitive, at any depth (not just folder root) --
            # the dataset's `path` is already relative to the skill folder, so a
            # top-level README.md is the common case but nested ones also count.
            "has_readme_in_folder": any(Path(p).name.lower() == "readme.md" for p in paths),
        }
    return idx


def load_source_tables(fs: HfFileSystem):
    print("[full] projecting skills_initial.parquet ...")
    initial = _download_projected(fs, "skills_initial.parquet", INITIAL_COLS).to_pylist()
    print(f"[full] skills_initial: {len(initial)} rows")

    print("[full] projecting diffs_clean.parquet ...")
    clean = _download_projected(fs, "diffs_clean.parquet", CLEAN_COLS).to_pylist()
    print(f"[full] diffs_clean: {len(clean)} rows")

    return initial, clean


def build_states_by_skill(initial_rows: list[dict], clean_rows: list[dict]) -> dict:
    """skill_id -> content states (root + every diffs_clean pair for that skill),
    sorted by commit_date. No chain-integrity filtering here -- that is applied
    separately in build_chains() for the RQ4 table only; the cross-sectional table
    just wants "latest by commit_date, else initial" per README step 1.
    """
    states = defaultdict(list)
    for r in initial_rows:
        states[r["skill_id"]].append(
            {
                "sha": r["after_sha"],
                "before_sha": None,
                "text": r["after_content"],
                "commit_date": r["commit_date"],
                "intent_class": r.get("intent_class") or "initial",
                "intent_confidence": r.get("intent_confidence"),
                "quality_score": r.get("quality_score"),
                "repo": r["repo"],
                "skill_path": r["skill_path"],
                "platform": r["platform"],
                "skill_cluster_id": r.get("skill_cluster_id"),
                "is_canonical": r.get("is_canonical"),
                "is_root": True,
            }
        )
    for r in clean_rows:
        states[r["skill_id"]].append(
            {
                "sha": r["after_sha"],
                "before_sha": r["before_sha"],
                "text": r["after_content"],
                "commit_date": r["commit_date"],
                "intent_class": r.get("intent_class"),
                "intent_confidence": r.get("intent_confidence"),
                "quality_score": r.get("quality_score"),
                "repo": r["repo"],
                "skill_path": r["skill_path"],
                "platform": r["platform"],
                "skill_cluster_id": r.get("skill_cluster_id"),
                "is_canonical": r.get("is_canonical"),
                "is_root": False,
            }
        )
    for rows in states.values():
        # commit_date is ISO 8601 with an explicit UTC offset, e.g.
        # "2026-02-05T02:43:22-08:00" -- fromisoformat handles this natively (py>=3.7).
        rows.sort(key=lambda x: datetime.fromisoformat(x["commit_date"]))
    return states


def build_cross_sectional(states_by_skill: dict, repos_idx: dict, bundled_idx: dict) -> list[dict]:
    rows = []
    for skill_id, states in states_by_skill.items():
        root = states[0]
        latest = states[-1]
        repo = latest["repo"]
        repo_meta = repos_idx.get(repo, {})
        sib = bundled_idx.get(skill_id, {})
        text, frontmatter = extract_frontmatter(latest["text"])
        rows.append(
            {
                "skill_id": f"sd:{skill_id}",
                "source": SOURCE_SKILL_DIFFS,
                "platform": latest["platform"],
                "text": text,
                "frontmatter_json": frontmatter,
                "repo": repo,
                "stars": repo_meta.get("stars"),
                "downloads": None,
                "installs": None,
                "created_at": root["commit_date"],
                "updated_at": latest["commit_date"],
                "license_spdx": repo_meta.get("license_spdx"),
                # number of distinct content states seen for this skill (initial + every
                # diffs_clean pair) -- NOT the chain-integrity-filtered RQ4 version count.
                "n_revisions": len(states),
                # left NULL on purpose: filled by dedup.py's global cross-source pass, not
                # to be confused with skill-diffs' own per-source is_canonical (fork marker,
                # used only internally in build_chains()/apply_fork_exclusion()).
                "near_dup_cluster_id": None,
                "is_canonical": None,
                "n_sibling_files": sib.get("n_sibling_files"),
                "has_scripts_dir": sib.get("has_scripts_dir"),
                "has_references_dir": sib.get("has_references_dir"),
                "has_assets_dir": sib.get("has_assets_dir"),
                "has_readme_in_folder": sib.get("has_readme_in_folder"),
            }
        )
    rows.sort(key=lambda r: r["skill_id"])
    return rows


def build_chains(states_by_skill: dict) -> tuple[list[dict], int]:
    """Version-chain rows per §8b addendum: group by skill_id (already done),
    order by commit_date (already done), require before_sha == prev.after_sha;
    on a broken link split the chain and keep only the longest contiguous segment.
    """
    all_rows = []
    n_split_chains = 0
    for skill_id, states in states_by_skill.items():
        segments = [[states[0]]]
        for prev, cur in zip(states, states[1:]):
            if cur["before_sha"] == prev["sha"]:
                segments[-1].append(cur)
            else:
                segments.append([cur])
        if len(segments) > 1:
            n_split_chains += 1
        longest = max(segments, key=len)
        n_versions = len(longest)
        for i, st in enumerate(longest):
            all_rows.append(
                {
                    "skill_id": f"sd:{skill_id}",
                    "version_index": i,
                    "commit_date": st["commit_date"],
                    "after_sha": st["sha"],
                    "text": st["text"],
                    "intent_class": st["intent_class"],
                    "intent_confidence": st["intent_confidence"],
                    "quality_score": st["quality_score"],
                    # repeated per row on purpose: RQ4 filters chains to n_versions >= 3;
                    # skills with fewer still appear here (per spec), just marked.
                    "n_versions": n_versions,
                    "skill_cluster_id": st["skill_cluster_id"],
                    "is_canonical": st["is_canonical"],
                    "repo": st["repo"],
                }
            )
    return all_rows, n_split_chains


def apply_fork_exclusion(chain_rows: list[dict]) -> tuple[list[dict], int]:
    """When a skill_cluster_id (dataset-shipped MinHash linkage) spans multiple
    repos, keep only the is_canonical member's chain; the rest are forks/copies.
    """
    cluster_repos = defaultdict(set)
    cluster_canonical_skills = defaultdict(set)
    for r in chain_rows:
        cid = r["skill_cluster_id"]
        if cid is None:
            continue
        cluster_repos[cid].add(r["repo"])
        if r["is_canonical"]:
            cluster_canonical_skills[cid].add(r["skill_id"])

    excluded_skills = set()
    for cid, repos in cluster_repos.items():
        if len(repos) <= 1:
            continue
        canon = cluster_canonical_skills.get(cid, set())
        for r in chain_rows:
            if r["skill_cluster_id"] == cid and r["skill_id"] not in canon:
                excluded_skills.add(r["skill_id"])

    if not excluded_skills:
        return chain_rows, 0
    kept = [r for r in chain_rows if r["skill_id"] not in excluded_skills]
    return kept, len(excluded_skills)


def _cross_sectional_schema() -> pa.Schema:
    # CORPUS_COLUMNS as pa.string() to match build_gos.py's cross-builder convention
    # (numeric fields stringified; merge.py/downstream code casts as needed). The
    # 5 sibling-file columns are anchor-specific (not part of CORPUS_COLUMNS / the
    # cross-source merge contract) so they keep native types.
    fields = [(c, pa.string()) for c in CORPUS_COLUMNS]
    fields += [
        ("n_sibling_files", pa.int64()),
        ("has_scripts_dir", pa.bool_()),
        ("has_references_dir", pa.bool_()),
        ("has_assets_dir", pa.bool_()),
        ("has_readme_in_folder", pa.bool_()),
    ]
    return pa.schema(fields)


def _rows_to_table(rows: list[dict], schema: pa.Schema) -> pa.Table:
    arrays = []
    for field in schema:
        vals = [r.get(field.name) for r in rows]
        if pa.types.is_string(field.type):
            vals = [None if v is None else str(v) for v in vals]
        arrays.append(pa.array(vals, type=field.type))
    return pa.table({f.name: a for f, a in zip(schema, arrays)}, schema=schema)


def _chain_schema() -> pa.Schema:
    return pa.schema(
        [
            ("skill_id", pa.string()),
            ("version_index", pa.int64()),
            ("commit_date", pa.string()),
            ("after_sha", pa.string()),
            ("text", pa.string()),
            ("intent_class", pa.string()),
            ("intent_confidence", pa.float64()),
            ("quality_score", pa.float64()),
            ("n_versions", pa.int64()),
            ("skill_cluster_id", pa.string()),
            ("is_canonical", pa.bool_()),
            ("repo", pa.string()),
        ]
    )


def run_full() -> None:
    print("[full] starting full extract (projected download, diffs.parquet skipped) ...")

    api = HfApi()
    info = api.dataset_info(REPO_ID, files_metadata=True)
    sizes = {s.rfilename: s.size for s in info.siblings}

    fs = HfFileSystem()

    print("[full] downloading repos.parquet (full, small) ...")
    repos_path = hf_hub_download(repo_id=REPO_ID, filename="repos.parquet", repo_type=REPO_TYPE)
    repos_idx = _load_repos_index(repos_path)

    print("[full] projecting bundled.parquet (sibling paths only, content skipped) ...")
    bundled_idx = _load_bundled_index(fs)

    initial_rows, clean_rows = load_source_tables(fs)

    n_initial, n_clean = len(initial_rows), len(clean_rows)
    for fn, n in (("skills_initial.parquet", n_initial), ("diffs_clean.parquet", n_clean)):
        expected = SKILL_DIFFS_EXPECTED[fn]
        if n != expected:
            print(f"D7 SPEC/REALITY CONFLICT: {fn} has {n} rows, expected {expected}. Stopping.")
            sys.exit(1)

    states_by_skill = build_states_by_skill(initial_rows, clean_rows)

    def input_manifest_entries():
        entries = [
            {
                "hf_dataset": REPO_ID,
                "file": "repos.parquet",
                "n_rows": SKILL_DIFFS_EXPECTED["repos.parquet"],
                "size_bytes": sizes.get("repos.parquet"),
                "sha256": sha256_file(repos_path),
            },
            {
                "hf_dataset": REPO_ID,
                "file": "skills_initial.parquet",
                "n_rows": n_initial,
                "size_bytes": sizes.get("skills_initial.parquet"),
                "columns_projected": INITIAL_COLS,
            },
            {
                "hf_dataset": REPO_ID,
                "file": "diffs_clean.parquet",
                "n_rows": n_clean,
                "size_bytes": sizes.get("diffs_clean.parquet"),
                "columns_projected": CLEAN_COLS,
            },
            {
                "hf_dataset": REPO_ID,
                "file": "bundled.parquet",
                "n_rows": SKILL_DIFFS_EXPECTED["bundled.parquet"],
                "size_bytes": sizes.get("bundled.parquet"),
                "columns_projected": ["skill_id", "bundled_count", "bundled_files.list.element.path"],
            },
        ]
        return entries

    # (a) cross-sectional table
    print("[full] building cross-sectional table ...")
    cross_rows = build_cross_sectional(states_by_skill, repos_idx, bundled_idx)
    cross_table = _rows_to_table(cross_rows, _cross_sectional_schema())
    cross_out = data_dir() / "src_skill_diffs.parquet"
    pq.write_table(cross_table, str(cross_out))
    write_manifest(
        cross_out,
        source=SOURCE_SKILL_DIFFS,
        inputs=input_manifest_entries(),
        n_rows=len(cross_rows),
        packages=["huggingface_hub", "pyarrow"],
        extra={"n_distinct_skills": len(states_by_skill)},
    )
    print(f"[full] wrote {len(cross_rows)} rows to {cross_out.name}")

    # (b) version-chain table
    print("[full] building version-chain table ...")
    chain_rows, n_split = build_chains(states_by_skill)
    chain_rows, n_excluded = apply_fork_exclusion(chain_rows)
    chain_rows.sort(key=lambda r: (r["skill_id"], r["version_index"]))
    chain_table = _rows_to_table(chain_rows, _chain_schema())
    chain_out = data_dir() / "skill_diffs_chains.parquet"
    pq.write_table(chain_table, str(chain_out))
    write_manifest(
        chain_out,
        source=SOURCE_SKILL_DIFFS,
        inputs=input_manifest_entries(),
        n_rows=len(chain_rows),
        packages=["huggingface_hub", "pyarrow"],
        extra={
            "n_chains": len(states_by_skill) - n_excluded,
            "n_split_chains": n_split,
            "n_forks_excluded": n_excluded,
        },
    )
    print(f"[full] wrote {len(chain_rows)} rows to {chain_out.name} "
          f"({n_split} chains split on a broken link, {n_excluded} fork skills excluded)")


def run_chains_only() -> None:
    """Resumable rebuild of ONLY the RQ4 version-chain table (skill_diffs_chains.parquet).

    The cross-sectional table (src_skill_diffs.parquet) is already built by --full and is
    left untouched. This path downloads just skills_initial.parquet + diffs_clean.parquet via
    hf_hub_download (cached + auto-resume on a partial download), then reads only the columns
    it needs locally. It skips bundled.parquet (3.4GB, sibling features -> cross-sectional only)
    and repos.parquet (repo metadata -> cross-sectional only). Chain mechanics are identical to
    run_full (§8b addendum). Use this to recover from an interrupted --full run without re-doing
    the ~5.5GB, non-resumable streaming extract.
    """
    print("[chains-only] downloading skills_initial.parquet (resumable, cached) ...")
    initial_path = hf_hub_download(repo_id=REPO_ID, filename="skills_initial.parquet", repo_type=REPO_TYPE)
    print("[chains-only] downloading diffs_clean.parquet (resumable, cached) ...")
    clean_path = hf_hub_download(repo_id=REPO_ID, filename="diffs_clean.parquet", repo_type=REPO_TYPE)

    print("[chains-only] reading projected columns locally ...")
    initial_rows = pq.read_table(initial_path, columns=INITIAL_COLS).to_pylist()
    clean_rows = pq.read_table(clean_path, columns=CLEAN_COLS).to_pylist()
    n_initial, n_clean = len(initial_rows), len(clean_rows)
    print(f"[chains-only] skills_initial: {n_initial} rows, diffs_clean: {n_clean} rows")

    for fn, n in (("skills_initial.parquet", n_initial), ("diffs_clean.parquet", n_clean)):
        expected = SKILL_DIFFS_EXPECTED[fn]
        if n != expected:
            print(f"D7 SPEC/REALITY CONFLICT: {fn} has {n} rows, expected {expected}. Stopping.")
            sys.exit(1)

    states_by_skill = build_states_by_skill(initial_rows, clean_rows)

    print("[chains-only] building version-chain table ...")
    chain_rows, n_split = build_chains(states_by_skill)
    chain_rows, n_excluded = apply_fork_exclusion(chain_rows)
    chain_rows.sort(key=lambda r: (r["skill_id"], r["version_index"]))
    chain_table = _rows_to_table(chain_rows, _chain_schema())
    chain_out = data_dir() / "skill_diffs_chains.parquet"
    pq.write_table(chain_table, str(chain_out))

    sizes = {s.rfilename: s.size for s in HfApi().dataset_info(REPO_ID, files_metadata=True).siblings}
    inputs = [
        {"hf_dataset": REPO_ID, "file": "skills_initial.parquet", "n_rows": n_initial,
         "size_bytes": sizes.get("skills_initial.parquet"), "columns_projected": INITIAL_COLS,
         "sha256": sha256_file(initial_path)},
        {"hf_dataset": REPO_ID, "file": "diffs_clean.parquet", "n_rows": n_clean,
         "size_bytes": sizes.get("diffs_clean.parquet"), "columns_projected": CLEAN_COLS,
         "sha256": sha256_file(clean_path)},
    ]
    write_manifest(
        chain_out, source=SOURCE_SKILL_DIFFS, inputs=inputs, n_rows=len(chain_rows),
        packages=["huggingface_hub", "pyarrow"],
        extra={"n_chains": len(states_by_skill) - n_excluded, "n_split_chains": n_split,
               "n_forks_excluded": n_excluded},
    )
    print(f"[chains-only] wrote {len(chain_rows)} rows to {chain_out.name} "
          f"({n_split} chains split on a broken link, {n_excluded} fork skills excluded)")


def run_cross_only() -> None:
    """Resumable rebuild of ONLY the cross-sectional table (src_skill_diffs.parquet).

    Mirrors the (a) half of run_full but reads the hub-cached skills_initial + diffs_clean
    (already downloaded by --chains-only via hf_hub_download) instead of re-streaming them,
    and leaves the already-built chains table untouched. Use after a change to the text/
    frontmatter logic (extract_frontmatter) so the committed cross-sectional output is
    regenerated to match the current code. bundled.parquet's sibling columns come from the
    same cheap projected range read as run_full (the full file is 3.4GB; only paths needed).
    """
    api = HfApi()
    sizes = {s.rfilename: s.size for s in api.dataset_info(REPO_ID, files_metadata=True).siblings}
    fs = HfFileSystem()

    print("[cross-only] repos.parquet (cached) ...")
    repos_path = hf_hub_download(repo_id=REPO_ID, filename="repos.parquet", repo_type=REPO_TYPE)
    repos_idx = _load_repos_index(repos_path)

    print("[cross-only] skills_initial.parquet + diffs_clean.parquet (cached, read locally) ...")
    initial_path = hf_hub_download(repo_id=REPO_ID, filename="skills_initial.parquet", repo_type=REPO_TYPE)
    clean_path = hf_hub_download(repo_id=REPO_ID, filename="diffs_clean.parquet", repo_type=REPO_TYPE)
    initial_rows = pq.read_table(initial_path, columns=INITIAL_COLS).to_pylist()
    clean_rows = pq.read_table(clean_path, columns=CLEAN_COLS).to_pylist()

    n_initial, n_clean = len(initial_rows), len(clean_rows)
    for fn, n in (("skills_initial.parquet", n_initial), ("diffs_clean.parquet", n_clean)):
        expected = SKILL_DIFFS_EXPECTED[fn]
        if n != expected:
            print(f"D7 SPEC/REALITY CONFLICT: {fn} has {n} rows, expected {expected}. Stopping.")
            sys.exit(1)

    print("[cross-only] projecting bundled.parquet (sibling paths only, content skipped) ...")
    bundled_idx = _load_bundled_index(fs)

    states_by_skill = build_states_by_skill(initial_rows, clean_rows)

    print("[cross-only] building cross-sectional table ...")
    cross_rows = build_cross_sectional(states_by_skill, repos_idx, bundled_idx)
    cross_table = _rows_to_table(cross_rows, _cross_sectional_schema())
    cross_out = data_dir() / "src_skill_diffs.parquet"
    pq.write_table(cross_table, str(cross_out))
    inputs = [
        {"hf_dataset": REPO_ID, "file": "repos.parquet", "n_rows": SKILL_DIFFS_EXPECTED["repos.parquet"],
         "size_bytes": sizes.get("repos.parquet"), "sha256": sha256_file(repos_path)},
        {"hf_dataset": REPO_ID, "file": "skills_initial.parquet", "n_rows": n_initial,
         "size_bytes": sizes.get("skills_initial.parquet"), "columns_projected": INITIAL_COLS,
         "sha256": sha256_file(initial_path)},
        {"hf_dataset": REPO_ID, "file": "diffs_clean.parquet", "n_rows": n_clean,
         "size_bytes": sizes.get("diffs_clean.parquet"), "columns_projected": CLEAN_COLS,
         "sha256": sha256_file(clean_path)},
        {"hf_dataset": REPO_ID, "file": "bundled.parquet", "n_rows": SKILL_DIFFS_EXPECTED["bundled.parquet"],
         "size_bytes": sizes.get("bundled.parquet"),
         "columns_projected": ["skill_id", "bundled_count", "bundled_files.list.element.path"]},
    ]
    write_manifest(
        cross_out, source=SOURCE_SKILL_DIFFS, inputs=inputs, n_rows=len(cross_rows),
        packages=["huggingface_hub", "pyarrow"], extra={"n_distinct_skills": len(states_by_skill)},
    )
    print(f"[cross-only] wrote {len(cross_rows)} rows to {cross_out.name}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run the full ~5.5GB extract. Default is probe-only (safe, no bulk download).",
    )
    parser.add_argument(
        "--chains-only",
        action="store_true",
        help="Resumable rebuild of ONLY skill_diffs_chains.parquet (RQ4). ~2.1GB via "
        "hf_hub_download; skips bundled.parquet and leaves the cross-sectional table alone.",
    )
    parser.add_argument(
        "--cross-only",
        action="store_true",
        help="Resumable rebuild of ONLY src_skill_diffs.parquet (cross-sectional). Reuses the "
        "hub-cached skills_initial/diffs_clean; leaves the chains table alone.",
    )
    args = parser.parse_args()
    if args.chains_only:
        run_chains_only()
    elif args.cross_only:
        run_cross_only()
    elif args.full:
        run_full()
    else:
        run_probe()


if __name__ == "__main__":
    main()
