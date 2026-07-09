#!/usr/bin/env python3
"""Pool the text sources, apply the dedup map, join skills.sh installs, emit corpus.parquet.

Reads src_skill_diffs.parquet + src_gos.parquet + src_slop.parquet, projects each to
exactly CORPUS_COLUMNS, overlays near_dup_cluster_id/is_canonical from dedup_map.parquet,
joins installs from skillssh_meta.parquet via a loose owner/repo/name key (LEDGER.md
"RQ2 install-join key" finding), and writes corpus.parquet + rq2_holdout_candidates.parquet
+ REPORT.md (generated, never hand-typed — see render_report()).
"""
from __future__ import annotations

import json
import re

import pyarrow.parquet as pq

from _manifest import data_dir, manifest_dir, repo_root, sha256_file, write_manifest
from _schema import CORPUS_COLUMNS, SOURCE_GOS, SOURCE_SKILL_DIFFS, SOURCE_SLOP
from _text import string_table

HOLDOUT_COLUMNS = ["owner", "repo", "skill", "installs", "url"]

_JOIN_KEY_RE = re.compile(r"[^a-z0-9]")
_FRONTMATTER_NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)


def _join_key(s: str | None) -> str:
    """Lowercase + strip everything but [a-z0-9] (LEDGER: loose install-join key)."""
    return _JOIN_KEY_RE.sub("", (s or "").lower())


def _frontmatter_name(fm: str | None) -> str | None:
    """Parse the `name:` line out of raw frontmatter YAML text; strip matching quotes."""
    if not fm:
        return None
    m = _FRONTMATTER_NAME_RE.search(fm)
    if not m:
        return None
    val = m.group(1)
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        val = val[1:-1]
    return val or None


# --------------------------------------------------------------------------- pool/project


def project_row(row: dict, columns: list[str]) -> dict:
    """Project `row` onto exactly `columns`; missing keys -> None; extras dropped."""
    return {c: row.get(c) for c in columns}


# --------------------------------------------------------------------------- dedup map


def apply_dedup_map(pooled: list[dict], dedup_map: list[dict]) -> tuple[list[dict], int]:
    """Overwrite near_dup_cluster_id/is_canonical from dedup_map (keyed on skill_id).

    Returns (rows, n_missing) — n_missing counts pooled skill_ids absent from the map.
    Rows are never dropped, even when missing (D7-style loud-warn seam; main() prints it).
    """
    by_id = {r["skill_id"]: r for r in dedup_map}
    n_missing = 0
    out = []
    for row in pooled:
        hit = by_id.get(row["skill_id"])
        if hit is None:
            n_missing += 1
            out.append(dict(row))
            continue
        merged = dict(row)
        merged["near_dup_cluster_id"] = hit["near_dup_cluster_id"]
        merged["is_canonical"] = hit["is_canonical"]
        out.append(merged)
    return out, n_missing


# --------------------------------------------------------------------------- installs join


def _skillssh_lookup(skillssh_rows: list[dict]) -> tuple[dict, int]:
    """(owner,repo,skill) loose-key -> max installs; also returns dupe-key count."""
    lookup: dict[tuple[str, str, str], int] = {}
    n_dupe_keys = 0
    for r in skillssh_rows:
        key = (_join_key(r.get("owner")), _join_key(r.get("repo")), _join_key(r.get("skill")))
        installs = r.get("installs")
        try:
            installs = int(installs) if installs is not None else None
        except (TypeError, ValueError):
            installs = None
        if installs is None:
            continue
        if key in lookup:
            n_dupe_keys += 1
            lookup[key] = max(lookup[key], installs)
        else:
            lookup[key] = installs
    return lookup, n_dupe_keys


def _n_revisions_sort_key(row: dict) -> int:
    """Coerce n_revisions to int for max-comparison; None/unparseable -> -1 (ADR-0010 §3b)."""
    val = row.get("n_revisions")
    try:
        return int(val) if val is not None else -1
    except (TypeError, ValueError):
        return -1


