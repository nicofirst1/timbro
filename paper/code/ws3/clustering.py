"""WS3 step 3 — RQ1 clustering / instruction dialects.

Reads ``paper/data/features.parquet`` (step-1 output), restricts to the *organic*
canonical analysis population (``is_canonical == "true"`` AND ``analyze_error`` null
AND ``source != "slop_stub"`` — slop is the D5 probe corpus, not an RQ1 ecosystem;
see PRE-REG), then runs the pre-registered Biber-style pipeline:

  standardize (median-impute -> z-score)
    -> PCA (retain >= 90% variance, D3)
    -> platform-stratified 50K discovery sample (D2, corpus > 100K)
    -> HDBSCAN(min_cluster_size=200) on the 50K sample (D3)
    -> k-means fallback if noise > 0.50 or non-noise clusters < 3 (D3)
    -> "no discrete dialects" declaration if best silhouette < 0.10 (D3)
    -> assign the remaining ~172K docs by nearest cluster centroid in PCA space
    -> name clusters by their most-deviant standardized-median features
    -> confound gates: D4 platform / D8 domain (TF-IDF k-means) / D9 era (quarters),
       each via Cramer's V with the pre-registered V > 0.6 re-cluster trigger.

Everything the PRE-REG in ``paper/code/ws3/LEDGER.md`` (2026-07-09 12:14) fixes is a
constant here — nothing is decided at runtime. This is an unsupervised, descriptive
structure-discovery step: "Observed"-level claims only, no inferential statistic.

Run (from repo root):
  uv run --with-requirements paper/code/ws3/requirements.txt \
      python paper/code/ws3/clustering.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

# WS1 provenance helpers. __file__ = paper/code/ws3/clustering.py
sys.path.append(str(Path(__file__).resolve().parents[1] / "ws1"))
from _manifest import (  # noqa: E402
    SEED,
    data_dir,
    repo_root,
    sha256_file,
    write_manifest,
)

# --- pre-registered constants (LEDGER 2026-07-09 12:14) -----------------------

SEED_ALL = SEED  # 42 (D1) — the 50K draw, TF-IDF k-means, k-means fallback

FEATURES_NAME = "features.parquet"
CORPUS_NAME = "corpus.parquet"  # D8 text + D9 created_at, joined by skill_id
OUTPUT_NAME = "rq1_cluster_assignments.parquet"

# Carry/identity + JSON-string columns that are NOT model features (same as step 2).
NON_FEATURE_COLUMNS = {
    "skill_id",
    "source",
    "platform",
    "near_dup_cluster_id",
    "is_canonical",
    "installs",
    "analyze_error",
    "frontmatter_json",
    "dict_plain_replacements_json",
}

SLOP_SOURCE = "slop_stub"  # EXCLUDED from RQ1 (D5 probe corpus, not an ecosystem)

# Expected population counts (verified pre-run; STOP if they drift — D7).
EXPECT_N_CANONICAL = 227407
EXPECT_N_ORGANIC = 222256  # canonical, error-dropped, non-slop

# D3 PCA / HDBSCAN / fallback.
PCA_VARIANCE_TARGET = 0.90
HDBSCAN_MIN_CLUSTER_SIZE = 200  # D3 verbatim
KMEANS_K_RANGE = range(4, 13)  # D3: k in {4..12}
SILHOUETTE_FLOOR = 0.10  # D3: below this -> "no discrete dialects"
NOISE_FALLBACK = 0.50  # D3: noise > 0.50 -> k-means
MIN_CLUSTERS = 3  # D3: < 3 non-noise clusters -> k-means

# D2 discovery sample.
SAMPLE_SIZE = 50000  # D2 verbatim
SILHOUETTE_SUBSAMPLE = 10000  # silhouette on a seeded sub-sample if the 50K is slow

# D8 domain proxy (TF-IDF k-means, k=10, seed 42 — D8 verbatim).
DOMAIN_K = 10
TFIDF_MAX_FEATURES = 20000
TFIDF_MIN_DF = 5

# Confound-gate trigger (D4/D8/D9 verbatim).
CRAMER_V_TRIGGER = 0.6

# Cluster naming.
TOP_DEVIANT_PER_CLUSTER = 8


# --- pure seams (unit-tested) -------------------------------------------------

def numeric_feature_columns(df: pd.DataFrame) -> list[str]:
    """All numeric columns that are model features (excludes carry / JSON columns)."""
    cols = []
    for c in df.columns:
        if c in NON_FEATURE_COLUMNS:
            continue
        if pd.api.types.is_numeric_dtype(df[c]):
            cols.append(c)
    return cols


def organic_canonical(df: pd.DataFrame) -> pd.DataFrame:
    """The RQ1 population: canonical, no analyze_error, non-slop.

    ``is_canonical`` is a STRING column: canonical means the literal "true" (naive
    truthiness of "false" would keep every row). Rows with a non-null ``analyze_error``
    are dropped. slop_stub is excluded (D5 probe corpus, not an RQ1 ecosystem).
    """
    canonical = df[df["is_canonical"] == "true"]
    canonical = canonical[canonical["analyze_error"].isnull()]
    canonical = canonical[canonical["source"] != SLOP_SOURCE]
    return canonical.copy()


def cramers_v(a: pd.Series, b: pd.Series) -> tuple[float, pd.DataFrame]:
    """Bias-corrected Cramer's V between two categorical series + the contingency table.

    Uses the Bergsma (2013) bias correction so large sparse tables are not inflated.
    Rows where either value is null are dropped pairwise (count reported by the caller).
    """
    from scipy.stats import chi2_contingency

    mask = a.notna() & b.notna()
    a2, b2 = a[mask], b[mask]
    table = pd.crosstab(a2, b2)
    if table.shape[0] < 2 or table.shape[1] < 2:
        return 0.0, table
    chi2 = chi2_contingency(table.to_numpy(), correction=False)[0]
    n = table.to_numpy().sum()
    phi2 = chi2 / n
    r, k = table.shape
    phi2corr = max(0.0, phi2 - (k - 1) * (r - 1) / (n - 1))
    rcorr = r - (r - 1) ** 2 / (n - 1)
    kcorr = k - (k - 1) ** 2 / (n - 1)
    denom = min(kcorr - 1, rcorr - 1)
    if denom <= 0:
        return 0.0, table
    return float(np.sqrt(phi2corr / denom)), table


def cluster_deviant_features(
    z_medians: pd.Series, top_k: int = TOP_DEVIANT_PER_CLUSTER
) -> list[tuple[str, float]]:
    """Name a cluster by |standardized median| — the most-deviant features.

    ``z_medians`` is the per-feature median of the cluster's rows AFTER global z-scoring,
    so 0 is the corpus median by construction. Returns the top_k (feature, signed_median)
    ranked by absolute deviation.
    """
    ranked = z_medians.reindex(z_medians.abs().sort_values(ascending=False).index)
    return [(str(f), float(v)) for f, v in ranked.head(top_k).items()]


def nearest_centroid_labels(
    pcs: np.ndarray, centroids: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Assign each row in ``pcs`` to the nearest centroid (Euclidean in PCA space).

    Returns (labels index into centroids, distance to the chosen centroid). Chunked so a
    ~172K x centroid distance matrix never materializes in full.
    """
    n = pcs.shape[0]
    labels = np.empty(n, dtype=int)
    dists = np.empty(n, dtype=float)
    step = 20000
    for i in range(0, n, step):
        block = pcs[i : i + step]
        d = np.linalg.norm(block[:, None, :] - centroids[None, :, :], axis=2)
        labels[i : i + step] = d.argmin(axis=1)
        dists[i : i + step] = d.min(axis=1)
    return labels, dists


