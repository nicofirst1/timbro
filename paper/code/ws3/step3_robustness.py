"""WS3 step-3 robustness cut — farm-excluded recluster.

Tests the pre-registered reframe *"skill style is dimensional/continuous; the only
categorical clusters are template farms"* head-on: exclude the 10 template-farm islands
from the organic corpus, then re-cluster the remainder with the IDENTICAL step-3 pipeline.

Design (PRE-REG, LEDGER 2026-07-09 14:55):
  1. Rebuild the frozen step-3 geometry via ``step3_machine_projection._reproduce_step3``
     (imports ``clustering.py`` seams; asserts against
     ``rq1_cluster_assignments.parquet.manifest.json`` — 222,256 pop, PCA 62/0.9027,
     10 HDBSCAN islands noise 0.86308, k-means k=5). Any mismatch -> STOP.
  2. Exclusion rule = the machine-projection probe's ``_assign_islands`` (nearest island
     centroid within that island's 90th-pct member radius, in the frozen 62-comp PCA
     space), applied to ALL 222,256 organic docs. Every doc in any island's ball is
     excluded. Expected n_excluded >= 6,846 (the discovery-sample members are the floor;
     out-of-sample docs in island radii add to it).
  3. Recluster the remainder with the SAME step-3 D-rules (fresh standardize + PCA >=0.90
     on the reduced population, D2 seed-42 50K stratified discovery sample since the
     remainder > 100K, HDBSCAN(min_cluster_size=200), k-means fallback, confound gates) —
     ``recluster_population`` composes the ``clustering.py`` seams, no reimplementation.

Reading rule (FIXED IN ADVANCE): recluster noise > 0.50 AND/OR k-means silhouette < 0.25
SUPPORTS the dimensional reframe; noise < 0.50 with substantive clusters OR silhouette
>= 0.25 is a REAL NEW FINDING, reported straight.

Run (from repo root):
  OMP_NUM_THREADS=4 OPENBLAS_NUM_THREADS=4 MKL_NUM_THREADS=4 \
  VECLIB_MAXIMUM_THREADS=4 NUMEXPR_NUM_THREADS=4 \
  uv run --with-requirements paper/code/ws3/requirements.txt \
      python paper/code/ws3/step3_robustness.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

WS3 = Path(__file__).resolve().parent
sys.path.append(str(WS3))
sys.path.append(str(WS3.parents[0] / "ws1"))

import clustering as C  # noqa: E402  reuse step-3 pipeline seams (no reimplementation)
import step3_machine_projection as MP  # noqa: E402  frozen-geometry reproduction + island rule
from _manifest import (  # noqa: E402
    data_dir,
    repo_root,
    sha256_file,
    write_manifest,
)

OUTPUT_NAME = "step3_robustness_assignments.parquet"

# The dimensional-vs-categorical reading threshold, fixed in the PRE-REG.
NOISE_SUPPORT = 0.50       # recluster noise > this supports the dimensional reframe
SILHOUETTE_STRUCTURE = 0.25  # k-means silhouette >= this = a real new finding
N_EXCLUDED_FLOOR = 6846    # discovery-sample island members (dedup probe) — hard floor


# --- new reusable seam: run the step-3 pipeline on an arbitrary population ----

def recluster_population(pop: pd.DataFrame) -> dict:
    """Run the step-3 Biber pipeline (standardize -> PCA>=0.90 -> D2 50K -> HDBSCAN ->
    k-means fallback) on ``pop``, composing ``clustering.py`` seams. No reimplementation.

    ``pop`` is any organic-canonical-shaped frame (has the numeric feature columns +
    ``platform``). Returns every quantity needed for the summary/manifest. Fresh
    standardize + PCA are fit on ``pop`` (this population's own geometry), exactly as
    step 3 fit on its own population — the frozen step-3 transforms are used only for the
    upstream *exclusion*, never here.
    """
    feats = C.numeric_feature_columns(pop)
    X = pop[feats].to_numpy(dtype=float)

    # fresh standardize fit on THIS population
    Z, imp, scl = C.standardize(X)
    zdf = pd.DataFrame(Z, columns=feats)
    dropped_zero_var = [f for f in feats if float(np.nanstd(zdf[f])) == 0.0]
    if dropped_zero_var:
        feats = [f for f in feats if f not in set(dropped_zero_var)]
        zdf = zdf[feats]
        Z = zdf.to_numpy()

    n_pop = len(pop)
    d2_fires = n_pop > 100000
    if d2_fires:
        sample_idx = C.stratified_sample_idx(pop["platform"], C.SAMPLE_SIZE)
    else:
        sample_idx = np.arange(n_pop)  # small remainder -> full population is the basis
    Z_sample = Z[sample_idx]

    pca, n_comp, cum_var = C.fit_pca(Z_sample)
    pcs_sample = pca.transform(Z_sample)
    pcs_all = pca.transform(Z)

    labels_sample, hdb_params = C.run_hdbscan(pcs_sample)
    non_noise = sorted(int(c) for c in set(labels_sample) if c >= 0)
    noise_frac = float((labels_sample < 0).mean())
    sil_hdb = C.silhouette_on_sample(pcs_sample, labels_sample)

    method = "hdbscan"
    best_k = None
    kmeans_per_k = None
    silhouette = sil_hdb
    no_dialects = False
    trigger_fired = noise_frac > C.NOISE_FALLBACK or len(non_noise) < C.MIN_CLUSTERS
    hdbscan_prefallback = {
        "n_clusters": len(non_noise),
        "noise_fraction": noise_frac,
        "silhouette": sil_hdb,
        "trigger_fired": trigger_fired,
    }
    if trigger_fired:
        method = "kmeans"
        labels_sample, best_k, silhouette, kmeans_per_k = C.kmeans_fallback(pcs_sample)
        non_noise = sorted(int(c) for c in set(labels_sample))
        noise_frac = 0.0
        if silhouette is None or silhouette < C.SILHOUETTE_FLOOR:
            no_dialects = True

    centroids, cluster_ids = C.centroids_from_labels(pcs_sample, labels_sample)
    assign_labels, assign_dist = C.nearest_centroid_labels(pcs_all, centroids)
    full_cluster = np.array(cluster_ids)[assign_labels]

    # cluster naming (deviant standardized medians on the full assigned set)
    cluster_names = {}
    for c in cluster_ids:
        rows = np.where(full_cluster == c)[0]
        z_med = zdf.iloc[rows].median()
        cluster_names[int(c)] = C.cluster_deviant_features(z_med)

    top5_axes = _pca_axis_loadings(pca, feats, k_axes=5)

    return {
        "feats": feats,
        "dropped_zero_var": dropped_zero_var,
        "n_pop": n_pop,
        "d2_fires": d2_fires,
        "sample_idx": sample_idx,
        "pca": pca,
        "n_comp": n_comp,
        "cum_var": cum_var,
        "pcs_all": pcs_all,
        "method": method,
        "hdb_params": hdb_params,
        "hdbscan_prefallback": hdbscan_prefallback,
        "non_noise": non_noise,
        "noise_frac": noise_frac,
        "silhouette": silhouette,
        "best_k": best_k,
        "kmeans_per_k": kmeans_per_k,
        "no_dialects": no_dialects,
        "cluster_ids": cluster_ids,
        "full_cluster": full_cluster,
        "assign_dist": assign_dist,
        "cluster_names": cluster_names,
        "top5_axes": top5_axes,
        "zdf": zdf,
    }


def _pca_axis_loadings(pca, feats, k_axes=5) -> list[list[tuple[str, float]]]:
    """Top-8 |loading| features per PCA axis (the dimensional-structure table)."""
    out = []
    for i in range(min(k_axes, pca.components_.shape[0])):
        comp = pd.Series(pca.components_[i], index=feats)
        top = comp.reindex(comp.abs().sort_values(ascending=False).index).head(8)
        out.append([(str(f), float(v)) for f, v in top.items()])
    return out


# --- one-phrase axis names for the top-5 reduced-population PCA components -----
# Named from the deviant-feature signature AFTER the run (a human reading), so they are
# populated from the observed loadings, not guessed in advance. Populated in main() once
# the loadings are known; the template lives here for locality.
def _name_axis(loadings: list[tuple[str, float]]) -> str:
    """Heuristic one-phrase axis name from the signed top loadings.

    Deterministic, feature-family based — reports what the axis IS made of, does not
    over-interpret. The write-up quotes the loadings; this label is a reading aid.
    """
    fams = {
        "struct_": "structure/formatting",
        "read_": "readability",
        "syn_": "syntactic complexity",
        "coh_": "cohesion",
        "lex_": "lexical richness",
        "dict_": "register (imperative/hedge/conditional)",
        "desc_": "length/size",
        "posdep_": "POS/dependency mix",
        "fm_": "frontmatter completeness",
    }
    counts: dict[str, float] = {}
    for f, v in loadings[:4]:  # top-4 dominate the reading
        for pref, name in fams.items():
            if f.startswith(pref):
                counts[name] = counts.get(name, 0.0) + abs(v)
                break
    if not counts:
        return "mixed"
    ordered = sorted(counts, key=lambda n: counts[n], reverse=True)
    return " vs ".join(ordered[:2]) if len(ordered) >= 2 else ordered[0]


def main() -> int:
    root = repo_root()
    ddir = data_dir()
    feats_path = ddir / C.FEATURES_NAME
    corpus_path = ddir / C.CORPUS_NAME
    figdir = root / "paper" / "figures"
    out_path = ddir / OUTPUT_NAME
    summary_md = WS3 / "step3_robustness.md"

    # --- 1. rebuild the frozen step-3 geometry (asserts vs manifest) ----------
    print("[robust] reproducing step-3 geometry (frozen islands) ...", flush=True)
    G = MP._reproduce_step3(feats_path)
    print(
        f"[robust] REPRODUCED: n_pop={G['n_pop']}, 62 PCA comps, 10 islands, "
        "k-means k=5 — matches manifest.",
        flush=True,
    )
    pop = G["pop"]  # 222,256 organic canonical docs, index reset

    # --- 2. exclusion: project ALL organic docs, assign to islands ------------
    print("[robust] projecting all organic docs into frozen PCA space ...", flush=True)
    feats_all = G["feats"]
    X_all = pop[feats_all].to_numpy(dtype=float)
    Z_all = G["scl"].transform(G["imp"].transform(X_all))
    pcs_all = G["pca"].transform(Z_all)

    isl_label, isl_nearest, isl_dist = MP._assign_islands(
        pcs_all, G["island_centroids"], G["island_radii"], G["islands"]
    )
    excluded_mask = isl_label != -1  # in some island's 90th-pct ball
    n_excluded = int(excluded_mask.sum())
    print(f"[robust] n_excluded (in any island ball): {n_excluded}", flush=True)
    assert n_excluded >= N_EXCLUDED_FLOOR, (
        f"n_excluded {n_excluded} < floor {N_EXCLUDED_FLOOR} — discovery members did not "
        "re-land in their islands; geometry/rule bug, STOP"
    )

    # per-island exclusion breakdown (the assigned island, -1 excluded from this table)
    excl_island_counts = {
        int(isl): int((isl_label == isl).sum()) for isl in G["islands"]
    }

    # per-repo breakdown of the excluded set (join corpus repo by skill_id)
    ct_repo = (
        pq.read_table(corpus_path, columns=["skill_id", "repo"])
        .to_pandas()
        .drop_duplicates("skill_id", keep="first")
        .set_index("skill_id")
    )
    excl_skill_ids = pop.loc[excluded_mask, "skill_id"]
    excl_repos = excl_skill_ids.map(
        lambda s: ct_repo.loc[s, "repo"] if s in ct_repo.index else "?"
    )
    excl_repo_top = excl_repos.value_counts().head(15)

    # --- 3. recluster the remainder -------------------------------------------
    remainder = pop.loc[~excluded_mask].reset_index(drop=True)
    n_remainder = len(remainder)
    assert n_remainder == G["n_pop"] - n_excluded, "remainder arithmetic mismatch — STOP"
    print(
        f"[robust] remainder = {n_remainder} "
        f"(source {remainder['source'].value_counts().to_dict()})",
        flush=True,
    )
    print("[robust] reclustering the remainder (step-3 pipeline) ...", flush=True)
    R = recluster_population(remainder)
    print(
        f"[robust] recluster: PCA {R['n_comp']}/{R['cum_var']:.4f}, method {R['method']}, "
        f"HDBSCAN noise {R['hdbscan_prefallback']['noise_fraction']:.3f} "
        f"sil {R['hdbscan_prefallback']['silhouette']}, "
        f"k-means best_k {R['best_k']} sil {R['silhouette']}",
        flush=True,
    )

    # --- confound gates on the reduced assigned set (parity with step 3) ------
    de = C._load_domain_era(remainder["skill_id"], corpus_path)
    v_platform, tab_platform = C.cramers_v(
        pd.Series(R["full_cluster"]), remainder["platform"].reset_index(drop=True)
    )
    domain_labels, domain_terms = C.assign_domain_labels(de["text"])
    v_domain, _ = C.cramers_v(pd.Series(R["full_cluster"]), pd.Series(domain_labels))
    era = C._era_quarter(de["created_at"])
    n_era_null = int(era.isna().sum())
    v_era, _ = C.cramers_v(pd.Series(R["full_cluster"]), era)
    print(
        f"[robust] confound V — platform {v_platform:.3f}, domain {v_domain:.3f}, "
        f"era {v_era:.3f}",
        flush=True,
    )

    # --- reading (mechanical, per the fixed rule) -----------------------------
    hdb_noise = R["hdbscan_prefallback"]["noise_fraction"]
    km_sil = R["silhouette"] if R["method"] == "kmeans" else None
    # substantive = non-degenerate clusters (size >= min_cluster_size) exist under HDBSCAN
    supports_dimensional = (hdb_noise > NOISE_SUPPORT) or (
        km_sil is not None and km_sil < SILHOUETTE_STRUCTURE
    )
    new_finding = (
        hdb_noise < NOISE_SUPPORT and R["method"] == "hdbscan"
    ) or (km_sil is not None and km_sil >= SILHOUETTE_STRUCTURE)
    reading = "SUPPORTS-DIMENSIONAL" if supports_dimensional and not new_finding else (
        "REAL-NEW-FINDING" if new_finding else "AMBIGUOUS"
    )
    print(f"[robust] READING: {reading}", flush=True)

    # --- write assignment parquet ---------------------------------------------
    out = remainder[["skill_id", "source", "platform", "near_dup_cluster_id"]].copy()
    out["cluster"] = R["full_cluster"]
    out["centroid_distance"] = R["assign_dist"]
    out.to_parquet(out_path, index=False)
    print(f"[robust] wrote {out_path.name} ({len(out)} rows)", flush=True)

    # --- figure: reduced-population PCA scatter (optional, cheap) --------------
    fig_path = _make_scatter(R["pcs_all"], R["full_cluster"], figdir)

    # --- named top-5 axes ------------------------------------------------------
    axis_names = [_name_axis(ax) for ax in R["top5_axes"]]

    # --- summary + manifest ----------------------------------------------------
    _write_summary(
        summary_md, root, G, R,
        n_excluded=n_excluded,
        excl_island_counts=excl_island_counts,
        excl_repo_top=excl_repo_top,
        n_remainder=n_remainder,
        remainder=remainder,
        v_platform=v_platform, v_domain=v_domain, v_era=v_era,
        n_era_null=n_era_null, domain_terms=domain_terms,
        tab_platform=tab_platform,
        axis_names=axis_names,
        reading=reading,
        supports_dimensional=supports_dimensional,
        new_finding=new_finding,
        fig_path=fig_path,
    )
    print(f"[robust] summary -> {summary_md.relative_to(root)}", flush=True)

    write_manifest(
        out_path,
        source="ws3_step3_robustness_farm_excluded_recluster",
        inputs=[
            {"file": C.FEATURES_NAME, "sha256": sha256_file(feats_path)},
            {"file": C.CORPUS_NAME, "sha256": sha256_file(corpus_path)},
        ],
        n_rows=len(out),
        packages=("scikit-learn", "pandas", "numpy", "scipy", "matplotlib", "pyarrow"),
        extra={
            "note": "step-3 robustness cut: exclude the 10 template-farm islands, recluster remainder",
            "reproduction_verified": True,
            "n_organic_total": G["n_pop"],
            "n_excluded": n_excluded,
            "n_excluded_floor_discovery_members": N_EXCLUDED_FLOOR,
            "excluded_per_island": excl_island_counts,
            "excluded_top_repos": {str(k): int(v) for k, v in excl_repo_top.items()},
            "n_remainder": n_remainder,
            "remainder_source_split": {
                str(k): int(v) for k, v in remainder["source"].value_counts().items()
            },
            "remainder_platform_split": {
                str(k): int(v)
                for k, v in remainder["platform"].fillna("__null__").value_counts().items()
            },
            "recluster_dropped_zero_variance": R["dropped_zero_var"],
            "recluster_d2_fired": R["d2_fires"],
            "recluster_pca_n_components": R["n_comp"],
            "recluster_pca_cum_variance": R["cum_var"],
            "recluster_method": R["method"],
            "recluster_hdbscan_prefallback": R["hdbscan_prefallback"],
            "recluster_hdbscan_params": R["hdb_params"],
            "recluster_noise_fraction": R["noise_frac"],
            "recluster_silhouette": R["silhouette"],
            "recluster_kmeans_best_k": R["best_k"],
            "recluster_kmeans_silhouette_per_k": R["kmeans_per_k"],
            "recluster_no_discrete_dialects": R["no_dialects"],
            "recluster_cluster_sizes": {
                int(k): int(v)
                for k, v in pd.Series(R["full_cluster"]).value_counts().sort_index().items()
            },
            "recluster_confound_gates": {
                "d4_platform": {"cramers_v": v_platform, "fired": v_platform > C.CRAMER_V_TRIGGER},
                "d8_domain": {"cramers_v": v_domain, "fired": v_domain > C.CRAMER_V_TRIGGER},
                "d9_era": {"cramers_v": v_era, "fired": v_era > C.CRAMER_V_TRIGGER, "n_era_null": n_era_null},
            },
            "step3_kmeans_silhouette_per_k": {
                "4": 0.1117, "5": 0.1129, "6": 0.0764, "7": 0.0779, "8": 0.0781,
                "9": 0.0624, "10": 0.0628, "11": 0.0764, "12": 0.0687,
            },
            "reading_thresholds": {
                "noise_support": NOISE_SUPPORT,
                "silhouette_structure": SILHOUETTE_STRUCTURE,
            },
            "reading": reading,
            "top5_pca_axis_names": axis_names,
            "figure": fig_path,
            "seed": C.SEED_ALL,
        },
    )
    print("[robust] manifest written under paper/code/ws1/manifests/", flush=True)
    return 0


def _make_scatter(pcs_all, clusters, figdir: Path) -> str:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figdir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(C.SEED_ALL)
    n = len(clusters)
    m = min(30000, n)
    sub = rng.choice(n, size=m, replace=False)
    fig, ax = plt.subplots(figsize=(7, 6))
    cmap = plt.get_cmap("tab10")
    for j, c in enumerate(sorted(set(clusters))):
        mask = clusters[sub] == c
        ax.scatter(
            pcs_all[sub][mask, 0], pcs_all[sub][mask, 1],
            s=3, alpha=0.35, color=cmap(j % 10), label=f"cluster {c}",
        )
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_title("WS3 step-3 robustness — farm-excluded remainder (PC1 vs PC2, 30K sample)")
    ax.legend(markerscale=3, fontsize=8)
    fig.tight_layout()
    p = figdir / "ws3_step3_robustness_pca_scatter.png"
    fig.savefig(p, dpi=130)
    plt.close(fig)
    return str(p.relative_to(repo_root()))


def _fmt_deviant(pairs: list[tuple[str, float]]) -> str:
    return ", ".join(f"`{f}` {v:+.2f}" for f, v in pairs)


def _write_summary(path: Path, root, G, R, **kw) -> None:
    L = []
    L.append("# WS3 step-3 robustness cut — farm-excluded recluster\n")
    L.append(
        "Generated by `paper/code/ws3/step3_robustness.py`. Numbers here are the ones cited "
        "in the LEDGER RESULT — do not retype from elsewhere. **Exploratory / descriptive** "
        "structure-discovery, same as step 3: Observed-level claims only, no inferential "
        "statistic. Tests the pre-registered reframe *\"skill style is dimensional/continuous; "
        "the only categorical clusters are template farms\"* by removing the 10 template-farm "
        "islands and re-clustering the remainder with the identical step-3 pipeline.\n"
    )
    L.append(
        "> The step-3 geometry is reproduced by importing "
        "`step3_machine_projection._reproduce_step3` (which imports `clustering.py` seams) and "
        "asserted against `rq1_cluster_assignments.parquet.manifest.json` before excluding.\n"
    )

    L.append("## Reproduction gate (asserted before excluding)\n")
    L.append("| quantity | value | matches manifest |")
    L.append("|---|---|---|")
    L.append(f"| organic canonical error-dropped pop | {G['n_pop']} | yes |")
    L.append("| PCA components (>=90% var) | 62 (0.9027) | yes |")
    L.append("| HDBSCAN islands / noise / silhouette | 10 / 0.86308 / 0.6638 | yes |")
    L.append("| k-means best k / full sizes | 5 / {0:108698,1:4,2:30342,3:218,4:82994} | yes |")
    L.append("")

    L.append("## Exclusion — the 10 template-farm islands\n")
    L.append(
        f"Every organic doc projected into the frozen 62-comp PCA space and assigned to its "
        f"nearest island iff within that island's 90th-pct member radius (the machine-"
        f"projection probe's `_assign_islands` rule). **n_excluded = {kw['n_excluded']}** of "
        f"{G['n_pop']} (floor {kw['n_excluded'] and ''}6,846 discovery-sample members; the "
        f"excess is out-of-sample docs falling in island radii).\n"
    )
    L.append("### Per-island exclusion count (in that island's ball)\n")
    L.append("| island | 90th-pct radius | n excluded |")
    L.append("|---|---|---|")
    for isl in G["islands"]:
        r = float(G["island_radii"][G["islands"].index(isl)])
        L.append(f"| {isl} | {r:.2f} | {kw['excl_island_counts'][isl]} |")
    L.append("")
    L.append("### Top repos in the excluded set (template-farm signature)\n")
    L.append("| repo | n excluded members |")
    L.append("|---|---|")
    for repo, n in kw["excl_repo_top"].items():
        L.append(f"| `{repo}` | {int(n)} |")
    L.append("")

    L.append("## Remainder (the re-clustered population)\n")
    rem = kw["remainder"]
    L.append(f"- **n_remainder = {kw['n_remainder']}** = {G['n_pop']} − {kw['n_excluded']}")
    L.append(f"- source split: {rem['source'].value_counts().to_dict()}")
    L.append(
        f"- platform split: "
        f"{rem['platform'].fillna('null').value_counts().to_dict()}\n"
    )

    L.append("## Recluster outcome vs step 3 (side by side)\n")
    pf = R["hdbscan_prefallback"]
    L.append("| quantity | step 3 (full organic) | robustness (farm-excluded) |")
    L.append("|---|---|---|")
    L.append(f"| population N | 222,256 | {kw['n_remainder']} |")
    L.append(f"| PCA comps / cum var | 62 / 0.9027 | {R['n_comp']} / {R['cum_var']:.4f} |")
    L.append(
        f"| HDBSCAN clusters / noise / silhouette | 10 / 0.863 / 0.6638 | "
        f"{pf['n_clusters']} / {pf['noise_fraction']:.3f} / {pf['silhouette']} |"
    )
    L.append(
        f"| D3 fallback fired? | yes (noise>0.50) | "
        f"{'yes' if pf['trigger_fired'] else 'no'} |"
    )
    L.append(
        f"| k-means best k / silhouette | 5 / 0.1129 | "
        f"{R['best_k']} / {R['silhouette']} |"
    )
    km_sizes = {
        int(k): int(v)
        for k, v in pd.Series(R["full_cluster"]).value_counts().sort_index().items()
    }
    L.append(
        f"| cluster sizes (assigned) | {{0:108698,1:4,2:30342,3:218,4:82994}} | {km_sizes} |"
    )
    L.append("")

    L.append("### k-means silhouette per k — side by side\n")
    step3_perk = {
        4: 0.1117, 5: 0.1129, 6: 0.0764, 7: 0.0779, 8: 0.0781,
        9: 0.0624, 10: 0.0628, 11: 0.0764, 12: 0.0687,
    }
    rperk = R["kmeans_per_k"] or {}
    L.append("| k | step 3 | robustness |")
    L.append("|---|---|---|")
    for k in range(4, 13):
        s3 = step3_perk.get(k, "-")
        rk = rperk.get(k, rperk.get(str(k), "-"))
        L.append(f"| {k} | {s3} | {rk} |")
    L.append("")

    L.append("## Reading (fixed in advance — read off the rule, not massaged)\n")
    L.append(
        f"**Rule:** recluster HDBSCAN noise > {NOISE_SUPPORT} AND/OR k-means silhouette < "
        f"{SILHOUETTE_STRUCTURE} → SUPPORTS the dimensional reframe (no hidden categorical "
        f"structure behind the farms). HDBSCAN noise < {NOISE_SUPPORT} with substantive "
        f"clusters OR k-means silhouette ≥ {SILHOUETTE_STRUCTURE} → REAL NEW FINDING.\n"
    )
    L.append(f"- HDBSCAN noise (remainder): **{pf['noise_fraction']:.3f}**")
    L.append(f"- k-means best silhouette (remainder): **{R['silhouette']}**")
    L.append(f"- **VERDICT: {kw['reading']}**\n")
    if kw["reading"] == "SUPPORTS-DIMENSIONAL":
        L.append(
            "> Once the industrial template output (the 10 farm islands) is removed, the "
            "residual organic corpus does **not** partition into hidden categorical dialects — "
            "the same high-noise / low-silhouette signature as step 3 persists. This **supports "
            "the pre-registered reframe**: skill style is dimensional/continuous, and the only "
            "categorical clusters in the corpus were the template farms. Observed-level; no test.\n"
        )
    elif kw["reading"] == "REAL-NEW-FINDING":
        L.append(
            "> **New finding:** hidden categorical structure emerged once the template farms "
            "were removed — the farms were masking it. Reported straight (cluster names + "
            "confound gates below); the reframe needs revisiting. Observed-level; no test.\n"
        )
    else:
        L.append(
            "> Ambiguous under the fixed rule (e.g. HDBSCAN did not fall back but silhouette is "
            "borderline). Reported straight; see the numbers above.\n"
        )

    L.append("## Top-5 PCA axes of the reduced population (dimensional-structure table)\n")
    L.append(
        "Per axis: the 8 highest-|loading| features + a one-phrase axis name (family-based "
        "reading of the top loadings, not an over-interpretation). This is the continuous-"
        "dimension table the dimensional reframe rests on.\n"
    )
    for i, axis in enumerate(R["top5_axes"]):
        name = kw["axis_names"][i]
        L.append(f"- **PC{i + 1} — {name}:** {_fmt_deviant(axis)}")
    L.append("")

    L.append("## Recluster cluster names — top deviant features (signed standardized median)\n")
    L.append("Per-feature median AFTER global z-scoring on the remainder (0 = remainder median).\n")
    for c, pairs in R["cluster_names"].items():
        L.append(f"- **cluster {c}:** {_fmt_deviant(pairs)}")
    L.append("")

    L.append("## Confound gates on the reduced assigned set (parity with step 3)\n")
    L.append("| gate | Cramér's V | fired (>0.6)? |")
    L.append("|---|---|---|")
    L.append(f"| D4 platform | {kw['v_platform']:.3f} | {kw['v_platform'] > C.CRAMER_V_TRIGGER} |")
    L.append(f"| D8 domain (TF-IDF k=10) | {kw['v_domain']:.3f} | {kw['v_domain'] > C.CRAMER_V_TRIGGER} |")
    L.append(f"| D9 era (quarters) | {kw['v_era']:.3f} | {kw['v_era'] > C.CRAMER_V_TRIGGER} |")
    L.append(f"\n_D9: {kw['n_era_null']} rows null/unparseable `created_at` (excluded from era gate only)._\n")

    L.append(f"## Figure\n\n`{kw['fig_path']}` — PC1 vs PC2 scatter of the reduced population (30K sample).\n")

    path.write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
