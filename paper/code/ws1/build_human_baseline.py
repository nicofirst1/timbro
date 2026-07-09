#!/usr/bin/env python3
"""Build RQ5 human-baseline cells (paper/data/human_baseline.parquet) — WS1 step 9.

Two cells, per ADR-0008 (D10, frozen data rules):

  (a) human/pre-2023: stream `bigcode/the-stack` (HF `streaming=True`, NEVER a full
      download), keep files whose path basename matches README*/CONTRIBUTING* with a
      .md extension, sample ~20k docs at a fixed seed. `bigcode/the-stack` is a GATED
      HF dataset — if the local token lacks access, this cell is BLOCKED and the run
      reports it loudly instead of stalling; cell (b) still proceeds.

  (b) human/post-2023: READMEs from currently-active GitHub repos (`gh` CLI, already
      authenticated in this environment), created/updated >= 2023, same filename
      filter, dropping any repo that contains a SKILL.md (ADR-0008 exclusion).
      Contamination (LLM-assisted READMEs) is expected and acceptable per ADR-0008 —
      it is what makes the C3-C2 contrast a conservative lower bound, not a defect
      to filter out.

Both cells get the SAME English-only filter (ADR-0008 requires it applied identically).
ADR-0008 names "langdetect or equivalent" — `langdetect` is NOT a WS1 dependency and
CLAUDE.md forbids adding one without sign-off, so this builder uses an ASCII-ratio +
function-word heuristic instead (see `is_english_heuristic`). This is a methodology
SUBSTITUTION, not an ADR-sanctioned default — flagged in REPORT/LEDGER, not hidden.

Output schema (human_baseline.parquet; deliberately NOT paper's CORPUS_COLUMNS — this
is a WS3-side RQ5 join artifact, like skillssh_meta.parquet, not part of the merged
skills corpus):
  doc_id, audience, era, text, repo, license_spdx, first_timestamp, last_timestamp,
  source_detail
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import random
import re
import subprocess
import sys
import time
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from _manifest import SEED, data_dir, write_manifest

OUTPUT_COLUMNS = [
    "doc_id", "audience", "era", "text", "repo", "license_spdx",
    "first_timestamp", "last_timestamp", "source_detail",
]

AUDIENCE_HUMAN = "human"
ERA_PRE = "pre"
ERA_POST = "post"

POST_ERA_CUTOFF = "2023-01-01"  # ADR-0008: post-2023 = created/updated >= this date
STACK_SAMPLE_TARGET = 20_000  # ADR-0008: ~20k docs for cell (a)
STACK_DATASET_ID = "bigcode/the-stack"

GH_SAMPLE_TARGET = 20_000  # comparable size for cell (b) (PLAN step 9 "~20k")
GH_MIN_STARS = 5  # cheap floor to avoid near-empty/abandoned repos flooding the sample
# DEVIATION (not in ADR-0008, flagged in REPORT/LEDGER): a single monorepo can carry
# dozens of per-module README/CONTRIBUTING files (observed: one repo -> 172 matches),
# which would let one repo dominate the sample and blow the "one repo, one register
# sample" spirit of a corpus of documents. Capping per repo is a sampling-diversity
# safeguard, not a change to the frozen filename/era/SKILL.md rules.
MAX_DOCS_PER_REPO = 5

CONTACT_EMAIL = "nicofirst1@gmail.com"


# --------------------------------------------------------------------------- pure filters

_FILENAME_RE = re.compile(r"^(README|CONTRIBUTING)", re.IGNORECASE)


def is_readme_or_contributing_basename(basename: str | None) -> bool:
    """True if `basename` (no directory) is a README*/CONTRIBUTING* .md file.

    Case-insensitive prefix match on the stem, exact (case-insensitive) `.md` suffix —
    excludes README.rst, README.txt, readme (no ext), CONTRIBUTING.adoc, etc.
    """
    if not basename:
        return False
    if not basename.lower().endswith(".md"):
        return False
    stem = basename[: -len(".md")]
    return bool(_FILENAME_RE.match(stem))


def assign_era(date_str: str | None, cutoff: str = POST_ERA_CUTOFF) -> str:
    """Classify an ISO-ish date string as 'pre' or 'post' relative to `cutoff`.

    Lexicographic comparison on the YYYY-MM-DD prefix — valid for ISO 8601 timestamps
    (with or without a time component) as long as they share the same format, which
    GitHub API timestamps ("...Z") and the cutoff constant do. Missing/unparseable
    dates default to 'post' (conservative: an undated doc is not assumed pre-ChatGPT).
    """
    if not date_str or len(date_str) < 10:
        return ERA_POST
    return ERA_PRE if date_str[:10] < cutoff else ERA_POST


# English-only heuristic (ADR-0008 names langdetect "or equivalent"; langdetect is not
# a WS1 dependency and none is being added without sign-off — see module docstring and
# report to the ledger). ASCII-ratio catches most non-Latin-script text cheaply; the
# stopword check catches Latin-script non-English (Portuguese/Spanish/French/German
# READMEs are common on GitHub and would sail through a pure-ASCII filter).
_ENGLISH_STOPWORDS = frozenset({
    "the", "and", "is", "to", "of", "for", "in", "a", "this", "you", "with",
    "on", "it", "are", "that", "your", "or", "be", "can", "from", "an",
})
_ASCII_MIN_RATIO = 0.90
_STOPWORD_MIN_HITS = 2  # at least 2 distinct common English stopwords present


def is_english_heuristic(text: str | None) -> bool:
    """Cheap English detector: ASCII-dominant text containing common English stopwords.

    Not a real language ID model (see module docstring: ASCII+stopword substitution for
    langdetect, no new dependency). Two-part check:
      1. >= 90% of characters are ASCII (rejects CJK/Cyrillic/Arabic/etc. READMEs).
      2. At least 2 distinct words from a short English-stopword list appear (rejects
         Latin-script non-English text — French/Spanish/Portuguese/German READMEs are
         mostly ASCII too).
    Empty/whitespace-only text is not English (no signal to classify on).
    """
    if not text or not text.strip():
        return False
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    if ascii_chars / len(text) < _ASCII_MIN_RATIO:
        return False
    words = set(re.findall(r"[a-zA-Z']+", text.lower()))
    hits = len(words & _ENGLISH_STOPWORDS)
    return hits >= _STOPWORD_MIN_HITS


def repo_has_skill_md(tree_paths: list[str]) -> bool:
    """True if any path in a repo's file tree is a SKILL.md (any directory, ADR-0008 exclusion)."""
    return any(Path(p).name == "SKILL.md" for p in tree_paths)