# --- pipeline stages ----------------------------------------------------------

def standardize(X: np.ndarray):
    """Median-impute (fit on all organic canonical) then z-score. Returns (Z, imputer, scaler)."""
    from sklearn.impute import SimpleImputer
    from sklearn.preprocessing import StandardScaler

    imp = SimpleImputer(strategy="median")
    Xi = imp.fit_transform(X)
    scl = StandardScaler()
    Z = scl.fit_transform(Xi)
    return Z, imp, scl


def fit_pca(Z: np.ndarray):
    """PCA retaining >= 90% variance (D3). Fit on the 50K discovery sample."""
    from sklearn.decomposition import PCA

    full = PCA(random_state=SEED_ALL).fit(Z)
    cum = np.cumsum(full.explained_variance_ratio_)
    n_comp = int(np.searchsorted(cum, PCA_VARIANCE_TARGET) + 1)
    pca = PCA(n_components=n_comp, random_state=SEED_ALL).fit(Z)
    return pca, n_comp, float(cum[n_comp - 1])


def stratified_sample_idx(platform: pd.Series, size: int) -> np.ndarray:
    """Platform-stratified proportional sample of ``size`` rows (D2, seed 42).

    Null-platform rows (the 40 graph_of_skills) form their own stratum and are retained
    proportionally. Deterministic under SEED_ALL.
    """
    rng = np.random.default_rng(SEED_ALL)
    key = platform.fillna("__null__").to_numpy()
    idx_all = np.arange(len(key))
    n_total = len(key)
    picked = []
    # proportional allocation, largest-remainder so the total is exactly `size`
    groups = {}
    for g in pd.unique(key):
        groups[g] = idx_all[key == g]
    exact = {g: len(v) / n_total * size for g, v in groups.items()}
    floor = {g: int(np.floor(e)) for g, e in exact.items()}
    remainder = size - sum(floor.values())
    # distribute the remaining slots to the largest fractional parts (deterministic order)
    frac_order = sorted(exact, key=lambda g: (exact[g] - floor[g], g), reverse=True)
    for g in frac_order[:remainder]:
        floor[g] += 1
    for g, members in groups.items():
        take = min(floor[g], len(members))
        if take <= 0:
            continue
        chosen = rng.choice(members, size=take, replace=False)
        picked.append(chosen)
    out = np.concatenate(picked)
    out.sort()
    return out