def _pick_representative(group: list[dict]) -> dict:
    """Deterministic representative per ADR-0010 §3: canonical, else max n_revisions,
    else smallest skill_id (also the tie-break within the earlier criteria)."""
    canonical = [r for r in group if r.get("is_canonical") == "true"]
    pool = canonical if canonical else group
    best_n_rev = max(_n_revisions_sort_key(r) for r in pool)
    tied = [r for r in pool if _n_revisions_sort_key(r) == best_n_rev]
    return min(tied, key=lambda r: r["skill_id"])


def join_installs(corpus_rows: list[dict], skillssh_rows: list[dict]) -> dict:
    """Label exactly one representative row per matched loose-key group (ADR-0010).

    Only rows with source == skill_diffs are candidates (others carry null repo).
    Groups matching skill_diffs rows by the loose (owner, repo, name) key, then per
    matched key assigns `installs` to a single deterministic representative row
    (canonical, else max n_revisions, else smallest skill_id).

    Returns stats:
      n_skill_diffs             — total skill_diffs rows considered
      n_matched_rows            — rows whose key is in the skills.sh lookup (row-level
                                   diagnostic; the pre-rework over-count numerator)
      n_entries_matched         — distinct matched keys = rows actually labeled
                                   (== n_installs_matched, kept for main()/downstream)
      n_installs_matched        — alias of n_entries_matched
      n_clusters_matched        — distinct near_dup_cluster_id across matched rows
                                   (nulls excluded from the set)
      n_canonical_entries_matched — distinct matched keys whose group contains an
                                   is_canonical row (the canonical-only-would-recover diagnostic)
      n_dupe_skillssh_keys      — unchanged, from the skills.sh-side lookup build
    """
    lookup, n_dupe_keys = _skillssh_lookup(skillssh_rows)

    n_skill_diffs = 0
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for row in corpus_rows:
        if row.get("source") != SOURCE_SKILL_DIFFS:
            continue
        n_skill_diffs += 1
        repo = row.get("repo") or ""
        if "/" not in repo:
            continue
        owner, reponame = repo.split("/", 1)
        name = _frontmatter_name(row.get("frontmatter_json"))
        key = (_join_key(owner), _join_key(reponame), _join_key(name))
        if key not in lookup:
            continue
        groups.setdefault(key, []).append(row)

    n_matched_rows = sum(len(g) for g in groups.values())
    clusters_matched: set = set()
    n_canonical_entries_matched = 0
    for key, group in groups.items():
        installs = lookup[key]
        representative = _pick_representative(group)
        representative["installs"] = str(installs)
        for r in group:
            cid = r.get("near_dup_cluster_id")
            if cid is not None:
                clusters_matched.add(cid)
        if any(r.get("is_canonical") == "true" for r in group):
            n_canonical_entries_matched += 1

    n_entries_matched = len(groups)

    return {
        "n_skill_diffs": n_skill_diffs,
        "n_matched_rows": n_matched_rows,
        "n_entries_matched": n_entries_matched,
        "n_installs_matched": n_entries_matched,
        "n_clusters_matched": len(clusters_matched),
        "n_canonical_entries_matched": n_canonical_entries_matched,
        "n_dupe_skillssh_keys": n_dupe_keys,
    }


# --------------------------------------------------------------------------- holdout


def build_holdout(corpus_rows: list[dict], skillssh_rows: list[dict]) -> tuple[list[dict], dict]:
    """skills.sh rows in a repo overlapping the skill_diffs corpus, unmatched by full triple.

    Returns (holdout_rows sorted by (owner, repo, skill), stats: repo_overlap, ceiling).
    """
    sd_repo_pairs = set()
    matched_triples = set()
    for row in corpus_rows:
        if row.get("source") != SOURCE_SKILL_DIFFS:
            continue
        repo = row.get("repo") or ""
        if "/" not in repo:
            continue
        owner, reponame = repo.split("/", 1)
        sd_repo_pairs.add((_join_key(owner), _join_key(reponame)))
        name = _frontmatter_name(row.get("frontmatter_json"))
        matched_triples.add((_join_key(owner), _join_key(reponame), _join_key(name)))

    overlapping_repo_pairs = set()
    ceiling_rows = []
    holdout = []
    for r in skillssh_rows:
        pair = (_join_key(r.get("owner")), _join_key(r.get("repo")))
        if pair not in sd_repo_pairs:
            continue
        overlapping_repo_pairs.add(pair)
        ceiling_rows.append(r)
        triple = (pair[0], pair[1], _join_key(r.get("skill")))
        if triple not in matched_triples:
            hrow = project_row(r, HOLDOUT_COLUMNS)
            if hrow.get("installs") is not None:
                hrow["installs"] = str(hrow["installs"])  # all-string like join_installs; string_table needs it
            holdout.append(hrow)

    holdout.sort(key=lambda r: (r["owner"], r["repo"], r["skill"]))
    stats = {
        "repo_overlap": len(overlapping_repo_pairs),
        "ceiling": len(ceiling_rows),
    }
    return holdout, stats


