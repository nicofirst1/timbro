"""WS3 step-3 robustness cut — farm-excluded recluster.

Tests the pre-registered reframe *"skill style is dimensional/continuous; the only
categorical clusters are template farms"* head-on: exclude the template-farm islands
from the organic corpus, then re-cluster the remainder with the IDENTICAL step-3 pipeline.

Two exclusion modes (the recluster pipeline is identical; only the excluded island SET
differs):
  * default (``--all-islands`` / no flag): exclude ALL 10 HDBSCAN islands' balls
    (LEDGER 2026-07-09 14:55). n_excluded = 59,124 — but 35,413 of those came from
    island 8, the diffuse genuinely-diverse island, so this cut is honestly
    "farms + diverse tail".
  * ``--tight-only``: exclude ONLY the 9 tight single-repo/template-scaffold islands
    (0-7 and 9) and RETAIN island 8 (LEDGER 2026-07-09 15:20). This is the SURGICAL
    farm-only cut — it removes the template farms while keeping the diverse island 8,
    closing the "you removed the most diverse slice" reviewer objection.

Design (PRE-REG, LEDGER 2026-07-09 14:55 + surgical variant 2026-07-09 15:20):
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
OUTPUT_NAME_TIGHT = "step3_robustness_surgical_assignments.parquet"

# The dimensional-vs-categorical reading threshold, fixed in the PRE-REG.
NOISE_SUPPORT = 0.50       # recluster noise > this supports the dimensional reframe
SILHOUETTE_STRUCTURE = 0.25  # k-means silhouette >= this = a real new finding
N_EXCLUDED_FLOOR = 6846    # discovery-sample island members (dedup probe) — hard floor

# Surgical (--tight-only) exclusion set: the 9 tight single-repo/template-scaffold islands.
# Island 8 (radius 6.37, diffuse hand-written-looking content) is RETAINED, per the
# 2026-07-09 15:20 PRE-REG — so the residual keeps the corpus's most-diverse slice and the
# null result survives without the "you deleted diversity" objection.
TIGHT_ISLANDS = frozenset({0, 1, 2, 3, 4, 5, 6, 7, 9})
RETAINED_DIVERSE_ISLAND = 8


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


def main(tight_only: bool = False) -> int:
    root = repo_root()
    ddir = data_dir()
    feats_path = ddir / C.FEATURES_NAME
    corpus_path = ddir / C.CORPUS_NAME
    figdir = root / "paper" / "figures"
    out_path = ddir / (OUTPUT_NAME_TIGHT if tight_only else OUTPUT_NAME)
    # both variants append to the same side-by-side summary; the all-islands run writes it,
    # the surgical run appends its section (see _append_surgical_summary).
    summary_md = WS3 / "step3_robustness.md"
    mode = "SURGICAL farm-only (islands 0-7,9; island 8 RETAINED)" if tight_only else (
        "all-islands (0-9)"
    )
    print(f"[robust] exclusion mode: {mode}", flush=True)

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
    if tight_only:
        # SURGICAL: exclude only the 9 tight template-farm islands; RETAIN island 8.
        excluded_mask = np.isin(isl_label, list(TIGHT_ISLANDS))
        n_i8_retained = int((isl_label == RETAINED_DIVERSE_ISLAND).sum())
        print(
            f"[robust] SURGICAL: island {RETAINED_DIVERSE_ISLAND} retained "
            f"({n_i8_retained} docs kept in the remainder)",
            flush=True,
        )
    else:
        excluded_mask = isl_label != -1  # in some island's 90th-pct ball
        n_i8_retained = 0
    n_excluded = int(excluded_mask.sum())
    print(f"[robust] n_excluded (in an excluded island ball): {n_excluded}", flush=True)
    if not tight_only:
        assert n_excluded >= N_EXCLUDED_FLOOR, (
            f"n_excluded {n_excluded} < floor {N_EXCLUDED_FLOOR} — discovery members did not "
            "re-land in their islands; geometry/rule bug, STOP"
        )
    else:
        # island 8 must actually be retained -> surgical n_excluded is strictly below the
        # all-islands cut's 59,124 (it drops island 8's ~35K ball).
        assert n_i8_retained > 0, (
            "SURGICAL cut retained 0 island-8 docs — island 8 was not actually kept; "
            "geometry/rule bug, STOP"
        )

    # per-island exclusion breakdown — count only ACTUALLY-excluded docs, so island 8 shows
    # 0 in the surgical run (its ball members are retained), not its full ball membership.
    excl_island_counts = {
        int(isl): int((isl_label[excluded_mask] == isl).sum()) for isl in G["islands"]
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
    fig_path = _make_scatter(R["pcs_all"], R["full_cluster"], figdir, tight_only=tight_only)

    # --- named top-5 axes ------------------------------------------------------
    axis_names = [_name_axis(ax) for ax in R["top5_axes"]]

    # --- summary + manifest ----------------------------------------------------
    summary_kw = dict(
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
        n_i8_retained=n_i8_retained,
    )
    if tight_only:
        _append_surgical_summary(summary_md, root, G, R, **summary_kw)
    else:
        _write_summary(summary_md, root, G, R, **summary_kw)
    print(f"[robust] summary -> {summary_md.relative_to(root)}", flush=True)

    write_manifest(
        out_path,
        source=(
            "ws3_step3_robustness_surgical_farm_only_recluster" if tight_only
            else "ws3_step3_robustness_farm_excluded_recluster"
        ),
        inputs=[
            {"file": C.FEATURES_NAME, "sha256": sha256_file(feats_path)},
            {"file": C.CORPUS_NAME, "sha256": sha256_file(corpus_path)},
        ],
        n_rows=len(out),
        packages=("scikit-learn", "pandas", "numpy", "scipy", "matplotlib", "pyarrow"),
        extra={
            "note": (
                "step-3 SURGICAL robustness cut: exclude ONLY the 9 tight template-farm "
                "islands (0-7,9); RETAIN the diffuse diverse island 8; recluster remainder"
                if tight_only else
                "step-3 robustness cut: exclude the 10 template-farm islands, recluster remainder"
            ),
            "variant": "surgical_tight_only" if tight_only else "all_islands",
            "excluded_island_set": (
                sorted(TIGHT_ISLANDS) if tight_only else list(range(10))
            ),
            "retained_diverse_island": RETAINED_DIVERSE_ISLAND if tight_only else None,
            "n_island8_ball_retained_in_remainder": n_i8_retained if tight_only else 0,
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


def _make_scatter(pcs_all, clusters, figdir: Path, tight_only: bool = False) -> str:
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
    if tight_only:
        ax.set_title(
            "WS3 step-3 SURGICAL — farm-only remainder, island 8 kept (PC1 vs PC2, 30K)"
        )
        fname = "ws3_step3_robustness_surgical_pca_scatter.png"
    else:
        ax.set_title(
            "WS3 step-3 robustness — farm-excluded remainder (PC1 vs PC2, 30K sample)"
        )
        fname = "ws3_step3_robustness_pca_scatter.png"
    ax.legend(markerscale=3, fontsize=8)
    fig.tight_layout()
    p = figdir / fname
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


# --- committed all-islands numbers, for the three-way side-by-side in the surgical section.
# These are the frozen results of the all-islands cut (LEDGER RESULT 2026-07-09 15:14 /
# manifest step3_robustness_assignments.parquet.manifest.json) — cited, not recomputed.
_ALL_ISLANDS = {
    "n_excluded": 59124,
    "n_remainder": 163132,
    "pca": "64 / 0.9039",
    "hdbscan": "2 / 0.90364 / 0.3533",
    "km": "4 / 0.09298",
    "km_sizes": "{0:28029, 1:4, 2:63719, 3:71380}",
    "reading": "SUPPORTS-DIMENSIONAL",
    "perk": {4: 0.093, 5: 0.0697, 6: 0.0699, 7: 0.0683, 8: 0.0583,
             9: 0.0662, 10: 0.0569, 11: 0.0527, 12: 0.0671},
}
_STEP3_PERK = {4: 0.1117, 5: 0.1129, 6: 0.0764, 7: 0.0779, 8: 0.0781,
               9: 0.0624, 10: 0.0628, 11: 0.0764, 12: 0.0687}


def _append_surgical_summary(path: Path, root, G, R, **kw) -> None:
    """Append the SURGICAL (farm-only, island 8 retained) section to step3_robustness.md.

    Three-way side by side: step 3 (full organic) / all-islands cut / surgical farm-only cut.
    The all-islands numbers are the committed frozen results (cited, not recomputed here).
    """
    pf = R["hdbscan_prefallback"]
    km_sizes = {
        int(k): int(v)
        for k, v in pd.Series(R["full_cluster"]).value_counts().sort_index().items()
    }
    L = ["\n\n---\n"]
    L.append("# SURGICAL variant — farm-only recluster (island 8 RETAINED)\n")
    L.append(
        "Appended by `paper/code/ws3/step3_robustness.py --tight-only` (LEDGER PRE-REG "
        "2026-07-09 15:20). **Exploratory / descriptive**, Observed-level only, no inferential "
        "statistic. Closes the all-islands cut's honest hole: that run excluded ALL 10 islands "
        f"({_ALL_ISLANDS['n_excluded']} docs), but **35,413 of those were island 8** — the "
        "diffuse, genuinely-diverse, hand-written-looking island (90th-pct radius 6.37 vs "
        "~0.5–2.45 for the tight farms), NOT a template farm. A reviewer could object: *\"you "
        "removed the most diverse slice, of course the rest looks homogeneous.\"* This surgical "
        "cut excludes ONLY the **9 tight single-repo/template-scaffold islands (0–7 and 9)** and "
        f"**RETAINS island 8** ({kw['n_i8_retained']} island-8-ball docs kept in the remainder), "
        "so the null result survives with the diverse slice still in.\n"
    )

    L.append("## Surgical exclusion — the 9 tight farm islands only\n")
    L.append(
        f"Same island-radius assignment rule as the all-islands cut (`_assign_islands`, nearest "
        f"island centroid within its 90th-pct member radius, frozen 62-comp PCA space) — the "
        f"ONLY change is the excluded set: islands {sorted(TIGHT_ISLANDS)} excluded, island "
        f"{RETAINED_DIVERSE_ISLAND} retained. **n_excluded = {kw['n_excluded']}** of "
        f"{G['n_pop']} (vs {_ALL_ISLANDS['n_excluded']} for the all-islands cut; the "
        f"{_ALL_ISLANDS['n_excluded'] - kw['n_excluded']:,} difference is exactly island 8's "
        f"retained ball).\n"
    )
    L.append("### Per-island exclusion count (0 = retained)\n")
    L.append("| island | 90th-pct radius | n excluded (surgical) | retained? |")
    L.append("|---|---|---|---|")
    for isl in G["islands"]:
        r = float(G["island_radii"][G["islands"].index(isl)])
        retained = "**RETAINED**" if isl == RETAINED_DIVERSE_ISLAND else "excluded"
        L.append(f"| {isl} | {r:.2f} | {kw['excl_island_counts'][isl]} | {retained} |")
    L.append("")
    L.append("### Top repos in the surgically-excluded set (template-farm signature)\n")
    L.append("| repo | n excluded members |")
    L.append("|---|---|")
    for repo, n in kw["excl_repo_top"].items():
        L.append(f"| `{repo}` | {int(n)} |")
    L.append("")

    L.append("## Remainder (the re-clustered population — island 8 KEPT)\n")
    rem = kw["remainder"]
    L.append(f"- **n_remainder = {kw['n_remainder']}** = {G['n_pop']} − {kw['n_excluded']}")
    L.append(f"- source split: {rem['source'].value_counts().to_dict()}")
    L.append(
        f"- platform split: {rem['platform'].fillna('null').value_counts().to_dict()}\n"
    )

    L.append("## Three-way side by side (step 3 / all-islands cut / surgical farm-only cut)\n")
    L.append("| quantity | step 3 (full organic) | all-islands cut | **surgical (island 8 kept)** |")
    L.append("|---|---|---|---|")
    L.append(f"| population N | 222,256 | {_ALL_ISLANDS['n_remainder']:,} | {kw['n_remainder']:,} |")
    L.append(f"| n_excluded | 0 | {_ALL_ISLANDS['n_excluded']:,} | {kw['n_excluded']:,} |")
    L.append(f"| PCA comps / cum var | 62 / 0.9027 | {_ALL_ISLANDS['pca']} | {R['n_comp']} / {R['cum_var']:.4f} |")
    L.append(
        f"| HDBSCAN clusters / noise / silhouette | 10 / 0.863 / 0.6638 | "
        f"{_ALL_ISLANDS['hdbscan']} | "
        f"{pf['n_clusters']} / {pf['noise_fraction']:.5f} / {pf['silhouette']:.4f} |"
    )
    L.append(
        f"| D3 fallback fired? | yes | yes | {'yes' if pf['trigger_fired'] else 'no'} |"
    )
    L.append(
        f"| k-means best k / silhouette | 5 / 0.1129 | {_ALL_ISLANDS['km']} | "
        f"{R['best_k']} / {R['silhouette']:.5f} |"
    )
    L.append(
        f"| cluster sizes (assigned) | {{0:108698,1:4,2:30342,3:218,4:82994}} | "
        f"{_ALL_ISLANDS['km_sizes']} | {km_sizes} |"
    )
    L.append(
        f"| reading (fixed rule) | — | {_ALL_ISLANDS['reading']} | **{kw['reading']}** |"
    )
    L.append("")

    L.append("### k-means silhouette per k — three-way\n")
    rperk = R["kmeans_per_k"] or {}
    L.append("| k | step 3 | all-islands | surgical |")
    L.append("|---|---|---|---|")
    for k in range(4, 13):
        s3 = _STEP3_PERK.get(k, "-")
        allc = _ALL_ISLANDS["perk"].get(k, "-")
        surg = rperk.get(k, rperk.get(str(k), "-"))
        surg = f"{surg:.4f}" if isinstance(surg, float) else surg
        L.append(f"| {k} | {s3} | {allc} | {surg} |")
    L.append("")

    L.append("## Reading (fixed in advance — same rule/thresholds as the all-islands cut)\n")
    L.append(
        f"**Rule:** recluster HDBSCAN noise > {NOISE_SUPPORT} AND/OR k-means silhouette < "
        f"{SILHOUETTE_STRUCTURE} → SUPPORTS the dimensional reframe. HDBSCAN noise < "
        f"{NOISE_SUPPORT} with substantive clusters OR silhouette ≥ {SILHOUETTE_STRUCTURE} → "
        f"REAL NEW FINDING.\n"
    )
    L.append(f"- HDBSCAN noise (surgical remainder): **{pf['noise_fraction']:.5f}**")
    L.append(f"- k-means best silhouette (surgical remainder): **{R['silhouette']:.5f}**")
    L.append(f"- **VERDICT: {kw['reading']}**\n")
    if kw["reading"] == "SUPPORTS-DIMENSIONAL":
        L.append(
            "> Even the **surgical** cut — template farms removed but the diffuse, diverse "
            "island 8 KEPT — leaves an organic residual with no hidden categorical dialects: "
            "the same high-noise / low-silhouette signature as step 3 and the all-islands cut. "
            "This **supports the pre-registered reframe without the \"you deleted diversity\" "
            "objection**: skill style is dimensional/continuous, and the only categorical "
            "clusters in the corpus were the template farms. Observed-level; no test.\n"
        )
    elif kw["reading"] == "REAL-NEW-FINDING":
        L.append(
            "> **New finding under the surgical cut:** with the farms removed but island 8 "
            "retained, categorical structure emerged. Reported straight (cluster names + "
            "confound gates below). Observed-level; no test.\n"
        )
    else:
        L.append("> Ambiguous under the fixed rule; see the numbers above.\n")

    L.append("## Top-5 PCA axes of the surgical remainder (dimensional-structure table)\n")
    for i, axis in enumerate(R["top5_axes"]):
        name = kw["axis_names"][i]
        L.append(f"- **PC{i + 1} — {name}:** {_fmt_deviant(axis)}")
    L.append("")

    L.append("## Surgical recluster cluster names — top deviant features (signed z-median)\n")
    for c, pairs in R["cluster_names"].items():
        L.append(f"- **cluster {c}:** {_fmt_deviant(pairs)}")
    L.append("")

    L.append("## Confound gates on the surgical reduced assigned set (parity with step 3)\n")
    L.append("| gate | Cramér's V | fired (>0.6)? |")
    L.append("|---|---|---|")
    L.append(f"| D4 platform | {kw['v_platform']:.3f} | {kw['v_platform'] > C.CRAMER_V_TRIGGER} |")
    L.append(f"| D8 domain (TF-IDF k=10) | {kw['v_domain']:.3f} | {kw['v_domain'] > C.CRAMER_V_TRIGGER} |")
    L.append(f"| D9 era (quarters) | {kw['v_era']:.3f} | {kw['v_era'] > C.CRAMER_V_TRIGGER} |")
    L.append(f"\n_D9: {kw['n_era_null']} rows null/unparseable `created_at`._\n")

    L.append(
        f"## Surgical figure\n\n`{kw['fig_path']}` — PC1 vs PC2 scatter of the surgical "
        f"remainder (30K sample).\n"
    )

    with path.open("a") as fh:
        fh.write("\n".join(L))


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    grp = ap.add_mutually_exclusive_group()
    grp.add_argument(
        "--tight-only", action="store_true",
        help="SURGICAL cut: exclude only the 9 tight farm islands (0-7,9); retain island 8.",
    )
    grp.add_argument(
        "--all-islands", action="store_true",
        help="(default) exclude all 10 island balls (the 2026-07-09 14:55 cut).",
    )
    args = ap.parse_args()
    raise SystemExit(main(tight_only=args.tight_only))
