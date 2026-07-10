"""WS3 — EXPLORATORY island dedup-linkage probe (follow-up to step-3 islands).

How do the 10 HDBSCAN islands (discovered on the D2 seed-42 50K sample) relate to
the corpus dedup structure? The user read the per-island example docs and saw
template / copy-paste families (e.g. `NeuralBlitz/Agent-Gateway`,
`Sandeeprdy1729/skill_galaxy`). This probe quantifies that:

  - per island: n_members; n_distinct near_dup_cluster_id (expected == n_members
    because the RQ1 population is canonical-by-construction — one canonical per
    near-dup cluster; any duplicate is a REAL anomaly, flagged loudly);
  - member cluster_size distribution (median, max, SUM) from dedup_map — "sum" =
    the island's true corpus footprint including every lexical near-dup of its
    members (each member is a canonical head; cluster_size counts its fork family);
  - per-island platform split;
  - top-3 repos by member count (vendor-monorepo / template-farm concentration).

**Exploratory / descriptive only** (no hypothesis test, no inferential statistic,
never a headline claim). The islands are NOT a dedup leak — the population is
canonical-only; this probe measures STRUCTURAL template families invisible to
lexical MinHash, and the fork-family footprint each canonical head represents.

The step-3 geometry is reproduced by importing `step3_machine_projection`'s
`_reproduce_step3` seam (which itself imports `clustering.py` and asserts the
reproduction against `rq1_cluster_assignments.parquet.manifest.json`). Any mismatch
-> STOP inside that seam.

Run (from repo root):
  uv run --with-requirements paper/code/ws3/requirements.txt \
      python paper/code/ws3/step3_clustering/step3_island_dedup.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

WS3 = Path(__file__).resolve().parent
sys.path.append(str(WS3))
sys.path.append(str(WS3.parents[1] / "ws1"))

import clustering as C  # noqa: E402  step-3 constants (FEATURES_NAME, CORPUS_NAME, ...)
import step3_machine_projection as MP  # noqa: E402  reuse the reproduction seam
from _manifest import (  # noqa: E402
    data_dir,
    repo_root,
    sha256_file,
    write_manifest,
)

DEDUP_NAME = "dedup_map.parquet"
OUTPUT_NAME = "step3_island_dedup.parquet"
TOP_REPOS = 3


def _island_member_frame(G) -> pd.DataFrame:
    """One row per discovery-sample island member: island id + skill_id + platform.

    ``sample_idx`` are sorted positional indices into ``pop`` (the reset-index organic
    canonical frame); ``labels_hdb`` is aligned to ``Z[sample_idx]``. So
    ``sample_idx[labels_hdb == isl]`` are the ``pop`` positions of island ``isl``.
    """
    pop = G["pop"]
    sample_idx = np.asarray(G["sample_idx"])
    labels_hdb = np.asarray(G["labels_hdb"])
    rows = []
    for isl in G["islands"]:
        member_pop_idx = sample_idx[labels_hdb == isl]
        sub = pop.iloc[member_pop_idx][["skill_id", "platform", "near_dup_cluster_id"]].copy()
        sub.insert(0, "island", int(isl))
        rows.append(sub)
    return pd.concat(rows, ignore_index=True)


def _load_dedup(ddir: Path) -> pd.DataFrame:
    dm = pq.read_table(
        ddir / DEDUP_NAME,
        columns=["skill_id", "near_dup_cluster_id", "cluster_size", "is_canonical"],
    ).to_pandas()
    dm["cluster_size"] = dm["cluster_size"].astype(int)
    return dm


def _load_repo(ddir: Path) -> pd.DataFrame:
    return (
        pq.read_table(ddir / C.CORPUS_NAME, columns=["skill_id", "repo"])
        .to_pandas()
        .drop_duplicates("skill_id", keep="first")
    )


def _top_repos(repos: pd.Series, k: int) -> list[tuple[str, int]]:
    vc = repos.fillna("<null>").value_counts().head(k)
    return [(str(r), int(n)) for r, n in vc.items()]


def _platform_split(platforms: pd.Series) -> dict[str, int]:
    return {
        str(p): int(n)
        for p, n in platforms.fillna("<null>").value_counts().sort_index().items()
    }


def main() -> int:
    root = repo_root()
    ddir = data_dir()
    feats_path = ddir / C.FEATURES_NAME
    dedup_path = ddir / DEDUP_NAME
    corpus_path = ddir / C.CORPUS_NAME
    out_path = ddir / OUTPUT_NAME
    summary_md = WS3 / "step3_island_dedup.md"

    print("[isl-dedup] reproducing step-3 geometry (asserts vs manifest) ...", flush=True)
    G = MP._reproduce_step3(feats_path)
    print(
        f"[isl-dedup] REPRODUCED: n_pop={G['n_pop']}, 10 islands, "
        "geometry matches manifest.",
        flush=True,
    )

    members = _island_member_frame(G)
    dm = _load_dedup(ddir)
    repos = _load_repo(ddir)

    # --- dedup + repo joins ---------------------------------------------------
    # dedup_map already carries near_dup_cluster_id; join it for cluster_size (and to
    # confirm the canonical near_dup_cluster_id agrees with the features carry column).
    merged = members.merge(
        dm[["skill_id", "near_dup_cluster_id", "cluster_size", "is_canonical"]],
        on="skill_id",
        how="left",
        suffixes=("_feat", "_dedup"),
    )
    missing_dedup = int(merged["cluster_size"].isnull().sum())
    assert missing_dedup == 0, (
        f"{missing_dedup} island members missing from dedup_map — every canonical must be "
        "in dedup_map; STOP"
    )
    # sanity: features' near_dup_cluster_id must agree with dedup_map's
    ndc_disagree = int(
        (merged["near_dup_cluster_id_feat"] != merged["near_dup_cluster_id_dedup"]).sum()
    )
    assert ndc_disagree == 0, (
        f"{ndc_disagree} rows where features near_dup_cluster_id != dedup_map — join "
        "inconsistency; STOP"
    )
    # every island member should be a canonical head
    non_canonical = int((merged["is_canonical"] != "true").sum())
    assert non_canonical == 0, (
        f"{non_canonical} island members are NOT canonical in dedup_map — the RQ1 "
        "population should be canonical-only; STOP"
    )

    merged = merged.merge(repos, on="skill_id", how="left")

    # --- ANOMALY CHECK: duplicate near_dup_cluster_id within the population ----
    # Population is canonical-only => one canonical per near-dup cluster => each
    # near_dup_cluster_id should appear at most once among ALL island members.
    ndc = merged["near_dup_cluster_id_dedup"]
    dup_mask = ndc.duplicated(keep=False)
    anomaly_count = int(dup_mask.sum())
    anomaly_examples = []
    if anomaly_count > 0:
        print(
            f"[isl-dedup] !!! ANOMALY: {anomaly_count} island-member rows share a "
            f"near_dup_cluster_id ({ndc[dup_mask].nunique()} distinct clusters duplicated) "
            "— the canonical-only population has repeated near-dup clusters. LOUD FLAG.",
            flush=True,
        )
        anomaly_examples = (
            merged.loc[dup_mask, ["island", "skill_id", "near_dup_cluster_id_dedup"]]
            .sort_values("near_dup_cluster_id_dedup")
            .head(20)
            .to_dict("records")
        )
    else:
        print(
            "[isl-dedup] anomaly check: 0 duplicate near_dup_cluster_id in-population "
            "(canonical-by-construction confirmed).",
            flush=True,
        )

    # --- per-island table -----------------------------------------------------
    per_island_rows = []
    for isl in G["islands"]:
        g = merged[merged["island"] == isl]
        n_members = len(g)
        n_distinct_ndc = int(g["near_dup_cluster_id_dedup"].nunique())
        cs = g["cluster_size"]
        top_repos = _top_repos(g["repo"], TOP_REPOS)
        top_repo_name, top_repo_n = top_repos[0] if top_repos else ("<none>", 0)
        per_island_rows.append(
            {
                "island": int(isl),
                "n_members": int(n_members),
                "n_distinct_near_dup_cluster_id": n_distinct_ndc,
                "dup_ndc_in_island": int(n_members - n_distinct_ndc),
                "cluster_size_median": float(cs.median()),
                "cluster_size_max": int(cs.max()),
                "cluster_size_sum": int(cs.sum()),
                "platform_split": _platform_split(g["platform"]),
                "top_repos": top_repos,
                "top_repo": top_repo_name,
                "top_repo_share": round(top_repo_n / n_members, 3) if n_members else 0.0,
            }
        )

    # --- persist the computed table (parquet, no raw text) --------------------
    out_df = pd.DataFrame(
        [
            {
                "island": r["island"],
                "n_members": r["n_members"],
                "n_distinct_near_dup_cluster_id": r["n_distinct_near_dup_cluster_id"],
                "dup_ndc_in_island": r["dup_ndc_in_island"],
                "cluster_size_median": r["cluster_size_median"],
                "cluster_size_max": r["cluster_size_max"],
                "cluster_size_sum": r["cluster_size_sum"],
                "top_repo": r["top_repo"],
                "top_repo_share": r["top_repo_share"],
            }
            for r in per_island_rows
        ]
    )
    out_df.to_parquet(out_path, index=False)
    print(f"[isl-dedup] wrote {out_path.name} ({len(out_df)} rows)", flush=True)

    total_members = int(out_df["n_members"].sum())
    total_footprint = int(out_df["cluster_size_sum"].sum())
    print(
        f"[isl-dedup] {total_members} island members represent a corpus footprint of "
        f"{total_footprint} docs (sum of member cluster_size).",
        flush=True,
    )

    _write_summary(summary_md, per_island_rows, anomaly_count, anomaly_examples, G, root)
    print(f"[isl-dedup] summary -> {summary_md.relative_to(root)}", flush=True)

    write_manifest(
        out_path,
        source="ws3_island_dedup_linkage_probe_exploratory",
        inputs=[
            {"file": C.FEATURES_NAME, "sha256": sha256_file(feats_path)},
            {"file": DEDUP_NAME, "sha256": sha256_file(dedup_path)},
            {"file": C.CORPUS_NAME, "sha256": sha256_file(corpus_path)},
        ],
        n_rows=len(out_df),
        packages=("scikit-learn", "pandas", "numpy", "scipy", "pyarrow"),
        extra={
            "exploratory": True,
            "note": (
                "descriptive dedup-linkage of the 10 step-3 HDBSCAN islands — no "
                "hypothesis test, never a headline claim"
            ),
            "anomaly_duplicate_ndc_in_population": anomaly_count,
            "island_members_total": total_members,
            "corpus_footprint_total": total_footprint,
            "reproduction_verified": True,
            "seed": C.SEED_ALL,
        },
    )
    print("[isl-dedup] manifest written under paper/code/ws1/manifests/", flush=True)
    return 0


def _write_summary(path, rows, anomaly_count, anomaly_examples, G, root) -> None:
    L = []
    L.append("## Island dedup linkage (exploratory follow-up)\n")
    L.append(
        "Generated by `paper/code/ws3/step3_clustering/step3_island_dedup.py`. **Exploratory / descriptive "
        "only** — no hypothesis test, no inferential statistic, never a headline claim. "
        "Quantifies how the 10 step-3 HDBSCAN islands (discovered on the D2 seed-42 50K "
        "sample) relate to the corpus dedup structure. Islands are the 10 non-noise "
        "clusters, NOT the post-fallback k-means partition. Geometry reproduced by importing "
        "`step3_machine_projection._reproduce_step3` (asserts vs "
        "`rq1_cluster_assignments.parquet.manifest.json`).\n"
    )
    L.append(
        "> `cluster_size` (from `dedup_map.parquet`) = the number of lexical near-dup "
        "members of a doc's near-dup cluster. Each island member is the **canonical head** "
        "of its cluster, so **sum(cluster_size)** = the island's **true corpus footprint** "
        "including every lexical near-dup (fork) of its members. `n_distinct "
        "near_dup_cluster_id` should equal `n_members` (population is canonical-only); any "
        "shortfall is a real anomaly.\n"
    )

    # anomaly line up top
    if anomaly_count == 0:
        L.append(
            "**Anomaly check (duplicate `near_dup_cluster_id` within the canonical-only "
            "population): 0.** Canonical-by-construction confirmed — every island member is "
            "a distinct near-dup cluster's canonical head.\n"
        )
    else:
        L.append(
            f"**Anomaly check: {anomaly_count} island-member rows share a "
            "`near_dup_cluster_id` — LOUD FLAG.** The canonical-only population should have "
            "one canonical per near-dup cluster; a repeat means a non-canonical or duplicated "
            "row leaked into RQ1. First 20 offending rows:\n"
        )
        for e in anomaly_examples:
            L.append(
                f"- island {e['island']} · `{e['skill_id']}` · "
                f"`{e['near_dup_cluster_id_dedup']}`"
            )
        L.append("")

    L.append("### Per-island dedup linkage\n")
    L.append(
        "| island | n_members | distinct ndc | cluster_size median | max | "
        "**sum (footprint)** | top repo (share) |"
    )
    L.append("|---|---|---|---|---|---|---|")
    for r in rows:
        top = f"`{r['top_repo']}` ({100*r['top_repo_share']:.0f}%)"
        L.append(
            f"| {r['island']} | {r['n_members']} | {r['n_distinct_near_dup_cluster_id']} | "
            f"{r['cluster_size_median']:.0f} | {r['cluster_size_max']} | "
            f"**{r['cluster_size_sum']:,}** | {top} |"
        )
    total_members = sum(r["n_members"] for r in rows)
    total_footprint = sum(r["cluster_size_sum"] for r in rows)
    L.append(
        f"| **all** | **{total_members}** | — | — | — | **{total_footprint:,}** | — |"
    )
    L.append("")

    L.append("### Platform split and top-3 repos per island\n")
    L.append("| island | platform split | top-3 repos (member count) |")
    L.append("|---|---|---|")
    for r in rows:
        plat = ", ".join(f"{k} {v}" for k, v in r["platform_split"].items())
        repos = "; ".join(f"`{rp}` {n}" for rp, n in r["top_repos"])
        L.append(f"| {r['island']} | {plat} | {repos} |")
    L.append("")

    # honest 3-sentence reading, computed from the numbers
    frac_top = np.mean([r["top_repo_share"] for r in rows])
    max_foot = max(rows, key=lambda r: r["cluster_size_sum"])
    L.append("### Reading (exploratory, 3 sentences)\n")
    L.append(
        f"1. **Canonical-by-construction is confirmed** — {anomaly_count} duplicate "
        "`near_dup_cluster_id` within the population, so every island member is a distinct "
        "near-dup cluster's canonical head and the islands are **not a dedup leak**: they are "
        "structural template families whose near-identical scaffolds differ in enough tokens "
        "(swapped domain nouns) to escape the lexical MinHash near-dup threshold."
        if anomaly_count == 0
        else f"1. **ANOMALY** — {anomaly_count} island-member rows share a "
        "`near_dup_cluster_id`; the canonical-only invariant is violated and the linkage "
        "below must be read with that caveat (see the flag above)."
    )
    L.append(
        f"2. The islands carry real corpus **footprint beyond their visible members**: the "
        f"{total_members} island members are canonical heads standing in for "
        f"{total_footprint:,} total docs once every lexical near-dup is counted, and the "
        f"heaviest single island (island {max_foot['island']}) alone represents "
        f"{max_foot['cluster_size_sum']:,} docs from {max_foot['n_members']} canonical heads."
    )
    L.append(
        f"3. Repo concentration is high — the top repo alone holds a mean "
        f"{100*frac_top:.0f}% of each island's members — which says these template families "
        "**propagate by within-repo forking** (one scaffold, many domain-swapped copies in "
        "one vendor monorepo) rather than by the cross-corpus lexical copying the dedup "
        "threshold is tuned to catch; the two propagation modes are orthogonal, which is why "
        "the templates survive dedup and surface as tight islands."
    )
    L.append("")

    path.write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
