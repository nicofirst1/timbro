"""WS3 step 2 — descriptives + organic-vs-slop separability probe.

Reads ``paper/data/features.parquet`` (step-1 output), restricts to the canonical
analysis population, and produces:

  - per-source and per-platform median/IQR summary stats for every numeric feature;
  - distribution figures for a pre-registered headline feature set (organic vs. slop);
  - a logistic-regression separability probe reported as three ROC-AUCs (FULL,
    LENGTH-ONLY baseline, FULL-minus-LENGTH) with per-fold sd — the mandatory
    length-confound guard from the PRE-REG (experiment-discipline §2 / D5);
  - the top-10 most-separating features (|coef| on standardized inputs);
  - a manifest via the WS1 provenance conventions.

Everything the PRE-REG in ``paper/code/ws3/LEDGER.md`` (2026-07-09 11:22) fixes is a
constant here — nothing is decided at runtime. This is a validation/descriptive step,
not a confirmatory RQ test: no inferential statistic, "Observed"-level claims only.

Run (from repo root):
  uv run --with-requirements paper/code/ws3/requirements.txt \
      python paper/code/ws3/step2_descriptives/descriptives.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

# WS1 provenance helpers. __file__ = paper/code/ws3/step2_descriptives/descriptives.py
sys.path.append(str(Path(__file__).resolve().parents[2] / "ws1"))
from _manifest import (  # noqa: E402
    SEED,
    data_dir,
    repo_root,
    sha256_file,
    write_manifest,
)

# --- pre-registered constants (LEDGER 2026-07-09 11:22) -----------------------

SEED_CV = SEED  # 42 (D1) — StratifiedKFold shuffle
N_FOLDS = 5

INPUT_NAME = "features.parquet"

# Carry/identity + JSON-string columns that are NOT model features.
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

# Positive class vs organic (both under is_canonical == "true").
SLOP_SOURCE = "slop_stub"
ORGANIC_SOURCES = ("skill_diffs", "graph_of_skills")

# Length family — raw document-size counts (pre-registered).
LENGTH_FEATURES = [
    "desc_tokens",
    "desc_unique_tokens",
    "desc_characters",
    "desc_sentences",
    "struct_line_count",
]

# Headline features for the distribution figures — one per family, named in PRE-REG.
HEADLINE_FEATURES = [
    "dict_imperative_ratio",
    "dict_hedge_per_1k",
    "dict_conditional_per_1k",
    "dict_second_person_per_1k",
    "read_flesch_kincaid_grade",
    "syn_mean_tree_depth",
    "coh_lemma_overlap_adj",
    "lex_mtld",
    "struct_code_char_ratio",
    "desc_tokens",
]

# Expected canonical class counts (verified pre-run; STOP if they drift — D7).
EXPECT_N_CANONICAL = 227407
EXPECT_N_SLOP = 5147

TOP_K_FEATURES = 10


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


def split_classes(df: pd.DataFrame) -> tuple[pd.DataFrame, np.ndarray]:
    """Canonical analysis population + binary label (1 = slop_stub, 0 = organic).

    ``is_canonical`` is a STRING column: canonical means the literal "true" (naive
    truthiness of "false" would keep every row). Rows with a non-null ``analyze_error``
    are dropped. Only slop_stub + organic sources survive.
    """
    canonical = df[df["is_canonical"] == "true"]
    canonical = canonical[canonical["analyze_error"].isnull()]
    keep = canonical["source"].isin((SLOP_SOURCE, *ORGANIC_SOURCES))
    canonical = canonical[keep].copy()
    y = (canonical["source"] == SLOP_SOURCE).astype(int).to_numpy()
    return canonical, y


def _pipeline():
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler

    # Median impute (per-fold, no leakage) -> standardize -> balanced logistic.
    return Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    class_weight="balanced", max_iter=1000, random_state=SEED_CV
                ),
            ),
        ]
    )


def cv_auc(X: np.ndarray, y: np.ndarray) -> tuple[float, float, list[float]]:
    """5-fold stratified CV ROC-AUC. Returns (mean, sd, per_fold_scores)."""
    from sklearn.model_selection import StratifiedKFold, cross_val_score

    skf = StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED_CV)
    scores = cross_val_score(_pipeline(), X, y, cv=skf, scoring="roc_auc")
    return float(scores.mean()), float(scores.std()), [float(s) for s in scores]


def fit_full_coefficients(
    X: np.ndarray, y: np.ndarray, feature_names: list[str]
) -> pd.DataFrame:
    """Refit the FULL pipeline on all rows; return |coef| ranking on standardized inputs."""
    pipe = _pipeline()
    pipe.fit(X, y)
    coefs = pipe.named_steps["clf"].coef_.ravel()
    out = pd.DataFrame({"feature": feature_names, "coef": coefs})
    out["abs_coef"] = out["coef"].abs()
    return out.sort_values("abs_coef", ascending=False).reset_index(drop=True)


# --- descriptives + figures + table -------------------------------------------

def _median_iqr(series: pd.Series) -> tuple[float, float, float]:
    return (
        float(series.median()),
        float(series.quantile(0.25)),
        float(series.quantile(0.75)),
    )


def _group_summary(df: pd.DataFrame, group_col: str, feats: list[str]) -> pd.DataFrame:
    """median/Q1/Q3 per group per feature, long form."""
    rows = []
    for gval, sub in df.groupby(group_col, dropna=False):
        n = len(sub)
        for f in feats:
            med, q1, q3 = _median_iqr(sub[f])
            rows.append(
                {group_col: "None" if pd.isna(gval) else gval, "n": n,
                 "feature": f, "median": med, "q1": q1, "q3": q3}
            )
    return pd.DataFrame(rows)


def _make_figures(df: pd.DataFrame, y: np.ndarray, figdir: Path) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figdir.mkdir(parents=True, exist_ok=True)
    organic = df[y == 0]
    slop = df[y == 1]
    paths = []

    # One grid figure with all headline features (robust percentile clipping for display).
    n = len(HEADLINE_FEATURES)
    ncols = 3
    nrows = (n + ncols - 1) // ncols
    fig, axes = plt.subplots(nrows, ncols, figsize=(4.2 * ncols, 3.0 * nrows))
    axes = np.atleast_1d(axes).ravel()
    for ax, feat in zip(axes, HEADLINE_FEATURES):
        o = organic[feat].dropna().to_numpy()
        s = slop[feat].dropna().to_numpy()
        both = np.concatenate([o, s])
        if both.size:
            lo, hi = np.percentile(both, [1, 99])
            if lo == hi:
                lo, hi = float(both.min()), float(both.max()) or 1.0
            bins = np.linspace(lo, hi, 40)
        else:
            bins = 40
        ax.hist(o, bins=bins, density=True, alpha=0.55, label="organic", color="#2c7fb8")
        ax.hist(s, bins=bins, density=True, alpha=0.55, label="slop_stub", color="#d95f0e")
        ax.set_title(feat, fontsize=9)
        ax.tick_params(labelsize=7)
    for ax in axes[n:]:
        ax.set_visible(False)
    axes[0].legend(fontsize=8)
    fig.suptitle("WS3 step 2 — headline feature distributions (canonical, organic vs. slop)",
                 fontsize=11)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    grid_path = figdir / "ws3_step2_headline_distributions.png"
    fig.savefig(grid_path, dpi=130)
    plt.close(fig)
    paths.append(str(grid_path.relative_to(repo_root())))
    return paths


def _write_table(
    table_path: Path,
    *,
    n_canonical: int,
    n_slop: int,
    n_organic: int,
    n_dropped_error: int,
    auc_full: tuple[float, float, list[float]],
    auc_length: tuple[float, float, list[float]],
    auc_minus: tuple[float, float, list[float]],
    ablated: tuple[str, float, float] | None,
    coef_rank: pd.DataFrame,
    source_summary: pd.DataFrame,
    platform_summary: pd.DataFrame,
) -> None:
    lines = []
    lines.append("# WS3 step 2 — descriptives + organic-vs-slop separability\n")
    lines.append(
        "Generated by `paper/code/ws3/step2_descriptives/descriptives.py`. Numbers here are the ones cited "
        "in the LEDGER RESULT — do not retype from elsewhere. Canonical analysis "
        "population only; the RQ2 install-labeled extras are excluded (see PRE-REG).\n"
    )
    lines.append("## Class counts (canonical, after dropping analyze_error rows)\n")
    lines.append(f"- canonical rows read: **{n_canonical}**")
    lines.append(f"- dropped for non-null `analyze_error`: **{n_dropped_error}**")
    lines.append(f"- slop_stub (positive): **{n_slop}**")
    lines.append(f"- organic (skill_diffs + graph_of_skills): **{n_organic}**")
    lines.append(f"- total in probe: **{n_slop + n_organic}**\n")

    lines.append("## Separability probe — ROC-AUC (5-fold stratified CV, seed 42)\n")
    lines.append("| model | features | AUC mean | AUC sd |")
    lines.append("|---|---|---|---|")
    lines.append(f"| FULL | all 130 numeric | {auc_full[0]:.4f} | {auc_full[1]:.4f} |")
    lines.append(
        f"| LENGTH-ONLY baseline | {len(LENGTH_FEATURES)} length counts "
        f"| {auc_length[0]:.4f} | {auc_length[1]:.4f} |"
    )
    lines.append(
        f"| FULL − LENGTH | 130 − {len(LENGTH_FEATURES)} = 125 "
        f"| {auc_minus[0]:.4f} | {auc_minus[1]:.4f} |"
    )
    lines.append("")
    lines.append(
        f"- FULL per-fold: {['%.4f' % s for s in auc_full[2]]}\n"
        f"- LENGTH-ONLY per-fold: {['%.4f' % s for s in auc_length[2]]}\n"
        f"- FULL−LENGTH per-fold: {['%.4f' % s for s in auc_minus[2]]}\n"
    )
    delta = auc_full[0] - auc_length[0]
    lines.append(
        f"**Length-confound reading:** FULL − LENGTH-ONLY AUC gap = {delta:+.4f}. "
        "If this gap is small the separability is largely length-driven (PRE-REG §2 guard).\n"
    )
    if ablated is not None:
        lines.append(
            f"**D5 ablation (FULL AUC > 0.99 fired):** dropping `{ablated[0]}` "
            f"(largest |coef|) gives AUC {ablated[1]:.4f} ± {ablated[2]:.4f}.\n"
        )
    else:
        lines.append("**D5 ablation:** not triggered (FULL CV AUC ≤ 0.99).\n")

    lines.append(f"## Top-{TOP_K_FEATURES} most-separating features (|coef|, standardized, FULL fit)\n")
    lines.append("| rank | feature | coef (standardized) | direction |")
    lines.append("|---|---|---|---|")
    for i, row in coef_rank.head(TOP_K_FEATURES).iterrows():
        direction = "→ slop" if row["coef"] > 0 else "→ organic"
        lines.append(f"| {i + 1} | `{row['feature']}` | {row['coef']:+.4f} | {direction} |")
    lines.append("")

    lines.append("## Per-source median [Q1, Q3] — headline features\n")
    lines.append(_summary_md(source_summary, "source"))
    lines.append("\n## Per-platform median [Q1, Q3] — headline features\n")
    lines.append(_summary_md(platform_summary, "platform"))
    lines.append(
        "\n_Full per-feature per-group median/IQR (all 130 numeric features) are in the "
        "companion CSVs `step2_source_summary.csv` / `step2_platform_summary.csv`._\n"
    )
    table_path.write_text("\n".join(lines))


def _summary_md(summary: pd.DataFrame, group_col: str) -> str:
    sub = summary[summary["feature"].isin(HEADLINE_FEATURES)]
    groups = list(dict.fromkeys(sub[group_col].tolist()))
    header = "| feature | " + " | ".join(str(g) for g in groups) + " |"
    sep = "|---|" + "|".join(["---"] * len(groups)) + "|"
    rows = [header, sep]
    for feat in HEADLINE_FEATURES:
        cells = []
        for g in groups:
            m = sub[(sub["feature"] == feat) & (sub[group_col] == g)]
            if len(m):
                r = m.iloc[0]
                cells.append(f"{r['median']:.3g} [{r['q1']:.3g}, {r['q3']:.3g}]")
            else:
                cells.append("—")
        rows.append(f"| `{feat}` | " + " | ".join(cells) + " |")
    return "\n".join(rows)


# --- driver -------------------------------------------------------------------

def main() -> int:
    root = repo_root()
    ddir = data_dir()
    in_path = ddir / INPUT_NAME
    figdir = root / "paper" / "figures"
    ws3 = root / "paper" / "code" / "ws3"
    table_path = ws3 / "step2_descriptives.md"

    print(f"[ws3:step2] reading {in_path}", flush=True)
    df = pq.read_table(in_path).to_pandas()
    n_canonical_raw = int((df["is_canonical"] == "true").sum())
    print(f"[ws3:step2] canonical rows: {n_canonical_raw}", flush=True)

    # STOP gate (D7): canonical count must match the manifest-derived expectation.
    assert n_canonical_raw == EXPECT_N_CANONICAL, (
        f"canonical {n_canonical_raw} != {EXPECT_N_CANONICAL} — corpus drift / D7, STOP"
    )

    # analyze_error rows dropped from the canonical population (any source).
    canon_mask = df["is_canonical"] == "true"
    n_dropped_error = int((canon_mask & df["analyze_error"].notnull()).sum())
    # slop rows dropped for an analyze_error, for the STOP-gate arithmetic.
    n_slop_dropped = int(
        (canon_mask & (df["source"] == SLOP_SOURCE) & df["analyze_error"].notnull()).sum()
    )

    canonical, y = split_classes(df)
    n_slop = int(y.sum())
    n_organic = int((y == 0).sum())
    print(
        f"[ws3:step2] probe: slop={n_slop} organic={n_organic} "
        f"dropped_error={n_dropped_error} (slop_dropped={n_slop_dropped})",
        flush=True,
    )
    # STOP gate (D7 / PRE-REG): surviving slop count must equal expected minus any
    # slop rows carrying an analyze_error. Drift here means the corpus changed under us.
    assert n_slop == EXPECT_N_SLOP - n_slop_dropped, (
        f"slop {n_slop} != {EXPECT_N_SLOP} - {n_slop_dropped} — STOP (PRE-REG drift)"
    )

    feats = numeric_feature_columns(canonical)
    assert set(LENGTH_FEATURES) <= set(feats), "length features missing from numeric set"
    assert set(HEADLINE_FEATURES) <= set(feats), "headline features missing from numeric set"
    print(f"[ws3:step2] numeric features: {len(feats)}", flush=True)

    X_full = canonical[feats].to_numpy(dtype=float)
    X_len = canonical[LENGTH_FEATURES].to_numpy(dtype=float)
    minus_feats = [f for f in feats if f not in set(LENGTH_FEATURES)]
    X_minus = canonical[minus_feats].to_numpy(dtype=float)

    print("[ws3:step2] CV: FULL ...", flush=True)
    auc_full = cv_auc(X_full, y)
    print(f"           FULL AUC {auc_full[0]:.4f} ± {auc_full[1]:.4f}", flush=True)
    print("[ws3:step2] CV: LENGTH-ONLY ...", flush=True)
    auc_length = cv_auc(X_len, y)
    print(f"           LENGTH AUC {auc_length[0]:.4f} ± {auc_length[1]:.4f}", flush=True)
    print("[ws3:step2] CV: FULL - LENGTH ...", flush=True)
    auc_minus = cv_auc(X_minus, y)
    print(f"           MINUS AUC {auc_minus[0]:.4f} ± {auc_minus[1]:.4f}", flush=True)

    # Coefficient ranking (FULL refit on all rows).
    coef_rank = fit_full_coefficients(X_full, y, feats)

    # D5 ablation guard: only if FULL CV AUC > 0.99.
    ablated = None
    if auc_full[0] > 0.99:
        drop = coef_rank.iloc[0]["feature"]
        keep = [f for f in feats if f != drop]
        Xk = canonical[keep].to_numpy(dtype=float)
        m, sd, _ = cv_auc(Xk, y)
        ablated = (drop, m, sd)
        print(f"[ws3:step2] D5 ablation drop {drop}: AUC {m:.4f} ± {sd:.4f}", flush=True)

    # Descriptives: full per-feature median/IQR per source and per platform.
    print("[ws3:step2] descriptives (source / platform) ...", flush=True)
    source_summary = _group_summary(canonical, "source", feats)
    platform_summary = _group_summary(canonical, "platform", feats)
    source_summary.to_csv(ws3 / "step2_source_summary.csv", index=False)
    platform_summary.to_csv(ws3 / "step2_platform_summary.csv", index=False)

    # Figures.
    print("[ws3:step2] figures ...", flush=True)
    fig_paths = _make_figures(canonical, y, figdir)

    # Table.
    _write_table(
        table_path,
        n_canonical=n_canonical_raw,
        n_slop=n_slop,
        n_organic=n_organic,
        n_dropped_error=n_dropped_error,
        auc_full=auc_full,
        auc_length=auc_length,
        auc_minus=auc_minus,
        ablated=ablated,
        coef_rank=coef_rank,
        source_summary=source_summary,
        platform_summary=platform_summary,
    )
    print(f"[ws3:step2] table -> {table_path.relative_to(root)}", flush=True)

    # Manifest — a small marker file is what we hash (the .md summary).
    write_manifest(
        table_path,
        source="ws3_step2_descriptives",
        inputs=[{"file": INPUT_NAME, "sha256": sha256_file(in_path)}],
        n_rows=n_slop + n_organic,
        packages=("scikit-learn", "pandas", "matplotlib", "numpy", "pyarrow"),
        extra={
            "analysis_population": "canonical only (is_canonical == 'true'), RQ2 extras excluded",
            "n_canonical": n_canonical_raw,
            "n_dropped_analyze_error": n_dropped_error,
            "n_slop_stub": n_slop,
            "n_organic": n_organic,
            "n_numeric_features": len(feats),
            "length_features": LENGTH_FEATURES,
            "headline_features": HEADLINE_FEATURES,
            "auc_full_mean": auc_full[0],
            "auc_full_sd": auc_full[1],
            "auc_full_folds": auc_full[2],
            "auc_length_only_mean": auc_length[0],
            "auc_length_only_sd": auc_length[1],
            "auc_length_only_folds": auc_length[2],
            "auc_full_minus_length_mean": auc_minus[0],
            "auc_full_minus_length_sd": auc_minus[1],
            "auc_full_minus_length_folds": auc_minus[2],
            "auc_full_minus_length_gap": auc_full[0] - auc_length[0],
            "d5_ablation": (
                None if ablated is None
                else {"dropped": ablated[0], "auc_mean": ablated[1], "auc_sd": ablated[2]}
            ),
            "top_features": coef_rank.head(TOP_K_FEATURES)[["feature", "coef"]].to_dict("records"),
            "figures": fig_paths,
            "cv_folds": N_FOLDS,
            "cv_seed": SEED_CV,
            "class_weight": "balanced",
            "null_policy": "median impute per-fold (SimpleImputer) inside the CV pipeline",
        },
    )
    print("[ws3:step2] manifest written under paper/code/ws1/manifests/", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