def run_hdbscan(pcs: np.ndarray):
    """HDBSCAN(min_cluster_size=200) on PCA components (D3). Returns (labels, params)."""
    from sklearn.cluster import HDBSCAN

    model = HDBSCAN(min_cluster_size=HDBSCAN_MIN_CLUSTER_SIZE)
    labels = model.fit_predict(pcs)
    params = {
        "min_cluster_size": HDBSCAN_MIN_CLUSTER_SIZE,
        "min_samples": model.min_samples,  # None -> library default (== min_cluster_size)
        "metric": model.metric,
    }
    return labels, params


def silhouette_on_sample(pcs: np.ndarray, labels: np.ndarray) -> float | None:
    """Mean silhouette over non-noise points, on a seeded sub-sample if large."""
    from sklearn.metrics import silhouette_score

    mask = labels >= 0
    if mask.sum() < 2 or len(set(labels[mask])) < 2:
        return None
    pts, lab = pcs[mask], labels[mask]
    if len(pts) > SILHOUETTE_SUBSAMPLE:
        rng = np.random.default_rng(SEED_ALL)
        sub = rng.choice(len(pts), size=SILHOUETTE_SUBSAMPLE, replace=False)
        pts, lab = pts[sub], lab[sub]
        if len(set(lab)) < 2:
            return None
    return float(silhouette_score(pts, lab))


def kmeans_fallback(pcs: np.ndarray):
    """D3 fallback: k in {4..12} by best silhouette. Returns (labels, best_k, sil, per_k)."""
    from sklearn.cluster import KMeans

    per_k = {}
    best_k, best_sil, best_labels = None, -1.0, None
    for k in KMEANS_K_RANGE:
        km = KMeans(n_clusters=k, random_state=SEED_ALL, n_init=10)
        lab = km.fit_predict(pcs)
        sil = silhouette_on_sample(pcs, lab)
        per_k[k] = None if sil is None else round(sil, 4)
        if sil is not None and sil > best_sil:
            best_k, best_sil, best_labels = k, sil, lab
    return best_labels, best_k, best_sil, per_k


def centroids_from_labels(pcs: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, list[int]]:
    """Mean PCA coords of each non-noise cluster. Returns (centroids, ordered cluster ids)."""
    ids = sorted(int(c) for c in set(labels) if c >= 0)
    cents = np.vstack([pcs[labels == c].mean(axis=0) for c in ids])
    return cents, ids


# --- driver -------------------------------------------------------------------

def _load_domain_era(skill_ids: pd.Series, corpus_path: Path) -> pd.DataFrame:
    """Join D8 raw text + D9 created_at from corpus.parquet by skill_id."""
    ct = pq.read_table(
        corpus_path, columns=["skill_id", "text", "created_at"]
    ).to_pandas()
    ct = ct.drop_duplicates("skill_id", keep="first")
    idx = pd.DataFrame({"skill_id": skill_ids.to_numpy()})
    return idx.merge(ct, on="skill_id", how="left")