def make_doc_id(source_detail: str, repo: str | None, path: str) -> str:
    """Deterministic id: source tag + stable hash of (repo, path)."""
    key = f"{repo or ''}::{path}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"{source_detail}:{digest}"


# --------------------------------------------------------------------------- cell (a) — The Stack

def build_stack_cell(sample_target: int = STACK_SAMPLE_TARGET, seed: int = SEED) -> tuple[list[dict], dict]:
    """Stream bigcode/the-stack, filter to README*/CONTRIBUTING* .md, reservoir-sample.

    Returns (rows, info). `info` carries blocker detail if streaming failed (e.g. gated
    access) — caller decides whether to abort cell (a) or the whole run.

    Streaming-only (never a full download): `datasets.load_dataset(..., streaming=True)`
    yields an IterableDataset; reservoir sampling (Algorithm R, seeded) keeps memory
    bounded to `sample_target` rows regardless of how many matching docs stream by.
    """
    info: dict = {"blocked": False, "error": None, "n_scanned": 0, "n_matched": 0}
    try:
        from datasets import load_dataset
    except ImportError as exc:
        info["blocked"] = True
        info["error"] = f"ImportError: {exc}"
        return [], info

    try:
        ds = load_dataset(STACK_DATASET_ID, split="train", streaming=True)
    except Exception as exc:  # noqa: BLE001 - report any load failure as a blocker, not a crash
        info["blocked"] = True
        info["error"] = f"{type(exc).__name__}: {exc}"
        return [], info

    rng = random.Random(seed)
    reservoir: list[dict] = []
    n_scanned = 0
    n_matched = 0

    try:
        for example in ds:
            n_scanned += 1
            path = example.get("path") or ""
            basename = Path(path).name
            if not is_readme_or_contributing_basename(basename):
                if n_scanned % 500_000 == 0:
                    print(f"[build_human_baseline:stack] scanned {n_scanned}, matched {n_matched}")
                continue
            n_matched += 1
            row = {
                "doc_id": make_doc_id("stack", example.get("max_stars_repo_name"), path),
                "audience": AUDIENCE_HUMAN,
                "era": ERA_PRE,  # The Stack v1 collected Nov 2021-Jun 2022, pre-ChatGPT by construction
                "text": example.get("content"),
                "repo": example.get("max_stars_repo_name"),
                "license_spdx": example.get("max_stars_repo_licenses"),
                "first_timestamp": None,  # not carried in the-stack schema at file granularity
                "last_timestamp": example.get("max_stars_repo_stars_event_max_datetime"),
                "source_detail": "the_stack_v1",
            }
            if len(reservoir) < sample_target:
                reservoir.append(row)
            else:
                j = rng.randint(0, n_matched - 1)
                if j < sample_target:
                    reservoir[j] = row
    except Exception as exc:  # noqa: BLE001 - mid-stream failure (e.g. auth revoked) is still a blocker
        info["blocked"] = True
        info["error"] = f"mid-stream {type(exc).__name__}: {exc}"

    info["n_scanned"] = n_scanned
    info["n_matched"] = n_matched
    return reservoir, info


