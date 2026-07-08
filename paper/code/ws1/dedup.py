#!/usr/bin/env python3
"""Exact + near-dup collapse across the pooled TEXT sources (D1 pre-reg).

Reads src_skill_diffs.parquet + src_gos.parquet + src_slop.parquet, pools them, and
assigns near_dup_cluster_id / is_canonical per skill. Writes a COMPACT MAP
(dedup_map.parquet), not a text copy — merge.py joins this back onto the pooled text.

Method (frozen, LEDGER.md pre-reg): exact dedup by normalized-text SHA256; near-dup
via datasketch MinHashLSH, 0.9 Jaccard on word 5-gram shingles, num_perm=128, seed=42.
Near-dup runs over exact-canonical representatives only, then propagates to all
members of each exact class. Connected components (via LSH candidate pairs) = one
near_dup_cluster_id. Canonical per cluster: source rank (skill_diffs < graph_of_skills
< slop_stub), then most n_revisions, then smallest skill_id.
"""
from __future__ import annotations

import hashlib
import logging
import re

import pyarrow.parquet as pq
from datasketch import MinHash, MinHashLSH

from _manifest import SEED, data_dir, sha256_file, write_manifest
from _schema import SOURCE_GOS, SOURCE_SKILL_DIFFS, SOURCE_SLOP
from _text import string_table

log = logging.getLogger("dedup")

OUT_COLUMNS = ["skill_id", "near_dup_cluster_id", "cluster_size", "is_canonical"]

_WS_RE = re.compile(r"\s+")
_SOURCE_RANK = {SOURCE_SKILL_DIFFS: 0, SOURCE_GOS: 1, SOURCE_SLOP: 2}
_NUM_PERM = 128
_JACCARD_THRESHOLD = 0.9
_SHINGLE_N = 5


def normalize_text(text: str | None) -> str:
    """lowercase, collapse whitespace runs to a single space, strip."""
    if not text:
        return ""
    return _WS_RE.sub(" ", text.strip().lower()).strip()


def shingles(normalized_text: str) -> set[str]:
    """Word 5-gram shingles. Fewer than 5 tokens -> single shingle = whole text."""
    tokens = normalized_text.split(" ") if normalized_text else [""]
    if len(tokens) < _SHINGLE_N:
        return {normalized_text}
    return {" ".join(tokens[i:i + _SHINGLE_N]) for i in range(len(tokens) - _SHINGLE_N + 1)}


def _minhash(shingle_set: set[str]) -> MinHash:
    m = MinHash(num_perm=_NUM_PERM, seed=SEED)
    for s in shingle_set:
        m.update(s.encode("utf-8"))
    return m


class _UnionFind:
    def __init__(self, keys):
        self.parent = {k: k for k in keys}

    def find(self, k):
        while self.parent[k] != k:
            self.parent[k] = self.parent[self.parent[k]]
            k = self.parent[k]
        return k

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def _pick_canonical(rows: list[dict]) -> dict:
    def key(r):
        rank = _SOURCE_RANK.get(r.get("source"), 99)
        try:
            n_rev = float(r.get("n_revisions") or 0)
        except (TypeError, ValueError):
            n_rev = 0.0
        return (rank, -n_rev, r["skill_id"])

    return min(rows, key=key)


