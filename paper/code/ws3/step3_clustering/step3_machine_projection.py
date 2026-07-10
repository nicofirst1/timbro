"""WS3 — ADR-0009 EXPLORATORY machine-cell projection probe.

Where do the 587 KNOWN-machine-authored docs (SkillFlow 582 across 11 LLMs +
Trace2Skill 5) land in the FROZEN step-3 cluster geometry?

This is **exploratory / descriptive only** (ADR-0009): no hypothesis test, no
inferential statistic, never a headline claim. It projects provably machine-generated
docs into the step-3 PCA space and reports where they fall — it does NOT label any
organic doc as machine- or human-authored (the organic corpus has no authorship
ground truth).

The step-3 pipeline is **reproduced by importing `clustering.py`'s seams** (no
reimplementation). Before projecting we assert the reproduction matches the persisted
`rq1_cluster_assignments.parquet.manifest.json` (10 HDBSCAN islands, noise 0.86308,
silhouette 0.6638, k-means best k=5, full sizes {0:108698,1:4,2:30342,3:218,4:82994}).
Any mismatch -> STOP.

Assignment rules (pre-registered, LEDGER 2026-07-09 13:17):
  - k-means: nearest of the 5 k-means centroids (same `nearest_centroid_labels` seam
    step-3 uses for the ~172K remainder).
  - HDBSCAN island: nearest of the 10 island centroids; "in" island i iff distance
    <= island i's own 90th-pct member radius, else "blob/noise".

Run (from repo root):
  uv run --with-requirements paper/code/ws3/requirements.txt \
      python paper/code/ws3/step3_clustering/step3_machine_projection.py
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

import clustering as C  # noqa: E402  reuse step-3 seams (no reimplementation)
from _manifest import (  # noqa: E402
    data_dir,
    repo_root,
    sha256_file,
    write_manifest,
)

MACHINE_NAME = "features_machine.parquet"
PROJ_OUTPUT_NAME = "step3_machine_projection.parquet"
TRACE2SKILL_PREFIX = "machine:trace2skill:"
ISLAND_RADIUS_PCT = 90  # pre-registered acceptance-ball percentile

# Persisted step-3 numbers to assert reproduction against (from the manifest).
EXPECT = {
    "n_pop": 222256,
    "pca_n_components": 62,
    "pca_cum_variance_4dp": 0.9027,
    "hdbscan_n_clusters": 10,
    "hdbscan_noise": 0.86308,
    "hdbscan_silhouette": 0.6638091411557737,
    "kmeans_best_k": 5,
    "kmeans_sizes": {0: 108698, 1: 4, 2: 30342, 3: 218, 4: 82994},
}


def _reproduce_step3(feats_path: Path):
    """Recompute the step-3 pipeline via clustering.py seams; assert it reproduces.

    Returns a dict of the fitted transforms + island/k-means geometry needed to project
    out-of-sample machine docs into the same space.
    """
    df = pq.read_table(feats_path).to_pandas()
    n_canonical_raw = int((df["is_canonical"] == "true").sum())
    assert n_canonical_raw == C.EXPECT_N_CANONICAL, (
        f"canonical {n_canonical_raw} != {C.EXPECT_N_CANONICAL} — corpus drift, STOP"
    )

    pop = C.organic_canonical(df).reset_index(drop=True)
    n_pop = len(pop)
    assert n_pop == EXPECT["n_pop"], f"organic pop {n_pop} != {EXPECT['n_pop']} — STOP"

    feats = C.numeric_feature_columns(pop)
    X = pop[feats].to_numpy(dtype=float)

    # standardize (impute + z-score) fit on ALL organic canonical — these transforms
    # are what we reuse to project machine docs (no refit).
    Z, imp, scl = C.standardize(X)
    zdf = pd.DataFrame(Z, columns=feats)
    dropped = [f for f in feats if float(np.nanstd(zdf[f])) == 0.0]
    assert dropped == [], f"unexpected zero-variance drop {dropped} — geometry drift, STOP"

    # D2 50K discovery sample; PCA fit on it.
    sample_idx = C.stratified_sample_idx(pop["platform"], C.SAMPLE_SIZE)
    Z_sample = Z[sample_idx]
    pca, n_comp, cum_var = C.fit_pca(Z_sample)
    assert n_comp == EXPECT["pca_n_components"], (
        f"PCA comps {n_comp} != {EXPECT['pca_n_components']} — STOP"
    )
    assert round(cum_var, 4) == EXPECT["pca_cum_variance_4dp"], (
        f"PCA cum var {cum_var:.4f} != {EXPECT['pca_cum_variance_4dp']} — STOP"
    )

    pcs_sample = pca.transform(Z_sample)
    pcs_all = pca.transform(Z)

    # HDBSCAN on the discovery sample (the "islands").
    labels_hdb, _params = C.run_hdbscan(pcs_sample)
    islands = sorted(int(c) for c in set(labels_hdb) if c >= 0)
    noise_frac = float((labels_hdb < 0).mean())
    sil_hdb = C.silhouette_on_sample(pcs_sample, labels_hdb)
    assert len(islands) == EXPECT["hdbscan_n_clusters"], (
        f"HDBSCAN islands {len(islands)} != {EXPECT['hdbscan_n_clusters']} — STOP"
    )
    assert round(noise_frac, 5) == EXPECT["hdbscan_noise"], (
        f"HDBSCAN noise {noise_frac:.5f} != {EXPECT['hdbscan_noise']} — STOP"
    )
    assert abs(sil_hdb - EXPECT["hdbscan_silhouette"]) < 1e-9, (
        f"HDBSCAN silhouette {sil_hdb} != {EXPECT['hdbscan_silhouette']} — STOP"
    )

    # k-means fallback (noise > 0.50 fired) — the step-3 partition.
    labels_km, best_k, sil_km, _per_k = C.kmeans_fallback(pcs_sample)
    assert best_k == EXPECT["kmeans_best_k"], (
        f"k-means best k {best_k} != {EXPECT['kmeans_best_k']} — STOP"
    )
    km_centroids, km_ids = C.centroids_from_labels(pcs_sample, labels_km)
    km_full_lab, _ = C.nearest_centroid_labels(pcs_all, km_centroids)
    km_full = np.array(km_ids)[km_full_lab]
    km_sizes = {int(k): int(v) for k, v in pd.Series(km_full).value_counts().sort_index().items()}
    assert km_sizes == EXPECT["kmeans_sizes"], (
        f"k-means full sizes {km_sizes} != {EXPECT['kmeans_sizes']} — STOP"
    )

    # island geometry: centroid + 90th-pct member radius, in the 62-comp PCA space.
    island_centroids = []
    island_radii = []
    for isl in islands:
        members = pcs_sample[labels_hdb == isl]
        c = members.mean(axis=0)
        d = np.linalg.norm(members - c, axis=1)
        island_centroids.append(c)
        island_radii.append(float(np.percentile(d, ISLAND_RADIUS_PCT)))
    island_centroids = np.vstack(island_centroids)
    island_radii = np.array(island_radii)

    # island sizes in the discovery sample (for context).
    island_sizes = {
        int(isl): int((labels_hdb == isl).sum()) for isl in islands
    }

    return {
        "pop": pop,
        "feats": feats,
        "imp": imp,
        "scl": scl,
        "pca": pca,
        "labels_hdb": labels_hdb,
        "sample_idx": sample_idx,
        "islands": islands,
        "island_centroids": island_centroids,
        "island_radii": island_radii,
        "island_sizes": island_sizes,
        "km_centroids": km_centroids,
        "km_ids": km_ids,
        "n_pop": n_pop,
    }


def _project_machine(feats: list[str], imp, scl, pca, mdf: pd.DataFrame) -> np.ndarray:
    """Impute+standardize (organic fit) then PCA-transform (organic fit) the machine docs."""
    missing = [c for c in feats if c not in mdf.columns]
    assert not missing, f"machine features missing columns {missing[:5]} — STOP"
    Xm = mdf[feats].to_numpy(dtype=float)
    Zm = scl.transform(imp.transform(Xm))
    return pca.transform(Zm)


def _assign_islands(pcs_m: np.ndarray, centroids: np.ndarray, radii: np.ndarray, islands):
    """Nearest island; 'in' iff distance <= that island's 90th-pct radius, else blob/noise.

    Returns (island_label array of ints with -1 = blob/noise, nearest_island_id,
    nearest_distance).
    """
    d = np.linalg.norm(pcs_m[:, None, :] - centroids[None, :, :], axis=2)
    nearest_idx = d.argmin(axis=1)  # ties -> lowest index == lowest island id (islands sorted)
    nearest_dist = d.min(axis=1)
    nearest_island = np.array(islands)[nearest_idx]
    within = nearest_dist <= radii[nearest_idx]
    label = np.where(within, nearest_island, -1)
    return label, nearest_island, nearest_dist


def _dist_table(series: pd.Series, order=None) -> str:
    vc = series.value_counts()
    if order is not None:
        vc = vc.reindex(order).fillna(0).astype(int)
    else:
        vc = vc.sort_index()
    total = int(vc.sum())
    lines = ["| value | n | % |", "|---|---|---|"]
    for k, v in vc.items():
        pct = 100.0 * v / total if total else 0.0
        lines.append(f"| {k} | {int(v)} | {pct:.1f}% |")
    return "\n".join(lines)


def main() -> int:
    root = repo_root()
    ddir = data_dir()
    feats_path = ddir / C.FEATURES_NAME
    machine_path = ddir / MACHINE_NAME
    corpus_path = ddir / C.CORPUS_NAME
    proj_out = ddir / PROJ_OUTPUT_NAME
    summary_md = WS3 / "step3_machine_projection.md"
    islands_md = ddir / "step3_islands_examples.md"

    print("[proj] reproducing step-3 geometry ...", flush=True)
    G = _reproduce_step3(feats_path)
    print(
        f"[proj] REPRODUCED: n_pop={G['n_pop']}, 62 PCA comps, 10 islands, "
        "k-means k=5, sizes match manifest.",
        flush=True,
    )

    # --- project machine docs -------------------------------------------------
    mdf = pq.read_table(machine_path).to_pandas()
    assert len(mdf) == 587, f"machine rows {len(mdf)} != 587 — STOP"
    pcs_m = _project_machine(G["feats"], G["imp"], G["scl"], G["pca"], mdf)

    # k-means assignment (nearest of 5 centroids).
    km_lab_idx, km_dist = C.nearest_centroid_labels(pcs_m, G["km_centroids"])
    km_assign = np.array(G["km_ids"])[km_lab_idx]

    # island assignment (nearest island + 90th-pct ball).
    isl_label, isl_nearest, isl_dist = _assign_islands(
        pcs_m, G["island_centroids"], G["island_radii"], G["islands"]
    )

    is_t2s = mdf["skill_id"].str.startswith(TRACE2SKILL_PREFIX).to_numpy()

    out = pd.DataFrame(
        {
            "skill_id": mdf["skill_id"].to_numpy(),
            "generator_model": mdf["generator_model"].to_numpy(),
            "domain": mdf["domain"].to_numpy(),
            "is_trace2skill": is_t2s,
            "kmeans_cluster": km_assign,
            "kmeans_centroid_distance": km_dist,
            "island": isl_label,  # -1 = blob/noise
            "island_nearest": isl_nearest,
            "island_nearest_distance": isl_dist,
        }
    )
    out.to_parquet(proj_out, index=False)
    print(f"[proj] wrote {proj_out.name} ({len(out)} rows)", flush=True)

    sf = out[~out["is_trace2skill"]]  # 582 SkillFlow
    t2s = out[out["is_trace2skill"]]  # 5 Trace2Skill
    assert len(sf) == 582 and len(t2s) == 5, f"split {len(sf)}/{len(t2s)} != 582/5 — STOP"

    # --- island-inspection file (UNCOMMITTED; raw text stays out of git) ------
    _write_islands_examples(islands_md, G, corpus_path, root)
    print(f"[proj] islands inspection -> {islands_md} (uncommitted)", flush=True)

    # --- committed projection summary (NO raw text) ---------------------------
    _write_projection_summary(summary_md, out, sf, t2s, G, root)
    print(f"[proj] summary -> {summary_md.relative_to(root)}", flush=True)

    # --- manifest -------------------------------------------------------------
    isl_dist_overall = out["island"].apply(
        lambda x: "blob/noise" if x == -1 else int(x)
    )
    write_manifest(
        proj_out,
        source="ws3_machine_projection_probe_adr0009_exploratory",
        inputs=[
            {"file": C.FEATURES_NAME, "sha256": sha256_file(feats_path)},
            {"file": MACHINE_NAME, "sha256": sha256_file(machine_path)},
            {"file": C.CORPUS_NAME, "sha256": sha256_file(corpus_path)},
        ],
        n_rows=len(out),
        packages=("scikit-learn", "pandas", "numpy", "scipy", "pyarrow"),
        extra={
            "adr": "0009",
            "exploratory": True,
            "note": "descriptive locator only — no hypothesis test, never a headline claim",
            "n_machine_docs": int(len(out)),
            "n_skillflow": int(len(sf)),
            "n_trace2skill": int(len(t2s)),
            "island_radius_percentile": ISLAND_RADIUS_PCT,
            "reproduction_verified": True,
            "kmeans_assignment_distribution": {
                int(k): int(v) for k, v in out["kmeans_cluster"].value_counts().sort_index().items()
            },
            "island_assignment_distribution": {
                str(k): int(v) for k, v in isl_dist_overall.value_counts().items()
            },
            "kmeans_dist_skillflow": {
                int(k): int(v) for k, v in sf["kmeans_cluster"].value_counts().sort_index().items()
            },
            "island_dist_skillflow_blobnoise": int((sf["island"] == -1).sum()),
            "island_sizes_discovery_sample": G["island_sizes"],
            "island_radii_90pct": {
                int(isl): round(float(r), 3)
                for isl, r in zip(G["islands"], G["island_radii"])
            },
            "seed": C.SEED_ALL,
        },
    )
    print("[proj] manifest written under paper/code/ws1/manifests/", flush=True)
    return 0


# By-eye characterizations of the 10 HDBSCAN islands (written from the uncommitted
# inspection file's example docs; committed here as pointers-only, no raw text). These
# are a human reading, deliberately not machine-derived.
ISLAND_CHARACTERIZATION = {
    0: "Template family (repo NeuralBlitz/Agent-Gateway): identical 'Advanced <DOMAIN> Skill' "
       "scaffold, domain noun swapped. Generator output, not a human voice.",
    1: "Template family (Sandeeprdy1729/skill_galaxy): 'Quantum Specialized Skill <N>' + "
       "boilerplate class, only the number changes.",
    2: "Code-dominant snippets — near-all fenced code, minimal prose (low prose NOUN/PUNCT, "
       "high code_char_ratio). Heterogeneous repos, united by being almost-all-code.",
    3: "Template family (skill_galaxy): 'Spatial Expert <N> represents an expert-level "
       "specialization…' + boilerplate class.",
    4: "Template family (zwright8/OpenClaw-Code): 'Why This Skill Exists / 6-step Guide / "
       "Required Deliverables', first-person 'We need this skill because…', swapped title.",
    5: "Template family (OpenClaw-Code): 'Why This Skill Exists / Operational Runbook "
       "(Preflight/Execution/Recovery/Handoff)', '<TASK> for nonprofit program delivery'.",
    6: "Template family (Composio/Rube MCP): '<TOOLKIT> Automation via Rube MCP', toolkit "
       "name swapped. High booster density. Mirrored across several repos.",
    7: "Template family (membranedev/application-skills): Membrane-CLI integration scaffold, "
       "platform name swapped. Directive second-person register.",
    8: "THE DIFFUSE, GENUINELY-DIVERSE island (loosest, 90th-pct radius 6.37 — ~7x the tight "
       "islands): real hand-written-looking skills with distinct voices/structures. NOT a "
       "template family. Where the 118 in-island machine docs land, and nearest island for "
       "most blob machine docs.",
    9: "Template family (skill_galaxy): '<TITLE> represents a critical competency in the "
       "<DOMAIN> domain…' + boilerplate class.",
}


def _island_summary_rows(G) -> list[dict]:
    """Per-island: size, top-5 deviant features, example skill_id + repo pointers (no text)."""
    pop = G["pop"]
    feats = G["feats"]
    labels_hdb = G["labels_hdb"]
    sample_idx = np.asarray(G["sample_idx"])
    Zpop = G["scl"].transform(G["imp"].transform(pop[feats].to_numpy(dtype=float)))
    zdf = pd.DataFrame(Zpop, columns=feats)
    ct = pq.read_table(
        (data_dir() / C.CORPUS_NAME), columns=["skill_id", "repo"]
    ).to_pandas().drop_duplicates("skill_id", keep="first").set_index("skill_id")

    rows = []
    for isl in G["islands"]:
        member_pop_idx = sample_idx[labels_hdb == isl]
        z_med = zdf.iloc[member_pop_idx].median()
        top5 = C.cluster_deviant_features(z_med, top_k=5)
        c = G["island_centroids"][G["islands"].index(isl)]
        pcs_members = G["pca"].transform(zdf.iloc[member_pop_idx].to_numpy())
        d = np.linalg.norm(pcs_members - c, axis=1)
        order = np.argsort(d)[:2]
        examples = []
        for oi in order:
            sid = pop.iloc[member_pop_idx[oi]]["skill_id"]
            repo = ct.loc[sid, "repo"] if sid in ct.index else "?"
            examples.append((sid, repo))
        rows.append(
            {
                "island": isl,
                "size": len(member_pop_idx),
                "radius": float(G["island_radii"][G["islands"].index(isl)]),
                "top5": top5,
                "examples": examples,
            }
        )
    return rows


def _write_projection_summary(path: Path, out, sf, t2s, G, root) -> None:
    L = []
    L.append("# WS3 — machine-cell projection probe (ADR-0009 EXPLORATORY)\n")
    L.append(
        "Generated by `paper/code/ws3/step3_clustering/step3_machine_projection.py`. **Exploratory / "
        "descriptive only** — no hypothesis test, no inferential statistic, and per ADR-0009 "
        "this **never becomes a headline claim**. It projects the 587 KNOWN-machine-authored "
        "docs (SkillFlow 582 across 11 LLMs + Trace2Skill 5) into the frozen step-3 cluster "
        "geometry and reports where they land. It does **not** label any organic doc as "
        "machine- or human-authored — the organic corpus has no authorship ground truth.\n"
    )
    L.append(
        "> Numbers here are cited in the LEDGER RESULT; do not retype from elsewhere. The "
        "step-3 geometry is reproduced by importing `clustering.py`'s seams and asserted "
        "against `rq1_cluster_assignments.parquet.manifest.json` before projecting.\n"
    )

    L.append("## Reproduction gate (asserted before projecting)\n")
    L.append("| quantity | value | matches manifest |")
    L.append("|---|---|---|")
    L.append(f"| organic canonical error-dropped pop | {G['n_pop']} | yes |")
    L.append("| PCA components (>=90% var) | 62 (0.9027) | yes |")
    L.append("| HDBSCAN islands / noise / silhouette | 10 / 0.86308 / 0.6638 | yes |")
    L.append("| k-means best k / full sizes | 5 / {0:108698,1:4,2:30342,3:218,4:82994} | yes |")
    L.append("")

    L.append("## Island geometry (10 HDBSCAN islands, discovery sample)\n")
    L.append("These are the tight islands the (a)/(b) hypothesis is about. Radius = 90th-pct "
             "member Euclidean distance to centroid (the acceptance ball for out-of-sample docs).\n")
    L.append("| island | discovery-sample size | 90th-pct radius |")
    L.append("|---|---|---|")
    for isl in G["islands"]:
        r = float(G["island_radii"][G["islands"].index(isl)])
        L.append(f"| {isl} | {G['island_sizes'][isl]} | {r:.2f} |")
    L.append("")

    L.append("## Where the 587 machine docs land\n")

    L.append("### k-means cluster (0–4) — nearest of the 5 step-3 centroids\n")
    L.append("**All 587:**\n")
    L.append(_dist_table(out["kmeans_cluster"]))
    L.append("\n**SkillFlow only (582):**\n")
    L.append(_dist_table(sf["kmeans_cluster"]))
    L.append("")

    L.append("### HDBSCAN island — nearest island within its 90th-pct ball, else blob/noise\n")
    isl_lbl = out["island"].apply(lambda x: "blob/noise" if x == -1 else f"island {int(x)}")
    L.append("**All 587:**\n")
    L.append(_dist_table(isl_lbl))
    sf_lbl = sf["island"].apply(lambda x: "blob/noise" if x == -1 else f"island {int(x)}")
    L.append("\n**SkillFlow only (582):**\n")
    L.append(_dist_table(sf_lbl))
    L.append("")

    L.append("## Per-generator-model breakdown (11 SkillFlow models)\n")
    L.append("k-means cluster distribution + island landing (in-island count / blob-noise "
             "count) per model. `island in` = doc fell within some island's 90th-pct ball.\n")
    L.append("| generator_model | n | k-means dist (0/1/2/3/4) | island in | blob/noise |")
    L.append("|---|---|---|---|---|")
    for m, g in sf.groupby("generator_model"):
        n = len(g)
        km = g["kmeans_cluster"].value_counts()
        km_str = "/".join(str(int(km.get(c, 0))) for c in range(5))
        n_in = int((g["island"] != -1).sum())
        n_blob = int((g["island"] == -1).sum())
        L.append(f"| `{m}` | {n} | {km_str} | {n_in} | {n_blob} |")
    L.append("")

    L.append("### Island landing detail per SkillFlow model (which islands, when in-island)\n")
    any_in = sf[sf["island"] != -1]
    if len(any_in) == 0:
        L.append("_No SkillFlow doc fell within any island's 90th-pct ball — all 582 land in "
                 "the blob/noise region (outside every tight island)._\n")
    else:
        L.append("| generator_model | island | n |")
        L.append("|---|---|---|")
        for (m, isl), g in any_in.groupby(["generator_model", "island"]):
            L.append(f"| `{m}` | island {int(isl)} | {len(g)} |")
        L.append("")

    L.append("## Trace2Skill (5 rows, reported separately — N too small for anything but a note)\n")
    L.append("| skill_id | k-means cluster | nearest island | dist | in island? |")
    L.append("|---|---|---|---|---|")
    for _, r in t2s.iterrows():
        in_isl = "blob/noise" if r["island"] == -1 else f"island {int(r['island'])}"
        L.append(
            f"| `{r['skill_id']}` | {int(r['kmeans_cluster'])} | "
            f"island {int(r['island_nearest'])} | {r['island_nearest_distance']:.2f} | {in_isl} |"
        )
    L.append("")

    L.append("## Island summary (sizes, deviant features, characterization, pointers)\n")
    L.append(
        "Characterizations are a **by-eye reading** of the example docs in the uncommitted "
        "`paper/data/step3_islands_examples.md` (raw text stays out of git per data-hygiene). "
        "Pointers are skill_id + repo only. Deviant features = per-feature median after global "
        "z-scoring (|value| = SDs from the corpus median).\n"
    )
    for r in _island_summary_rows(G):
        dev = ", ".join(f"`{f}` {v:+.2f}" for f, v in r["top5"])
        ptr = "; ".join(f"`{sid}` (`{repo}`)" for sid, repo in r["examples"])
        char = ISLAND_CHARACTERIZATION.get(r["island"], "")
        L.append(
            f"\n### Island {r['island']} — size {r['size']}, 90th-pct radius {r['radius']:.2f}\n"
        )
        L.append(f"- **deviant:** {dev}")
        L.append(f"- **looks like:** {char}")
        L.append(f"- **example pointers:** {ptr}")
    L.append("")

    # landing rollup for the reading
    n_blob = int((out["island"] == -1).sum())
    n_i8 = int((out["island"] == 8).sum())
    n_other_isl = int(((out["island"] != -1) & (out["island"] != 8)).sum())
    L.append("## Reading of the evidence (calibrated, exploratory — NOT a claim)\n")
    L.append(
        "_This is which direction the observed landing **leans**; it does not confirm either "
        "hypothesis (exploratory, ADR-0009 — this may never become a headline claim). The same "
        "wording is recorded in the LEDGER RESULT._\n"
    )
    L.append(
        f"The 10 tight HDBSCAN islands are, by eye, **bulk-generated template/generator "
        f"families** (islands 0,1,3,4,5,6,7,9 are one-scaffold-many-variants; island 2 is "
        f"code-only snippets) — with the sole exception of **island 8**, the loosest island "
        f"(radius {G['island_radii'][G['islands'].index(8)]:.2f}, ~{G['island_radii'][G['islands'].index(8)] / np.median([G['island_radii'][G['islands'].index(i)] for i in G['islands'] if i != 8]):.1f}x "
        f"the median tight-island radius), which holds genuinely diverse hand-written-looking "
        f"skills. The 587 known-machine docs land: **{n_blob} ({100*n_blob/len(out):.0f}%) in "
        f"blob/noise, {n_i8} ({100*n_i8/len(out):.0f}%) in island 8, {n_other_isl} in any "
        f"other tight island.**\n"
    )
    L.append(
        "**This leans toward a *refinement of* hypothesis (b), not (a).** The tightest, most "
        "template-like structure in the corpus is NOT where the known-machine docs sit — those "
        "tight islands are bulk-generated *organic-corpus* repos (template farms), a separate "
        "phenomenon from our machine cell. The known-machine docs behave like **generic, "
        "moderately-diverse prose**: they miss every crisp template island and pool in the "
        "diffuse island 8 / blob. So 'machine text is the more uniform thing' (b) is only true "
        "of *template-farm* generation; the *SkillFlow/Trace2Skill* machine text is diverse "
        "enough to look like ordinary blob writing. **Neither (a) nor (b) as stated is "
        "confirmed** — (a) is not supported (the tight islands are demonstrably templates, not "
        "human voices), and (b) is only half-supported (template farms are uniform, but our "
        "known-machine cell is not). Exploratory; N and geometry stated; no test run.\n"
    )

    path.write_text("\n".join(L))


def _write_islands_examples(path: Path, G, corpus_path: Path, root) -> None:
    """Human-readable island inspection (UNCOMMITTED — contains raw organic text).

    For each of the 10 HDBSCAN islands: discovery-sample size, top-5 deviant features
    (|standardized median|), and 3 example docs (repo, platform, skill_id, first ~30 lines).
    """
    pop = G["pop"]
    feats = G["feats"]
    labels_hdb = G["labels_hdb"]
    sample_idx = G["sample_idx"]

    # z-scored feature frame for deviant medians (organic fit).
    Zpop = G["scl"].transform(G["imp"].transform(pop[feats].to_numpy(dtype=float)))
    zdf = pd.DataFrame(Zpop, columns=feats)

    # map discovery-sample position -> pop row index
    sample_pop_idx = np.asarray(sample_idx)

    # corpus text join
    ct = pq.read_table(
        corpus_path, columns=["skill_id", "text", "repo", "platform"]
    ).to_pandas().drop_duplicates("skill_id", keep="first").set_index("skill_id")

    L = []
    L.append("# WS3 step-3 HDBSCAN islands — inspection (UNCOMMITTED)\n")
    L.append(
        "> **Do not commit.** Contains raw organic SKILL.md text (repo data-hygiene: feature "
        "vectors publish, raw text never). Generated by `step3_machine_projection.py` to help "
        "read what the 10 tight HDBSCAN islands actually *are* — so you can judge by eye "
        "whether the tight islands look like template/generator families (hypothesis b) or "
        "distinct human voices (hypothesis a).\n"
    )
    L.append(
        "Each island: its discovery-sample size, top-5 deviant features (per-feature median "
        "after global z-scoring, |value| = SDs from the corpus median), and 3 example docs "
        "(first ~30 lines each).\n"
    )

    for isl in G["islands"]:
        mask_sample = labels_hdb == isl
        member_pop_idx = sample_pop_idx[mask_sample]
        size = len(member_pop_idx)
        z_med = zdf.iloc[member_pop_idx].median()
        top5 = C.cluster_deviant_features(z_med, top_k=5)
        dev_str = ", ".join(f"`{f}` {v:+.2f}" for f, v in top5)

        L.append(f"\n---\n\n## Island {isl}  (discovery-sample size {size})\n")
        L.append(f"**Top-5 deviant features:** {dev_str}\n")
        L.append(f"**What this island looks like:** {ISLAND_CHARACTERIZATION.get(isl, '')}\n")

        # 3 examples closest to the island centroid (most representative).
        c = G["island_centroids"][G["islands"].index(isl)]
        pcs_members = G["pca"].transform(zdf.iloc[member_pop_idx].to_numpy())
        d = np.linalg.norm(pcs_members - c, axis=1)
        order = np.argsort(d)[:3]
        for rank, oi in enumerate(order, 1):
            pop_i = member_pop_idx[oi]
            sid = pop.iloc[pop_i]["skill_id"]
            row = ct.loc[sid] if sid in ct.index else None
            repo = row["repo"] if row is not None else "?"
            plat = row["platform"] if row is not None else "?"
            text = row["text"] if row is not None else ""
            head = "\n".join(str(text).splitlines()[:30])
            L.append(f"### Example {rank} — `{sid}`")
            L.append(f"- repo: `{repo}`")
            L.append(f"- platform: `{plat}`")
            L.append(f"- centroid distance: {d[oi]:.2f}\n")
            L.append("```markdown")
            L.append(head)
            L.append("```\n")

    path.write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