def assign_domain_labels(texts: pd.Series) -> tuple[np.ndarray, list[list[str]]]:
    """D8 domain proxy: TF-IDF k-means (k=10, seed 42) on content-word lemmas.

    Content-word lemmas approximated by a deterministic stop-word-filtered alphabetic
    tokenizer (recorded as a limitation in the PRE-REG). Returns (labels, top terms/cluster).
    """
    from sklearn.cluster import KMeans
    from sklearn.feature_extraction.text import TfidfVectorizer

    vec = TfidfVectorizer(
        stop_words="english",
        lowercase=True,
        token_pattern=r"(?u)\b[a-zA-Z]{3,}\b",
        max_features=TFIDF_MAX_FEATURES,
        min_df=TFIDF_MIN_DF,
    )
    tfidf = vec.fit_transform(texts.fillna("").to_numpy())
    km = KMeans(n_clusters=DOMAIN_K, random_state=SEED_ALL, n_init=10)
    labels = km.fit_predict(tfidf)
    terms = np.array(vec.get_feature_names_out())
    top_terms = []
    for c in range(DOMAIN_K):
        center = km.cluster_centers_[c]
        top_terms.append([str(t) for t in terms[center.argsort()[::-1][:12]]])
    return labels, top_terms


def _era_quarter(created_at: pd.Series) -> pd.Series:
    """D9: calendar-quarter bins from created_at (mixed-tz ISO strings)."""
    dt = pd.to_datetime(created_at, errors="coerce", utc=True)
    return dt.dt.to_period("Q").astype("string")