# --------------------------------------------------------------------------- cell (b) — GitHub

def gh_api_json(args: list[str]) -> dict | list | None:
    """Run `gh api <args>` and parse JSON stdout; return None on any failure (404 etc.)."""
    try:
        out = subprocess.run(
            ["gh", "api", *args],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return json.loads(out.stdout)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, json.JSONDecodeError):
        return None


def gh_search_candidate_repos(target_repos: int, seed: int = SEED) -> list[dict]:
    """Search GitHub for active, post-2023 repos via `gh api search/repositories`.

    Paginates the search API (max 1,000 results per query per GitHub's cap) across a
    handful of star-bucket queries to get variety within the 1,000-result ceiling, then
    shuffles deterministically. Search API is rate-limited (30 req/min) — this function
    makes O(dozens) calls, not thousands.
    """
    rng = random.Random(seed)
    candidates: dict[str, dict] = {}
    star_buckets = [
        f"stars:{lo}..{hi}"
        for lo, hi in [(5, 20), (21, 100), (101, 1000), (1001, 100000)]
    ]
    per_page = 100
    max_pages = 10  # 10 * 100 = 1,000 = the search API's per-query result cap

    for bucket in star_buckets:
        query = f"{bucket} pushed:>={POST_ERA_CUTOFF} created:>={POST_ERA_CUTOFF}"
        for page in range(1, max_pages + 1):
            result = gh_api_json([
                "search/repositories", "-X", "GET",
                "-f", f"q={query}", "-f", "sort=updated", "-f", "order=desc",
                "-f", f"per_page={per_page}", "-f", f"page={page}",
            ])
            time.sleep(2.1)  # search API cap ~30/min -> stay under it
            if not result or not result.get("items"):
                break
            for item in result["items"]:
                full_name = item.get("full_name")
                if full_name and full_name not in candidates:
                    candidates[full_name] = item
            if len(result["items"]) < per_page:
                break
            if len(candidates) >= target_repos * 3:  # 3x headroom for SKILL.md/README/lang drops
                break
        if len(candidates) >= target_repos * 3:
            break

    ordered = sorted(candidates.values(), key=lambda r: r["full_name"])
    rng.shuffle(ordered)
    return ordered