# --------------------------------------------------------------------------- report


def render_report(stats: dict) -> str:
    """Pure: render REPORT.md from an already-assembled stats dict. No recomputation."""
    lines = ["# WS1 corpus assembly — REPORT", ""]

    lines.append("## Per-source row counts")
    lines.append("")
    lines.append("| source | rows | canonical |")
    lines.append("|---|---:|---:|")
    for source, count in stats["per_source_counts"].items():
        canon = stats["per_source_canonical_counts"].get(source)
        lines.append(f"| {source} | {count} | {canon} |")
    lines.append("")

    dedup = stats["dedup"]
    lines.append("## Dedup (cited from dedup_map.parquet.manifest.json, not recomputed)")
    lines.append("")
    lines.append(f"- exact_removal_rate: {dedup.get('exact_removal_rate')}")
    lines.append(f"- near_dup_removal_rate: {dedup.get('near_dup_removal_rate')}")
    lines.append(f"- n_exact_classes: {dedup.get('n_exact_classes')}")
    lines.append(f"- n_near_dup_clusters: {dedup.get('n_near_dup_clusters')}")
    lines.append(f"- d1_fork_explosion: {dedup.get('d1_fork_explosion')}")
    lines.append("")

    lines.append("## Platform breakdown")
    lines.append("")
    for platform, count in stats["platform_counts"].items():
        lines.append(f"- {platform}: {count}")
    lines.append("")

    lines.append("## License breakdown")
    lines.append("")
    for license_spdx, count in stats["license_counts"].items():
        lines.append(f"- {license_spdx}: {count}")
    lines.append("")

    ij = stats["install_join"]
    lines.append("## Installs join (RQ2)")
    lines.append("")
    lines.append(f"- n_skill_diffs: {ij.get('n_skill_diffs')}")
    lines.append(f"- n_installs_matched: {ij.get('n_installs_matched')}")
    lines.append(f"- n_matched_rows (row-level, pre-dedup diagnostic): {ij.get('n_matched_rows')}")
    lines.append(f"- n_entries_matched (distinct keys labeled): {ij.get('n_entries_matched')}")
    lines.append(f"- n_clusters_matched (distinct near_dup_cluster_id over matched rows): {ij.get('n_clusters_matched')}")
    lines.append(
        f"- n_canonical_entries_matched (canonical-only would recover): {ij.get('n_canonical_entries_matched')}"
    )
    lines.append(
        "- install_labeled_share_skill_diffs (labeled entries / all skill_diffs rows): "
        f"{ij.get('install_labeled_share_skill_diffs')}"
    )
    lines.append(f"- install_join_rate_ceiling (vs repo-overlap ceiling): {ij.get('install_join_rate_ceiling')}")
    lines.append(
        "- install_join_rate_corpus_present (vs corpus-present skills): "
        f"{ij.get('install_join_rate_corpus_present')} "
        f"(denominator excludes the {ij.get('holdout_n')} temporal-skew triples — skills.sh "
        "skills absent from the corpus snapshot)"
    )
    lines.append(f"- repo_overlap: {ij.get('repo_overlap')}")
    lines.append(f"- holdout_n (rq2_holdout_candidates.parquet): {ij.get('holdout_n')}")
    lines.append("")

    lines.append("## dedup_map coverage")
    lines.append("")
    lines.append(f"- pooled skill_ids absent from dedup_map: {stats.get('dedup_map_missing_n')}")
    lines.append("")

    return "\n".join(lines)