def main() -> int:
    root = repo_root()
    ddir = data_dir()
    feats_path = ddir / FEATURES_NAME
    corpus_path = ddir / CORPUS_NAME
    figdir = root / "paper" / "figures"
    ws3 = root / "paper" / "code" / "ws3"
    out_path = ddir / OUTPUT_NAME
    summary_path = ws3 / "step3_clusters.md"

    print(f"[ws3:step3] reading {feats_path}", flush=True)
    df = pq.read_table(feats_path).to_pandas()

    n_canonical_raw = int((df["is_canonical"] == "true").sum())
    assert n_canonical_raw == EXPECT_N_CANONICAL, (
        f"canonical {n_canonical_raw} != {EXPECT_N_CANONICAL} — corpus drift / D7, STOP"
    )

    pop = organic_canonical(df).reset_index(drop=True)
    n_pop = len(pop)
    print(f"[ws3:step3] organic canonical error-dropped: {n_pop}", flush=True)
    # STOP gate (D7 / PRE-REG): population must match the manifest-derived expectation.
    assert n_pop == EXPECT_N_ORGANIC, (
        f"organic population {n_pop} != {EXPECT_N_ORGANIC} — STOP (PRE-REG drift / D7)"
    )
    assert (pop["source"] != SLOP_SOURCE).all(), "slop leaked into RQ1 population — STOP"

    feats = numeric_feature_columns(pop)
    print(f"[ws3:step3] numeric features: {len(feats)}", flush=True)
    X = pop[feats].to_numpy(dtype=float)

    # Standardize on the full organic canonical set (unsupervised — no leakage risk).
    Z, _imp, _scl = standardize(X)
    zdf = pd.DataFrame(Z, columns=feats)
    dropped_zero_var = [f for f in feats if float(np.nanstd(zdf[f])) == 0.0]
    if dropped_zero_var:
        print(f"[ws3:step3] dropping zero-variance cols: {dropped_zero_var}", flush=True)
        feats = [f for f in feats if f not in set(dropped_zero_var)]
        zdf = zdf[feats]
        Z = zdf.to_numpy()

    # D2: platform-stratified 50K discovery sample (corpus > 100K).
    assert n_pop > 100000, "population <= 100K — D2 sample would not apply; STOP + reconsider"
    sample_idx = stratified_sample_idx(pop["platform"], SAMPLE_SIZE)
    print(
        f"[ws3:step3] D2 sample: {len(sample_idx)} rows "
        f"(platform strata: {pop.iloc[sample_idx]['platform'].fillna('null').value_counts().to_dict()})",
        flush=True,
    )
    Z_sample = Z[sample_idx]

    # PCA fit on the discovery sample; project the whole population.
    pca, n_comp, cum_var = fit_pca(Z_sample)
    pcs_sample = pca.transform(Z_sample)
    pcs_all = pca.transform(Z)
    print(f"[ws3:step3] PCA: {n_comp} comps -> {cum_var:.4f} cum variance", flush=True)

    # D3: HDBSCAN on the discovery sample.
    labels_sample, hdb_params = run_hdbscan(pcs_sample)
    non_noise = sorted(int(c) for c in set(labels_sample) if c >= 0)
    noise_frac = float((labels_sample < 0).mean())
    sil_hdb = silhouette_on_sample(pcs_sample, labels_sample)
    print(
        f"[ws3:step3] HDBSCAN: {len(non_noise)} clusters, noise {noise_frac:.3f}, "
        f"silhouette {sil_hdb}",
        flush=True,
    )

    # D3 fallback trigger: noise > 0.50 OR non-noise clusters < 3.
    method = "hdbscan"
    kmeans_per_k = None
    best_k = None
    silhouette = sil_hdb
    no_dialects = False
    trigger_fired = noise_frac > NOISE_FALLBACK or len(non_noise) < MIN_CLUSTERS
    hdbscan_prefallback = {
        "n_clusters": len(non_noise),
        "noise_fraction": noise_frac,
        "silhouette": sil_hdb,
        "trigger_fired": trigger_fired,
    }
    if trigger_fired:
        print(
            f"[ws3:step3] D3 fallback fired (noise {noise_frac:.3f} > {NOISE_FALLBACK} "
            f"or clusters {len(non_noise)} < {MIN_CLUSTERS}) -> k-means",
            flush=True,
        )
        method = "kmeans"
        labels_sample, best_k, silhouette, kmeans_per_k = kmeans_fallback(pcs_sample)
        non_noise = sorted(int(c) for c in set(labels_sample))
        noise_frac = 0.0
        print(f"[ws3:step3] k-means best k={best_k}, silhouette {silhouette}", flush=True)
        # D3: best silhouette < 0.10 -> "no discrete dialects".
        if silhouette is None or silhouette < SILHOUETTE_FLOOR:
            no_dialects = True
            print(
                f"[ws3:step3] best silhouette {silhouette} < {SILHOUETTE_FLOOR} "
                "-> NO DISCRETE DIALECTS (D3); report top-5 PCA axes as continuous dims",
                flush=True,
            )

    # Assign the full population to clusters by nearest centroid in PCA space.
    centroids, cluster_ids = centroids_from_labels(pcs_sample, labels_sample)
    assign_labels, assign_dist = nearest_centroid_labels(pcs_all, centroids)
    # map centroid-index back to cluster id
    cluster_id_arr = np.array(cluster_ids)
    full_cluster = cluster_id_arr[assign_labels]

    pop_out = pop[["skill_id", "source", "platform", "near_dup_cluster_id"]].copy()
    pop_out["cluster"] = full_cluster
    pop_out["centroid_distance"] = assign_dist
    pop_out["in_discovery_sample"] = False
    pop_out.loc[sample_idx, "in_discovery_sample"] = True

    # --- confound gates (on the full assigned set) ----------------------------
    print("[ws3:step3] confound gates (D4 / D8 / D9) ...", flush=True)
    de = _load_domain_era(pop["skill_id"], corpus_path)

    # D4 platform.
    v_platform, tab_platform = cramers_v(pop_out["cluster"], pop["platform"])
    d4_fired = v_platform > CRAMER_V_TRIGGER

    # D8 domain (TF-IDF k-means k=10).
    print("[ws3:step3] D8 TF-IDF k-means domain proxy (k=10) ...", flush=True)
    domain_labels, domain_terms = assign_domain_labels(de["text"])
    pop_out["domain"] = domain_labels
    v_domain, tab_domain = cramers_v(pop_out["cluster"], pd.Series(domain_labels))
    d8_fired = v_domain > CRAMER_V_TRIGGER

    # D9 era (calendar quarters).
    era = _era_quarter(de["created_at"])
    pop_out["era"] = era.to_numpy()
    n_era_null = int(era.isna().sum())
    v_era, tab_era = cramers_v(pop_out["cluster"], era)
    d9_fired = v_era > CRAMER_V_TRIGGER
    print(
        f"[ws3:step3] Cramer's V — platform {v_platform:.3f} (fired={d4_fired}), "
        f"domain {v_domain:.3f} (fired={d8_fired}), era {v_era:.3f} (fired={d9_fired})",
        flush=True,
    )

    # --- cluster naming (most-deviant standardized-median features) -----------
    # z-medians per cluster computed on the FULL assigned set (zdf aligns with pop rows).
    cluster_sizes = pop_out["cluster"].value_counts().sort_index()
    cluster_names = {}
    for c in cluster_ids:
        rows = pop_out.index[pop_out["cluster"] == c]
        z_med = zdf.loc[rows].median()
        cluster_names[int(c)] = cluster_deviant_features(z_med)

    # --- write outputs --------------------------------------------------------
    print(f"[ws3:step3] writing {out_path}", flush=True)
    pop_out.to_parquet(out_path, index=False)

    fig_paths = _make_figures(
        pcs_all, full_cluster, pop["platform"], figdir
    )

    top5_axes = _pca_axis_loadings(pca, feats, k_axes=5)
    _write_summary(
        summary_path,
        n_pop=n_pop,
        n_features=len(feats),
        dropped_zero_var=dropped_zero_var,
        n_comp=n_comp,
        cum_var=cum_var,
        sample_size=len(sample_idx),
        method=method,
        n_clusters=len(cluster_ids),
        noise_frac=noise_frac,
        silhouette=silhouette,
        best_k=best_k,
        kmeans_per_k=kmeans_per_k,
        no_dialects=no_dialects,
        cluster_sizes=cluster_sizes,
        cluster_names=cluster_names,
        hdb_params=hdb_params,
        hdbscan_prefallback=hdbscan_prefallback,
        v_platform=v_platform,
        v_domain=v_domain,
        v_era=v_era,
        d4_fired=d4_fired,
        d8_fired=d8_fired,
        d9_fired=d9_fired,
        tab_platform=tab_platform,
        tab_domain=tab_domain,
        tab_era=tab_era,
        domain_terms=domain_terms,
        n_era_null=n_era_null,
        top5_axes=top5_axes,
        assign_dist=assign_dist,
    )
    print(f"[ws3:step3] summary -> {summary_path.relative_to(root)}", flush=True)

    # --- manifest -------------------------------------------------------------
    write_manifest(
        out_path,
        source="ws3_step3_rq1_clustering",
        inputs=[
            {"file": FEATURES_NAME, "sha256": sha256_file(feats_path)},
            {"file": CORPUS_NAME, "sha256": sha256_file(corpus_path)},
        ],
        n_rows=len(pop_out),
        packages=("scikit-learn", "pandas", "numpy", "scipy", "matplotlib", "pyarrow"),
        extra={
            "analysis_population": "organic canonical, error-dropped, slop excluded (RQ1)",
            "n_organic_canonical": n_pop,
            "n_numeric_features": len(feats),
            "dropped_zero_variance": dropped_zero_var,
            "pca_variance_target": PCA_VARIANCE_TARGET,
            "pca_n_components": n_comp,
            "pca_cum_variance": cum_var,
            "d2_sample_size": len(sample_idx),
            "clustering_method": method,
            "hdbscan_params": hdb_params,
            "hdbscan_prefallback": hdbscan_prefallback,
            "n_clusters": len(cluster_ids),
            "noise_fraction": noise_frac,
            "silhouette": silhouette,
            "kmeans_best_k": best_k,
            "kmeans_silhouette_per_k": kmeans_per_k,
            "no_discrete_dialects": no_dialects,
            "cluster_sizes": {int(k): int(v) for k, v in cluster_sizes.items()},
            "confound_gates": {
                "d4_platform": {"cramers_v": v_platform, "fired": d4_fired},
                "d8_domain": {"cramers_v": v_domain, "fired": d8_fired, "k": DOMAIN_K},
                "d9_era": {"cramers_v": v_era, "fired": d9_fired, "n_era_null": n_era_null},
            },
            "figures": fig_paths,
            "seed": SEED_ALL,
        },
    )
    print("[ws3:step3] manifest written under paper/code/ws1/manifests/", flush=True)
    return 0