def gh_fetch_repo_docs(repo_full_name: str, default_branch: str, cache: "GhCache") -> list[dict]:
    """For one repo: get its file tree, drop it if it has SKILL.md, else pull matching docs.

    Uses one `git/trees?recursive=true` call to both check the SKILL.md exclusion and
    find README*/CONTRIBUTING* .md paths anywhere in the tree in a single request, then
    one `contents` GET per matched file. Cached to disk (per repo) so a re-run resumes
    without re-hitting the API for repos already resolved.
    """
    cached = cache.read(repo_full_name)
    if cached is not None:
        return cached

    tree = gh_api_json([
        "repos/" + repo_full_name + f"/git/trees/{default_branch}",
        "-X", "GET", "-f", "recursive=true",
    ])
    if not tree or "tree" not in tree:
        cache.write(repo_full_name, [])
        return []

    paths = [entry["path"] for entry in tree["tree"] if entry.get("type") == "blob"]
    if repo_has_skill_md(paths):
        # Excluded per ADR-0008. Cache a marker (not a bare []) so the exclusion count
        # survives resumed runs — a bare [] is indistinguishable from "no matching file".
        cache.write_excluded(repo_full_name)
        return []

    matched_paths = [p for p in paths if is_readme_or_contributing_basename(Path(p).name)]
    # Prefer root-level docs first (shortest path = most likely the primary README/
    # CONTRIBUTING), then cap at MAX_DOCS_PER_REPO so one monorepo can't dominate the
    # sample (see MAX_DOCS_PER_REPO deviation note above).
    matched_paths = sorted(matched_paths, key=lambda p: (p.count("/"), p))[:MAX_DOCS_PER_REPO]
    rows = []
    for path in matched_paths:
        content = gh_api_json(["repos/" + repo_full_name + "/contents/" + path])
        if not content or content.get("encoding") != "base64" or "content" not in content:
            continue
        try:
            text = base64.b64decode(content["content"]).decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            continue
        rows.append({"path": path, "text": text})

    cache.write(repo_full_name, rows)
    return rows