def assign_clusters(rows: list[dict]) -> list[dict]:
    """Pure logic: pooled source rows -> [{skill_id, near_dup_cluster_id, cluster_size, is_canonical}].

    rows: list of dicts with at least skill_id, source, text, n_revisions.
    No I/O — safe for unit tests.
    """
    log.info("exact-dedup over %d pooled rows...", len(rows))
    # 1. Exact dedup by normalized-text SHA256.
    exact_classes: dict[str, list[dict]] = {}
    for r in rows:
        norm = normalize_text(r.get("text"))
        digest = hashlib.sha256(norm.encode("utf-8")).hexdigest()
        exact_classes.setdefault(digest, []).append({**r, "_norm": norm})

    # One representative per exact class (deterministic: smallest skill_id).
    rep_by_digest = {
        digest: min(members, key=lambda r: r["skill_id"])
        for digest, members in exact_classes.items()
    }
    digests = sorted(rep_by_digest.keys())

    # 2. Near-dup via MinHash LSH over exact-class representatives.
    log.info("MinHashing %d exact-class reps...", len(digests))
    minhashes = {}
    for i, d in enumerate(digests):
        minhashes[d] = _minhash(shingles(rep_by_digest[d]["_norm"]))
        if (i + 1) % 50_000 == 0:
            log.info("  minhash %d/%d", i + 1, len(digests))
    lsh = MinHashLSH(threshold=_JACCARD_THRESHOLD, num_perm=_NUM_PERM)
    for d in digests:
        lsh.insert(d, minhashes[d])

    uf = _UnionFind(digests)
    log.info("LSH querying %d reps for near-dup pairs...", len(digests))
    for i, d in enumerate(digests):
        for cand in lsh.query(minhashes[d]):
            # LSH banding only approximates the threshold; post-filter on the MinHash
            # Jaccard estimate so the 0.9 bound is actually enforced (LEDGER pre-reg).
            if cand != d and minhashes[d].jaccard(minhashes[cand]) >= _JACCARD_THRESHOLD:
                uf.union(d, cand)
        if (i + 1) % 50_000 == 0:
            log.info("  lsh query %d/%d", i + 1, len(digests))

    # 3. Connected components -> near_dup_cluster_id, assigned by lexicographically
    #    smallest skill_id among all members (across all exact classes) in the component.
    components: dict[str, list[str]] = {}
    for d in digests:
        components.setdefault(uf.find(d), []).append(d)

    def component_min_skill_id(digest_list):
        return min(
            r["skill_id"]
            for d in digest_list
            for r in exact_classes[d]
        )

    ordered_roots = sorted(components.keys(), key=lambda root: component_min_skill_id(components[root]))
    cluster_id_by_root = {root: f"ndc:{i:06d}" for i, root in enumerate(ordered_roots)}

    # 4. Canonical selection + output rows.
    out: list[dict] = []
    for root, digest_list in components.items():
        cluster_id = cluster_id_by_root[root]
        member_rows = [r for d in digest_list for r in exact_classes[d]]
        cluster_size = str(len(member_rows))
        canonical = _pick_canonical(member_rows)
        canonical_id = canonical["skill_id"]
        for r in member_rows:
            out.append({
                "skill_id": r["skill_id"],
                "near_dup_cluster_id": cluster_id,
                "cluster_size": cluster_size,
                "is_canonical": "true" if r["skill_id"] == canonical_id else "false",
            })

    return out


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [dedup] %(message)s",
        datefmt="%H:%M:%S",
    )
    d = data_dir()
    src_paths = {
        SOURCE_SKILL_DIFFS: d / "src_skill_diffs.parquet",
        SOURCE_GOS: d / "src_gos.parquet",
        SOURCE_SLOP: d / "src_slop.parquet",
    }

    log.info("Reading pooled text sources...")
    rows: list[dict] = []
    for source, path in src_paths.items():
        table = pq.read_table(path, columns=["skill_id", "text", "n_revisions"])
        cols = table.to_pylist()
        for r in cols:
            rows.append({"skill_id": r["skill_id"], "source": source, "text": r["text"], "n_revisions": r["n_revisions"]})
    n_input = len(rows)
    log.info("Pooled %d rows across %d sources", n_input, len(src_paths))

    log.info("Computing exact + near-dup clusters...")
    out_rows = assign_clusters(rows)

    n_exact_classes = len(
        {hashlib.sha256(normalize_text(r.get("text")).encode("utf-8")).hexdigest() for r in rows}
    )
    n_near_dup_clusters = len({r["near_dup_cluster_id"] for r in out_rows})
    exact_removal_rate = 1 - (n_exact_classes / n_input) if n_input else 0.0
    near_dup_removal_rate = 1 - (n_near_dup_clusters / n_input) if n_input else 0.0

    # D1 check: skill_diffs near-dup removal rate, computed over the skill_diffs subset only.
    sd_skill_ids = {r["skill_id"] for r in rows if r["source"] == SOURCE_SKILL_DIFFS}
    sd_out = [r for r in out_rows if r["skill_id"] in sd_skill_ids]
    sd_clusters = {r["near_dup_cluster_id"] for r in sd_out}
    n_sd = len(sd_skill_ids)
    skill_diffs_near_dup_removal_rate = (1 - (len(sd_clusters) / n_sd)) if n_sd else 0.0
    d1_fork_explosion = skill_diffs_near_dup_removal_rate > 0.60

    if d1_fork_explosion:
        log.warning(
            "*** D1 FORK-EXPLOSION: skill_diffs near-dup removal %.4f > 60%% — unit of "
            "analysis must become the cluster; STOP and consult (LEDGER pre-reg) ***",
            skill_diffs_near_dup_removal_rate,
        )

    out_rows.sort(key=lambda r: r["skill_id"])
    n_rows = len(out_rows)

    out_path = d / "dedup_map.parquet"
    log.info("Writing %s...", out_path)
    pq.write_table(string_table(out_rows, OUT_COLUMNS), str(out_path))

    log.info("Writing manifest...")
    write_manifest(
        out_path,
        source="dedup",
        inputs=[
            {"file": path.name, "sha256": sha256_file(path)}
            for path in src_paths.values()
        ],
        n_rows=n_rows,
        packages=["datasketch", "pyarrow"],
        extra={
            "n_input": n_input,
            "n_exact_classes": n_exact_classes,
            "n_near_dup_clusters": n_near_dup_clusters,
            "exact_removal_rate": exact_removal_rate,
            "near_dup_removal_rate": near_dup_removal_rate,
            "skill_diffs_near_dup_removal_rate": skill_diffs_near_dup_removal_rate,
            "d1_fork_explosion": d1_fork_explosion,
        },
    )

    log.info("Complete. Wrote %d rows to %s", n_rows, out_path.name)


if __name__ == "__main__":
    main()