# --------------------------------------------------------------------------- main


def _read_source(path, source_tag) -> list[dict]:
    table = pq.read_table(path)
    rows = table.to_pylist()
    for r in rows:
        r.setdefault("source", source_tag)
    return rows


def main():
    d = data_dir()
    src_specs = [
        (SOURCE_SKILL_DIFFS, d / "src_skill_diffs.parquet"),
        (SOURCE_GOS, d / "src_gos.parquet"),
        (SOURCE_SLOP, d / "src_slop.parquet"),
    ]

    print("[merge] Reading + projecting text sources...")
    per_source_rows: dict[str, list[dict]] = {}
    pooled: list[dict] = []
    for source, path in src_specs:
        raw_rows = _read_source(path, source)
        projected = [project_row(r, CORPUS_COLUMNS) for r in raw_rows]
        per_source_rows[source] = projected
        pooled.extend(projected)
        print(f"[merge]   {source}: {len(projected)} rows")

    expected_total = sum(len(rows) for rows in per_source_rows.values())
    if len(pooled) != expected_total:
        print(
            f"*** D7: pooled row count {len(pooled)} != sum of source counts {expected_total} ***"
        )

    print("[merge] Applying dedup_map...")
    dedup_map_path = d / "dedup_map.parquet"
    dedup_manifest_path = manifest_dir() / "dedup_map.parquet.manifest.json"
    if dedup_map_path.exists():
        dedup_map = pq.read_table(dedup_map_path).to_pylist()
    else:
        print("[merge] WARNING: dedup_map.parquet not found — near_dup_cluster_id/is_canonical left null")
        dedup_map = []
    pooled, dedup_map_missing_n = apply_dedup_map(pooled, dedup_map)
    if dedup_map_missing_n:
        print(f"*** D7: {dedup_map_missing_n} pooled skill_ids absent from dedup_map ***")

    dedup_extra = {}
    if dedup_manifest_path.exists():
        dedup_extra = json.loads(dedup_manifest_path.read_text())

    print("[merge] Joining skills.sh installs...")
    skillssh_path = d / "skillssh_meta.parquet"
    skillssh_rows = pq.read_table(skillssh_path).to_pylist() if skillssh_path.exists() else []
    install_stats = join_installs(pooled, skillssh_rows)

    print("[merge] Building rq2_holdout_candidates...")
    holdout_rows, holdout_stats = build_holdout(pooled, skillssh_rows)

    n_skill_diffs = install_stats["n_skill_diffs"]
    n_matched = install_stats["n_installs_matched"]
    ceiling = holdout_stats["ceiling"]
    install_labeled_share_skill_diffs = (n_matched / n_skill_diffs) if n_skill_diffs else 0.0
    install_join_rate_ceiling = (n_matched / ceiling) if ceiling else 0.0
    n_overlap_triples = ceiling
    holdout_n = len(holdout_rows)
    corpus_present_denom = n_overlap_triples - holdout_n
    install_join_rate_corpus_present = (n_matched / corpus_present_denom) if corpus_present_denom else 0.0

    pooled.sort(key=lambda r: r["skill_id"])

    print("[merge] Writing corpus.parquet...")
    corpus_path = d / "corpus.parquet"
    pq.write_table(string_table(pooled, CORPUS_COLUMNS), str(corpus_path))

    print("[merge] Writing rq2_holdout_candidates.parquet...")
    holdout_path = d / "rq2_holdout_candidates.parquet"
    pq.write_table(string_table(holdout_rows, HOLDOUT_COLUMNS), str(holdout_path))

    inputs = [
        {"file": path.name, "sha256": sha256_file(path)}
        for _, path in src_specs
    ]
    if dedup_map_path.exists():
        inputs.append({"file": dedup_map_path.name, "sha256": sha256_file(dedup_map_path)})
    if skillssh_path.exists():
        inputs.append({"file": skillssh_path.name, "sha256": sha256_file(skillssh_path)})

    n_canonical = sum(1 for r in pooled if r.get("is_canonical") == "true")
    per_source_counts = {s: len(rows) for s, rows in per_source_rows.items()}
    per_source_canonical_counts = {s: 0 for s in per_source_rows}
    for r in pooled:
        if r.get("is_canonical") == "true":
            per_source_canonical_counts[r["source"]] = per_source_canonical_counts.get(r["source"], 0) + 1

    print("[merge] Writing corpus manifest...")
    write_manifest(
        corpus_path,
        source="corpus",
        inputs=inputs,
        n_rows=len(pooled),
        packages=["pyarrow"],
        extra={
            "per_source_counts": per_source_counts,
            "n_canonical": n_canonical,
            "n_installs_matched": n_matched,
            "n_matched_rows": install_stats["n_matched_rows"],
            "n_entries_matched": install_stats["n_entries_matched"],
            "n_clusters_matched": install_stats["n_clusters_matched"],
            "n_canonical_entries_matched": install_stats["n_canonical_entries_matched"],
            "install_labeled_share_skill_diffs": install_labeled_share_skill_diffs,
            "install_join_rate_ceiling": install_join_rate_ceiling,
            "install_join_rate_corpus_present": install_join_rate_corpus_present,
            "repo_overlap": holdout_stats["repo_overlap"],
            "holdout_n": len(holdout_rows),
            "dedup_map_missing_n": dedup_map_missing_n,
        },
    )

    print("[merge] Writing holdout manifest...")
    write_manifest(
        holdout_path,
        source="rq2_holdout_candidates",
        inputs=[{"file": skillssh_path.name, "sha256": sha256_file(skillssh_path)}] if skillssh_path.exists() else [],
        n_rows=len(holdout_rows),
        packages=["pyarrow"],
        extra={"repo_overlap": holdout_stats["repo_overlap"], "ceiling": ceiling},
    )

    print("[merge] Rendering REPORT.md...")
    platform_counts: dict = {}
    for r in pooled:
        platform_counts[r.get("platform")] = platform_counts.get(r.get("platform"), 0) + 1
    license_counts: dict = {}
    for r in pooled:
        license_counts[r.get("license_spdx")] = license_counts.get(r.get("license_spdx"), 0) + 1

    stats = {
        "per_source_counts": per_source_counts,
        "per_source_canonical_counts": per_source_canonical_counts,
        "dedup": {
            "exact_removal_rate": dedup_extra.get("exact_removal_rate"),
            "near_dup_removal_rate": dedup_extra.get("near_dup_removal_rate"),
            "n_exact_classes": dedup_extra.get("n_exact_classes"),
            "n_near_dup_clusters": dedup_extra.get("n_near_dup_clusters"),
            "d1_fork_explosion": dedup_extra.get("d1_fork_explosion"),
        },
        "platform_counts": platform_counts,
        "license_counts": license_counts,
        "install_join": {
            "n_skill_diffs": n_skill_diffs,
            "n_installs_matched": n_matched,
            "n_matched_rows": install_stats["n_matched_rows"],
            "n_entries_matched": install_stats["n_entries_matched"],
            "n_clusters_matched": install_stats["n_clusters_matched"],
            "n_canonical_entries_matched": install_stats["n_canonical_entries_matched"],
            "install_labeled_share_skill_diffs": install_labeled_share_skill_diffs,
            "install_join_rate_ceiling": install_join_rate_ceiling,
            "install_join_rate_corpus_present": install_join_rate_corpus_present,
            "repo_overlap": holdout_stats["repo_overlap"],
            "holdout_n": len(holdout_rows),
        },
        "dedup_map_missing_n": dedup_map_missing_n,
    }
    report_path = repo_root() / "paper" / "code" / "ws1" / "REPORT.md"
    report_path.write_text(render_report(stats))

    print(f"[merge] Complete. corpus.parquet={len(pooled)} rows, holdout={len(holdout_rows)} rows")


if __name__ == "__main__":
    main()