class GhCache:
    """On-disk per-repo cache so a resumed run skips repos already resolved.

    Payload is either a list of doc rows, or the dict marker
    `{"skill_md_excluded": true}` for repos dropped by the ADR-0008 exclusion —
    the marker keeps the exclusion *reason* recoverable across resumed runs
    (a bare [] would be indistinguishable from "repo had no matching file").
    Legacy caches that stored [] for excluded repos read back as "no docs",
    undercounting exclusions — documented in the manifest field name.
    """

    _EXCLUDED_MARKER = {"skill_md_excluded": True}

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, repo_full_name: str) -> Path:
        key = hashlib.sha256(repo_full_name.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{key}.json"

    def read(self, repo_full_name: str) -> list[dict] | None:
        p = self._path(repo_full_name)
        if not p.exists():
            return None
        payload = json.loads(p.read_text())
        if isinstance(payload, dict) and payload.get("skill_md_excluded"):
            return []
        return payload

    def is_excluded(self, repo_full_name: str) -> bool:
        p = self._path(repo_full_name)
        if not p.exists():
            return False
        payload = json.loads(p.read_text())
        return isinstance(payload, dict) and bool(payload.get("skill_md_excluded"))

    def write(self, repo_full_name: str, rows: list[dict]) -> None:
        self._path(repo_full_name).write_text(json.dumps(rows))

    def write_excluded(self, repo_full_name: str) -> None:
        self._path(repo_full_name).write_text(json.dumps(self._EXCLUDED_MARKER))


def build_github_cell(target_docs: int = GH_SAMPLE_TARGET, seed: int = SEED) -> tuple[list[dict], dict]:
    """Assemble the human/post-2023 GitHub README/CONTRIBUTING cell.

    Searches active post-2023 repos, drops any containing SKILL.md, pulls matching
    README/CONTRIBUTING .md files, stops once `target_docs` rows are collected (or
    candidates are exhausted). Resumable via the on-disk GhCache.
    """
    info: dict = {"n_repos_scanned": 0, "n_repos_matched": 0}
    cache_root = data_dir() / "human_baseline_gh_cache"
    cache = GhCache(cache_root)

    # The candidate list itself is staged to disk: GitHub search sorted by `updated`
    # is NOT stable across runs (repos keep getting pushed), so without this a rerun
    # would scan a different repo set and the output would not reproduce. Delete
    # _candidates.json to force a fresh search.
    candidates_path = cache_root / "_candidates.json"
    if candidates_path.exists():
        candidates = json.loads(candidates_path.read_text())
        print(f"[build_human_baseline:github] {len(candidates)} candidate repos "
              f"(reused from {candidates_path.name})")
    else:
        candidates = gh_search_candidate_repos(target_docs, seed=seed)
        candidates_path.write_text(json.dumps(candidates))
        print(f"[build_human_baseline:github] {len(candidates)} candidate repos from search")

    rows: list[dict] = []
    for repo_item in candidates:
        if len(rows) >= target_docs:
            break
        full_name = repo_item["full_name"]
        default_branch = repo_item.get("default_branch") or "main"
        info["n_repos_scanned"] += 1

        docs = gh_fetch_repo_docs(full_name, default_branch, cache)
        if not docs:
            continue
        info["n_repos_matched"] += 1

        created_at = repo_item.get("created_at")
        updated_at = repo_item.get("pushed_at") or repo_item.get("updated_at")
        license_spdx = (repo_item.get("license") or {}).get("spdx_id") if repo_item.get("license") else None

        # ADR-0008 defines C2 membership as "created OR last-updated >= 2023", so the
        # era tag uses the LATER of the two dates (lexicographic max is valid for ISO
        # timestamps). Today every candidate is already double-constrained post-2023 by
        # the search query (`created:>=2023-01-01 pushed:>=2023-01-01`), so created_at
        # alone would give the same answer — but that would silently depend on the
        # query string; max() keeps the tag correct if the query ever loosens to the
        # ADR's OR-semantics.
        era_date = max((d for d in (created_at, updated_at) if d), default=None)

        for doc in docs:
            rows.append({
                "doc_id": make_doc_id("github", full_name, doc["path"]),
                "audience": AUDIENCE_HUMAN,
                "era": assign_era(era_date),
                "text": doc["text"],
                "repo": full_name,
                "license_spdx": license_spdx,
                "first_timestamp": created_at,
                "last_timestamp": updated_at,
                "source_detail": "github_active",
            })

        if info["n_repos_scanned"] % 100 == 0:
            print(f"[build_human_baseline:github] scanned {info['n_repos_scanned']} repos, "
                  f"{len(rows)} docs collected so far")

    # Exclusion count read back from the cache markers so it is correct even on a
    # resumed run. Caveat: cache files written before the marker existed (pre-fix runs)
    # stored a bare [] for excluded repos and read back as "no match" — hence the
    # explicit *_marker_based name.
    scanned = candidates[: info["n_repos_scanned"]]
    info["n_repos_skill_md_excluded_marker_based"] = sum(
        1 for repo_item in scanned if cache.is_excluded(repo_item["full_name"])
    )
    # Everything scanned-but-unmatched that is NOT a marked exclusion: tree-fetch
    # failure, no README*/CONTRIBUTING* .md in the tree, or a pre-marker legacy cache.
    info["n_repos_no_match_or_fetch_fail"] = (
        info["n_repos_scanned"] - info["n_repos_matched"]
        - info["n_repos_skill_md_excluded_marker_based"]
    )

    return rows, info


# --------------------------------------------------------------------------- assembly

def apply_english_filter(rows: list[dict]) -> tuple[list[dict], int]:
    kept = [r for r in rows if is_english_heuristic(r.get("text"))]
    return kept, len(rows) - len(kept)


def write_output(rows: list[dict]) -> Path:
    rows_sorted = sorted(rows, key=lambda r: r["doc_id"])
    schema = pa.schema([(c, pa.string()) for c in OUTPUT_COLUMNS])
    arrays = [pa.array([r.get(c) for r in rows_sorted], type=pa.string()) for c in OUTPUT_COLUMNS]
    table = pa.table({c: a for c, a in zip(OUTPUT_COLUMNS, arrays)}, schema=schema)
    out_path = data_dir() / "human_baseline.parquet"
    pq.write_table(table, str(out_path))
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-stack", action="store_true",
                         help="Skip cell (a) (The Stack) even if HF access is available.")
    parser.add_argument("--skip-github", action="store_true",
                         help="Skip cell (b) (GitHub) — e.g. to test cell (a) alone.")
    parser.add_argument("--stack-sample", type=int, default=STACK_SAMPLE_TARGET)
    parser.add_argument("--github-sample", type=int, default=GH_SAMPLE_TARGET)
    args = parser.parse_args(argv)

    all_rows: list[dict] = []
    cell_reports: dict = {}

    if not args.skip_stack:
        print(f"[build_human_baseline] Cell (a): streaming {STACK_DATASET_ID} (seed={SEED})...")
        stack_rows, stack_info = build_stack_cell(sample_target=args.stack_sample, seed=SEED)
        if stack_info["blocked"]:
            print("=" * 78)
            print("[build_human_baseline] *** BLOCKER: cell (a) — bigcode/the-stack ***")
            print(f"  {stack_info['error']}")
            print("  bigcode/the-stack is a GATED HF dataset; the local HF token lacks access")
            print("  (or none is configured). Per task instructions: report and continue with")
            print("  cell (b) only. RQ5 floor is >=5,000 docs per human cell (ADR-0008) — cell")
            print("  (a) currently contributes 0 rows until access is granted and this rerun.")
            print("=" * 78)
        else:
            print(f"[build_human_baseline] Cell (a): scanned={stack_info['n_scanned']} "
                  f"matched={stack_info['n_matched']} sampled={len(stack_rows)}")
        all_rows.extend(stack_rows)
        cell_reports["stack"] = {**stack_info, "n_sampled": len(stack_rows)}
    else:
        cell_reports["stack"] = {"skipped": True}

    if not args.skip_github:
        print(f"[build_human_baseline] Cell (b): GitHub search + fetch (target={args.github_sample})...")
        gh_rows, gh_info = build_github_cell(target_docs=args.github_sample, seed=SEED)
        print(f"[build_human_baseline] Cell (b): {len(gh_rows)} docs from "
              f"{gh_info['n_repos_matched']} repos ({gh_info['n_repos_scanned']} scanned)")
        all_rows.extend(gh_rows)
        cell_reports["github"] = {**gh_info, "n_docs": len(gh_rows)}
    else:
        cell_reports["github"] = {"skipped": True}

    print(f"[build_human_baseline] Pooled {len(all_rows)} rows before English filter...")
    kept_rows, n_dropped_lang = apply_english_filter(all_rows)
    print(f"[build_human_baseline] English filter: kept {len(kept_rows)}, dropped {n_dropped_lang} "
          f"(ASCII+stopword heuristic — NOT langdetect, see module docstring)")

    n_by_era = {}
    for r in kept_rows:
        n_by_era[r["era"]] = n_by_era.get(r["era"], 0) + 1
    print(f"[build_human_baseline] Post-filter era breakdown: {n_by_era}")

    # Seeded over BOTH eras so a blocked/empty cell records an explicit false
    # (a missing key would hide the pre-cell blocker from the manifest).
    floor_status = {era: n_by_era.get(era, 0) >= 5000 for era in (ERA_PRE, ERA_POST)}
    for era in (ERA_PRE, ERA_POST):
        n = n_by_era.get(era, 0)
        status = "OK" if n >= 5000 else "BELOW ADR-0008 FLOOR (5,000) -> RQ5 downgrades to descriptive"
        print(f"[build_human_baseline]   era={era}: n={n} [{status}]")

    out_path = write_output(kept_rows)
    print(f"[build_human_baseline] Wrote {len(kept_rows)} rows to {out_path}")

    write_manifest(
        out_path,
        source="human_baseline",
        inputs=[
            {"hf_dataset": STACK_DATASET_ID, "streaming": True, "blocked": cell_reports["stack"].get("blocked", "skipped")},
            {"source": "github_search_api", "cutoff": POST_ERA_CUTOFF, "min_stars": GH_MIN_STARS,
             "contact": CONTACT_EMAIL},
        ],
        n_rows=len(kept_rows),
        packages=["pyarrow", "datasets", "huggingface_hub"],
        extra={
            "english_filter_method": "ascii_ratio+stopword_heuristic_NOT_langdetect",
            # ADR-0008 requires the language-filter threshold LOGGED, not just named.
            "english_filter_ascii_min_ratio": _ASCII_MIN_RATIO,
            "english_filter_stopword_min_hits": _STOPWORD_MIN_HITS,
            "english_filter_dropped": n_dropped_lang,
            "n_by_era": n_by_era,
            "floor_status_per_era": floor_status,
            "cell_reports": cell_reports,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