def _pca_axis_loadings(pca, feats, k_axes=5) -> list[list[tuple[str, float]]]:
    """Top |loading| features per PCA axis (for the D3 continuous-dimension report)."""
    out = []
    for i in range(min(k_axes, pca.components_.shape[0])):
        comp = pd.Series(pca.components_[i], index=feats)
        top = comp.reindex(comp.abs().sort_values(ascending=False).index).head(8)
        out.append([(str(f), float(v)) for f, v in top.items()])
    return out


def _make_figures(pcs_all, clusters, platform, figdir: Path) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figdir.mkdir(parents=True, exist_ok=True)
    paths = []
    rng = np.random.default_rng(SEED_ALL)
    n = len(clusters)
    # seeded subsample for the scatter (rendering ~222K points is wasteful).
    m = min(30000, n)
    sub = rng.choice(n, size=m, replace=False)

    # PCA scatter by cluster.
    fig, ax = plt.subplots(figsize=(7, 6))
    uniq = sorted(set(clusters))
    cmap = plt.get_cmap("tab10")
    for j, c in enumerate(uniq):
        mask = clusters[sub] == c
        ax.scatter(
            pcs_all[sub][mask, 0], pcs_all[sub][mask, 1],
            s=3, alpha=0.35, color=cmap(j % 10), label=f"cluster {c}",
        )
    ax.set_xlabel("PC1")
    ax.set_ylabel("PC2")
    ax.set_title("WS3 step 3 — RQ1 register clusters (PC1 vs PC2, 30K sample)")
    ax.legend(markerscale=3, fontsize=8)
    fig.tight_layout()
    p1 = figdir / "ws3_step3_pca_scatter.png"
    fig.savefig(p1, dpi=130)
    plt.close(fig)
    paths.append(str(p1.relative_to(repo_root())))

    # cluster x platform heatmap (row-normalized).
    dfp = pd.DataFrame({"cluster": clusters, "platform": platform.fillna("null").to_numpy()})
    tab = pd.crosstab(dfp["cluster"], dfp["platform"], normalize="index")
    fig, ax = plt.subplots(figsize=(1.2 * tab.shape[1] + 3, 0.5 * tab.shape[0] + 2))
    im = ax.imshow(tab.to_numpy(), aspect="auto", cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(range(tab.shape[1]))
    ax.set_xticklabels(tab.columns, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(tab.shape[0]))
    ax.set_yticklabels(tab.index, fontsize=8)
    for i in range(tab.shape[0]):
        for jj in range(tab.shape[1]):
            ax.text(jj, i, f"{tab.iloc[i, jj]:.2f}", ha="center", va="center",
                    color="white" if tab.iloc[i, jj] < 0.5 else "black", fontsize=7)
    ax.set_title("WS3 step 3 — cluster x platform (row-normalized)")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    p2 = figdir / "ws3_step3_cluster_platform_heatmap.png"
    fig.savefig(p2, dpi=130)
    plt.close(fig)
    paths.append(str(p2.relative_to(repo_root())))
    return paths


def _fmt_deviant(pairs: list[tuple[str, float]]) -> str:
    return ", ".join(f"`{f}` {v:+.2f}" for f, v in pairs)


def _crosstab_md(tab: pd.DataFrame, row_label: str) -> str:
    tab = tab.copy()
    header = f"| {row_label} \\\\ | " + " | ".join(str(c) for c in tab.columns) + " |"
    sep = "|---|" + "|".join(["---"] * len(tab.columns)) + "|"
    lines = [header, sep]
    for idx, row in tab.iterrows():
        lines.append(f"| {idx} | " + " | ".join(str(int(v)) for v in row) + " |")
    return "\n".join(lines)


def _write_summary(summary_path: Path, **kw) -> None:
    L = []
    L.append("# WS3 step 3 — RQ1 clustering / instruction dialects\n")
    L.append(
        "Generated by `paper/code/ws3/clustering.py`. Numbers here are the ones cited in "
        "the LEDGER RESULT — do not retype from elsewhere. Population = **organic canonical "
        "error-dropped** docs (slop_stub excluded per PRE-REG; it is the D5 probe corpus, "
        "not an RQ1 ecosystem). Unsupervised, descriptive: Observed-level claims only.\n"
    )
    L.append("## Population + preprocessing\n")
    L.append(f"- organic canonical error-dropped rows: **{kw['n_pop']}**")
    L.append(f"- numeric features: **{kw['n_features']}** "
             f"(dropped zero-variance: {kw['dropped_zero_var'] or 'none'})")
    L.append(f"- standardize: median-impute (no rows dropped) -> z-score, fit on all "
             f"{kw['n_pop']} rows")
    L.append(f"- **PCA (D3):** {kw['n_comp']} components retain "
             f"{kw['cum_var']:.4f} cumulative variance (target >= {PCA_VARIANCE_TARGET})")
    L.append(f"- **D2 discovery sample:** {kw['sample_size']} platform-stratified rows "
             f"(seed {SEED_ALL}); PCA fit + clustering run on the sample, the remaining "
             f"~{kw['n_pop'] - kw['sample_size']} rows assigned by nearest PCA centroid\n")

    L.append("## Clustering outcome (D3)\n")
    L.append(f"- method: **{kw['method']}** "
             + (f"(HDBSCAN params {kw['hdb_params']})" if kw['method'] == 'hdbscan'
                else f"(HDBSCAN fell back — noise/clusters trigger; k-means best k={kw['best_k']})"))
    pf = kw["hdbscan_prefallback"]
    L.append(f"- **HDBSCAN pre-fallback diagnostics:** {pf['n_clusters']} clusters, "
             f"noise fraction {pf['noise_fraction']:.3f}, silhouette {pf['silhouette']}, "
             f"D3 fallback trigger fired = **{pf['trigger_fired']}**")
    L.append(f"- non-noise clusters: **{kw['n_clusters']}**")
    L.append(f"- noise fraction (discovery sample): **{kw['noise_frac']:.3f}**")
    L.append(f"- silhouette (discovery sample): **{kw['silhouette']}**")
    if kw['kmeans_per_k'] is not None:
        L.append(f"- k-means silhouette per k: {kw['kmeans_per_k']}")
    if kw['no_dialects']:
        L.append("\n> **D3 verdict: NO DISCRETE DIALECTS** — best silhouette < "
                 f"{SILHOUETTE_FLOOR}. Reporting the top-5 PCA axes as continuous dimensions "
                 "instead of clusters (per D3; a finding, not a failure).\n")
    dist = np.asarray(kw["assign_dist"])
    L.append(f"- out-of-sample centroid distance: median {np.median(dist):.2f}, "
             f"p95 {np.percentile(dist, 95):.2f}, max {dist.max():.2f} "
             "(a large tail = docs far from every centroid)\n")

    L.append("## Cluster sizes (full assigned set)\n")
    L.append("| cluster | n |")
    L.append("|---|---|")
    for c, n in kw["cluster_sizes"].items():
        L.append(f"| {c} | {int(n)} |")
    L.append("")

    L.append("## Cluster names — top deviant features (signed standardized median)\n")
    L.append("Feature values are the cluster's per-feature median AFTER global z-scoring, so "
             "0 = corpus median. Sign shows direction; |value| shows deviation in SDs.\n")
    for c, pairs in kw["cluster_names"].items():
        L.append(f"- **cluster {c}:** {_fmt_deviant(pairs)}")
    L.append("")

    if kw["no_dialects"] or True:
        L.append("## Top-5 PCA axes (continuous register dimensions)\n")
        for i, axis in enumerate(kw["top5_axes"]):
            L.append(f"- **PC{i + 1}:** {_fmt_deviant(axis)}")
        L.append("")

    L.append("## Confound gates (Cramer's V, bias-corrected; trigger > 0.6)\n")
    L.append("| gate | proxy | Cramer's V | fired? | pre-registered consequence |")
    L.append("|---|---|---|---|---|")
    L.append(f"| **D4 platform** | `platform` | {kw['v_platform']:.3f} | "
             f"{kw['d4_fired']} | re-cluster within each platform, report both views |")
    L.append(f"| **D8 domain** | TF-IDF k-means k={DOMAIN_K} | {kw['v_domain']:.3f} | "
             f"{kw['d8_fired']} | re-cluster within the two largest domains |")
    L.append(f"| **D9 era** | `created_at` quarters | {kw['v_era']:.3f} | "
             f"{kw['d9_fired']} | re-cluster within the two largest eras |")
    L.append(f"\n_D9: {kw['n_era_null']} rows had null/unparseable `created_at` "
             "(excluded from the era gate only)._\n")

    L.append("### D4 cluster x platform (counts)\n")
    L.append(_crosstab_md(kw["tab_platform"], "cluster"))
    L.append("\n### D9 cluster x era (counts)\n")
    L.append(_crosstab_md(kw["tab_era"], "cluster"))
    L.append("\n### D8 domain proxy — top TF-IDF terms per domain cluster\n")
    for i, terms in enumerate(kw["domain_terms"]):
        L.append(f"- **domain {i}:** {', '.join(terms)}")
    L.append("\n### D8 cluster x domain (counts)\n")
    L.append(_crosstab_md(kw["tab_domain"], "cluster"))
    L.append("")

    L.append("## Heuristic-table mapping (original research report)\n")
    L.append(
        "The original-report dialect heuristics are imperative-dense / conditional-rich / "
        "narrative. A cluster maps onto one only if its deviant-feature signature matches "
        "(e.g. high `dict_imperative_ratio` -> imperative-dense; high "
        "`dict_conditional_per_1k` / `dict_conditional_clauses_per_sentence` -> conditional-rich; "
        "low imperative + high `desc_sentences` / narrative cohesion -> narrative). Where a "
        "cluster's signature does not match a heuristic label, that is stated rather than "
        "forced. See the deviant-feature lists above for the mapping evidence.\n"
    )

    summary_path.write_text("\n".join(L))


if __name__ == "__main__":
    raise SystemExit(main())
