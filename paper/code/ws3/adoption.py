"""WS3 step 4 — RQ2 adoption analysis (CONFIRMATORY).

Reads ``paper/data/features.parquet`` (the 9,686 install-labeled entry-level
representative rows, ADR-0010), joins the weekly-install outcome from
``paper/data/skillssh_weekly.parquet`` and age/stars/repo/frontmatter from
``paper/data/corpus.parquet`` (by ``skill_id``), then runs the pre-frozen RQ2 rules:

  primary outcome  log1p(installs_wk_mean)            (ADR-0007)
  feature family   dict_imperative_ratio, dict_hedge_per_1k,
                   read_flesch_kincaid_grade, syn_mean_tree_depth,
                   coh_lemma_overlap_adj               (ADR-0004, FROZEN — 5 features)
  covariates       log(desc_tokens), log1p(skill_age_days)  (always; ADR-0004 + 0007)
  fixed effects    platform                            (domain FE omitted — no labels, D8)
  SEs              cluster-robust (CR1) on near_dup_cluster_id  (ADR-0010 §4)
  correction       Benjamini-Hochberg q=0.10 over the 5 confirmatory features  (D6)

  + exploratory Spearman screen (130 features, BH q=0.10, labeled exploratory)
  + robustness: (a) log1p(total installs+1); (b) canonical-only; (c) stars single-skill repos
  + selection-bias check: labeled vs unlabeled organic canonical docs

Everything the PRE-REG in ``paper/code/ws3/LEDGER.md`` (2026-07-09 15:23) fixes is a
constant here — nothing is decided at runtime. This is the paper's confirmatory analysis:
a null is publishable and reported straight with the minimum detectable effect (D6).

Run (from repo root):
  uv run --with-requirements paper/code/ws3/requirements.txt \
      python paper/code/ws3/adoption.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import statsmodels.api as sm
from scipy import stats

# WS1 provenance helpers. __file__ = paper/code/ws3/adoption.py
sys.path.append(str(Path(__file__).resolve().parents[1] / "ws1"))
from _manifest import (  # noqa: E402
    SEED,
    data_dir,
    repo_root,
    sha256_file,
    write_manifest,
)

# --- pre-registered constants (LEDGER 2026-07-09 15:23) -----------------------

FEATURES_NAME = "features.parquet"
CORPUS_NAME = "corpus.parquet"
WEEKLY_NAME = "skillssh_weekly.parquet"
OUTPUT_NAME = "rq2_adoption_rows.parquet"

CRAWL_ANCHOR = pd.Timestamp("2026-07-08", tz="UTC")  # ADR-0007 age anchor

# ADR-0004 confirmatory feature family (FROZEN — 5 features, not open).
CONFIRMATORY_FEATURES = [
    "dict_imperative_ratio",
    "dict_hedge_per_1k",
    "read_flesch_kincaid_grade",
    "syn_mean_tree_depth",
    "coh_lemma_overlap_adj",
]

# Carry/identity + JSON columns that are NOT model features (same set as steps 2/3).
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

# Pre-registered N gate (ADR-0010 entry-level labeled population).
EXPECTED_LABELED = 9686
EXPECTED_CANONICAL = 5667
EXPECTED_NONCANONICAL = 4019

BH_Q = 0.10  # D6

_JOIN_KEY_RE = re.compile(r"[^a-z0-9]")
_FRONTMATTER_NAME_RE = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)


# --------------------------------------------------------------------- join-key seam


def join_key(s: str | None) -> str:
    """Loose install-join key (merge.py convention): lowercase, strip non-[a-z0-9]."""
    return _JOIN_KEY_RE.sub("", (s or "").lower())


def frontmatter_name(fm: str | None) -> str | None:
    """Parse the ``name:`` line from raw frontmatter YAML; strip matching quotes."""
    if not isinstance(fm, str) or not fm:
        return None
    m = _FRONTMATTER_NAME_RE.search(fm)
    if not m:
        return None
    val = m.group(1)
    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
        val = val[1:-1]
    return val or None


def outcome_join_key(repo: str | None, frontmatter_json: str | None) -> tuple | None:
    """Reconstruct the merge.py ``(owner, repo, name)`` loose key from a corpus row.

    Returns None when ``repo`` has no ``owner/repo`` shape (the merge.py convention;
    such rows never join to the skills.sh weekly table). This is the seam the unit
    test exercises — the load-bearing join between corpus rows and skillssh_weekly.
    """
    if not isinstance(repo, str) or "/" not in repo:
        return None
    owner, reponame = repo.split("/", 1)
    return (join_key(owner), join_key(reponame), join_key(frontmatter_name(frontmatter_json)))


# --------------------------------------------------------------------- stats helpers


def benjamini_hochberg(pvals: np.ndarray, q: float) -> np.ndarray:
    """Return the BH-adjusted p-values (same order as input); reject where adj <= q."""
    p = np.asarray(pvals, dtype=float)
    n = p.size
    order = np.argsort(p)
    ranked = p[order]
    adj = ranked * n / (np.arange(1, n + 1))
    # enforce monotonicity (step-up)
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0, 1)
    out = np.empty(n, dtype=float)
    out[order] = adj
    return out


def zscore(series: pd.Series) -> pd.Series:
    """Median-impute then z-score (population fit); constant column -> zeros."""
    filled = series.fillna(series.median())
    sd = filled.std(ddof=0)
    if sd == 0 or not np.isfinite(sd):
        return pd.Series(np.zeros(len(filled)), index=filled.index)
    return (filled - filled.mean()) / sd


# --------------------------------------------------------------------- load


def load_population() -> pd.DataFrame:
    """Load the 9,686 labeled representatives + joined outcome/age/stars.

    Asserts the pre-registered N and split (D7 drift gate) and the ~100% weekly join.
    """
    dd = data_dir()
    feat = pq.read_table(dd / FEATURES_NAME).to_pandas()
    lab = feat[feat["installs"].notna() & (feat["installs"].astype(str) != "")].copy()

    n = len(lab)
    n_canon = int((lab["is_canonical"] == "true").sum())
    n_noncanon = int((lab["is_canonical"] == "false").sum())
    n_sd = int((lab["source"] == "skill_diffs").sum())
    if not (n == EXPECTED_LABELED and n_sd == EXPECTED_LABELED
            and n_canon == EXPECTED_CANONICAL and n_noncanon == EXPECTED_NONCANONICAL):
        raise SystemExit(
            f"[STOP] labeled population drift (D7): n={n} (want {EXPECTED_LABELED}), "
            f"skill_diffs={n_sd}, canonical={n_canon} (want {EXPECTED_CANONICAL}), "
            f"non-canonical={n_noncanon} (want {EXPECTED_NONCANONICAL}). "
            "Record + consult user before proceeding."
        )

    # corpus.parquet: outcome-join name (raw frontmatter), age, stars, repo — by skill_id.
    corp = pq.read_table(
        dd / CORPUS_NAME,
        columns=["skill_id", "repo", "frontmatter_json", "created_at", "stars"],
    ).to_pandas()
    lab = lab.merge(corp, on="skill_id", how="left", suffixes=("", "_corp"))

    # weekly outcome via the loose merge.py key (per-key max on the weekly side).
    wk = pq.read_table(dd / WEEKLY_NAME).to_pandas()
    wk["_k"] = list(zip(wk["owner"].map(join_key), wk["repo"].map(join_key),
                        wk["skill"].map(join_key)))
    wk_lookup = wk.groupby("_k")["installs_wk_mean"].max()

    lab["_k"] = [outcome_join_key(r, f)
                 for r, f in zip(lab["repo"], lab["frontmatter_json_corp"])]
    lab["installs_wk_mean"] = lab["_k"].map(wk_lookup)

    n_matched = int(lab["installs_wk_mean"].notna().sum())
    lab.attrs["join_coverage"] = (n_matched, n)
    if n_matched < 0.95 * n:
        raise SystemExit(
            f"[STOP] weekly-join coverage {n_matched}/{n} < 95% — the merge.py key should "
            "reproduce ~9,686 matches; a large miss means a key/schema change under us. "
            "Record + consult user."
        )

    # age from first-commit date (corpus created_at) to the crawl anchor.
    ca = pd.to_datetime(lab["created_at"], errors="coerce", utc=True)
    lab["skill_age_days"] = (CRAWL_ANCHOR - ca).dt.total_seconds() / 86400.0

    # total-installs robustness outcome (corpus `installs`, the max total).
    lab["installs_total"] = pd.to_numeric(lab["installs"], errors="coerce")
    lab["stars_num"] = pd.to_numeric(lab["stars"], errors="coerce")
    return lab


# --------------------------------------------------------------------- regression


def _design(df: pd.DataFrame, feats: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    """z-scored confirmatory features + log-covariates + platform dummies -> (X, groups)."""
    X = pd.DataFrame(index=df.index)
    imputed = {}
    for f in feats:
        n_null = int(df[f].isna().sum())
        imputed[f] = n_null
        X[f] = zscore(df[f])
    X["log_desc_tokens"] = np.log(df["desc_tokens"].clip(lower=1))
    X["log1p_age"] = np.log1p(df["skill_age_days"].clip(lower=0))
    plat = pd.get_dummies(df["platform"].fillna("NA"), prefix="plat", drop_first=True)
    X = pd.concat([X, plat.astype(float)], axis=1)
    X = sm.add_constant(X, has_constant="add")
    X.attrs["imputed"] = imputed
    return X, df["near_dup_cluster_id"]


def fit_ols_cluster(y: pd.Series, X: pd.DataFrame, groups: pd.Series) -> sm.regression.linear_model.RegressionResultsWrapper:  # noqa: E501
    """OLS with CR1 cluster-robust SEs on the given groups (near_dup_cluster_id)."""
    g = groups.fillna("__none__").astype(str).values
    model = sm.OLS(y.values.astype(float), X.values.astype(float))
    return model.fit(cov_type="cluster", cov_kwds={"groups": g})


def confirmatory_table(res, X: pd.DataFrame, feats: list[str]) -> pd.DataFrame:
    """Per-feature coef + 95% CI + raw p + BH-adjusted p over the 5 (D6)."""
    names = list(X.columns)
    idx = [names.index(f) for f in feats]
    coef = res.params[idx]
    ci = res.conf_int()[idx]  # 95% by default
    p = res.pvalues[idx]
    bh = benjamini_hochberg(p, BH_Q)
    return pd.DataFrame(
        {
            "feature": feats,
            "coef": coef,
            "ci_low": ci[:, 0],
            "ci_high": ci[:, 1],
            "p_raw": p,
            "p_bh": bh,
            "bh_survives": bh <= BH_Q,
        }
    )


def min_detectable_effect(res, X: pd.DataFrame, feats: list[str]) -> pd.Series:
    """Two-sided 80%-power MDE per confirmatory feature (1.96+0.84)*SE, in outcome SD units."""
    names = list(X.columns)
    idx = [names.index(f) for f in feats]
    return pd.Series((1.96 + 0.84) * res.bse[idx], index=feats)


# --------------------------------------------------------------------- screens / checks


def spearman_screen(df: pd.DataFrame, feature_cols: list[str], y: pd.Series) -> pd.DataFrame:
    rows = []
    for f in feature_cols:
        x = df[f]
        mask = x.notna() & y.notna()
        if mask.sum() < 3 or x[mask].nunique() < 2:
            rho, p = np.nan, np.nan
        else:
            rho, p = stats.spearmanr(x[mask], y[mask])
        rows.append({"feature": f, "spearman_rho": rho, "p_raw": p, "n": int(mask.sum())})
    out = pd.DataFrame(rows)
    valid = out["p_raw"].notna()
    out["p_bh"] = np.nan
    out.loc[valid, "p_bh"] = benjamini_hochberg(out.loc[valid, "p_raw"].values, BH_Q)
    out["bh_survives"] = out["p_bh"] <= BH_Q
    return out.sort_values("spearman_rho", key=lambda s: s.abs(), ascending=False)


def selection_bias_table(feat_all: pd.DataFrame, labeled_ids: set) -> pd.DataFrame:
    """Labeled vs unlabeled organic canonical docs on length/platform/confirmatory features."""
    canon = feat_all[
        (feat_all["is_canonical"] == "true")
        & (feat_all["source"] != "slop_stub")
        & (feat_all["analyze_error"].isna())
    ].copy()
    canon["labeled"] = canon["skill_id"].isin(labeled_ids)
    metrics = ["desc_tokens", *CONFIRMATORY_FEATURES]
    rows = []
    for grp, sub in canon.groupby("labeled"):
        row = {"group": "labeled" if grp else "unlabeled", "n": len(sub)}
        for m in metrics:
            row[f"{m}_median"] = sub[m].median()
        rows.append(row)
    tbl = pd.DataFrame(rows)
    plat = (
        canon.groupby(["labeled", "platform"]).size().unstack(fill_value=0)
    )
    plat_share = plat.div(plat.sum(axis=1), axis=0)
    return tbl, plat_share


# --------------------------------------------------------------------- figures


def make_figures(df: pd.DataFrame, conf_tbl: pd.DataFrame, figdir: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figs = []
    # (1) confirmatory coefficient forest plot (primary outcome).
    fig, ax = plt.subplots(figsize=(7, 3.2))
    ypos = np.arange(len(conf_tbl))[::-1]
    ax.errorbar(
        conf_tbl["coef"], ypos,
        xerr=[conf_tbl["coef"] - conf_tbl["ci_low"], conf_tbl["ci_high"] - conf_tbl["coef"]],
        fmt="o", color="#333", ecolor="#888", capsize=3,
    )
    ax.axvline(0, color="crimson", lw=1, ls="--")
    ax.set_yticks(ypos)
    ax.set_yticklabels(conf_tbl["feature"])
    ax.set_xlabel("per-SD coef on log1p(installs_wk_mean)  (95% CI, CR1 cluster-robust)")
    ax.set_title("RQ2 confirmatory features — primary outcome")
    fig.tight_layout()
    p1 = figdir / "ws3_step4_confirmatory_forest.png"
    fig.savefig(p1, dpi=140)
    plt.close(fig)
    figs.append(p1)

    # (2) outcome distribution (log1p) with the all-zero mass annotated.
    fig, ax = plt.subplots(figsize=(7, 3.2))
    y = np.log1p(df["installs_wk_mean"].dropna())
    ax.hist(y, bins=50, color="#4477aa")
    n_zero = int((df["installs_wk_mean"] == 0).sum())
    ax.set_xlabel("log1p(installs_wk_mean)  (8-week window, single anchor 2026-07-08)")
    ax.set_ylabel("labeled skills")
    ax.set_title(f"RQ2 outcome — {int(df['installs_wk_mean'].notna().sum())} labeled "
                 f"({n_zero} all-zero series)")
    fig.tight_layout()
    p2 = figdir / "ws3_step4_outcome_hist.png"
    fig.savefig(p2, dpi=140)
    plt.close(fig)
    figs.append(p2)
    return figs


# --------------------------------------------------------------------- report


def fmt_ci(row) -> str:
    return f"{row['coef']:+.4f} [{row['ci_low']:+.4f}, {row['ci_high']:+.4f}]"


def render_report(ctx: dict) -> str:
    L = []
    A = L.append
    A("# WS3 step 4 — RQ2 adoption (CONFIRMATORY)\n")
    A("Generated by `paper/code/ws3/adoption.py` — do not hand-edit. Numbers are the run's;")
    A("the pre-registration is in `LEDGER.md` (2026-07-09 15:23). ADR-0004/0007/0010 bind.\n")

    n_match, n_pop = ctx["join_coverage"]
    A("## Join coverage\n")
    A(f"- RQ2 population (ADR-0010 entry-level labeled representatives): **{n_pop}** rows "
      f"({ctx['n_canonical']} canonical + {ctx['n_noncanonical']} non-canonical, all skill_diffs).")
    A(f"- Weekly outcome (`installs_wk_mean`) matched via the loose merge.py key: "
      f"**{n_match}/{n_pop} ({100*n_match/n_pop:.1f}%)**.")
    A(f"- Age (`skill_age_days`) from first-commit `created_at` to crawl anchor 2026-07-08: "
      f"{ctx['age_nonnull']}/{n_pop} non-null (median {ctx['age_median']:.1f} d).")
    A(f"- **Caveats (ADR-0007):** the weekly series is an **8-week single-anchor window** "
      f"(2026-07-08); **{ctx['n_zero_series']} labeled skills have an all-zero weekly series** "
      "(kept; log1p handles 0). Install-labeled skills are a curated skills.sh slice "
      "(~1.74% of the corpus) — coverage is RQ2's denominator (PLAN §6 selection risk).\n")

    A("## Confirmatory regression — primary outcome `log1p(installs_wk_mean)`\n")
    A("OLS, z-scored confirmatory features (per-SD effects) + `log(desc_tokens)` + "
      "`log1p(skill_age_days)` + platform FE; **CR1 cluster-robust SEs on `near_dup_cluster_id`** "
      f"({ctx['n_clusters']} clusters). BH q=0.10 over the 5 features (D6). "
      "**Domain FE omitted — corpus rows carry no domain labels (ADR-0006 dropped ClawHub "
      "categories); stated as a limitation per D8.**\n")
    A("| feature | per-SD coef [95% CI] | p (raw) | p (BH) | BH survives |")
    A("|---|---|---|---|---|")
    for _, r in ctx["conf_primary"].iterrows():
        A(f"| `{r['feature']}` | {fmt_ci(r)} | {r['p_raw']:.4f} | {r['p_bh']:.4f} | "
          f"{'YES' if r['bh_survives'] else 'no'} |")
    A(f"\n- Model: N={ctx['n_primary']}, R²={ctx['r2_primary']:.4f}. Covariates: "
      f"`log(desc_tokens)` {ctx['cov_len']}, `log1p(age)` {ctx['cov_age']} (coef [95% CI]).")
    n_surv = int(ctx["conf_primary"]["bh_survives"].sum())
    if n_surv == 0:
        A("- **BH survivors: NONE.** Report the null with minimum detectable effects (per-SD, "
          "two-sided 80% power):")
        for f, m in ctx["mde"].items():
            A(f"  - `{f}`: MDE ≈ {m:.4f} outcome-SD-log units per feature-SD.")
    else:
        A(f"- **BH survivors: {n_surv}/5.**")
    A("")

    A("## Robustness reruns (pre-registered)\n")
    A("### (a) outcome `log1p(total installs + 1)`\n")
    A("| feature | per-SD coef [95% CI] | p (BH) | BH survives |")
    A("|---|---|---|---|")
    for _, r in ctx["conf_total"].iterrows():
        A(f"| `{r['feature']}` | {fmt_ci(r)} | {r['p_bh']:.4f} | "
          f"{'YES' if r['bh_survives'] else 'no'} |")
    A(f"\n(N={ctx['n_total']})\n")

    A("### (b) canonical-only population (ADR-0010 sensitivity, 5,667 entries)\n")
    A("| feature | per-SD coef [95% CI] | p (BH) | BH survives |")
    A("|---|---|---|---|")
    for _, r in ctx["conf_canon"].iterrows():
        A(f"| `{r['feature']}` | {fmt_ci(r)} | {r['p_bh']:.4f} | "
          f"{'YES' if r['bh_survives'] else 'no'} |")
    A(f"\n(N={ctx['n_canon']}. A sign flip vs the full set would indicate cluster/fork "
      "structure drives the result.)\n")

    A("### (c) stars on single-skill repos\n")
    A(ctx["stars_note"])
    if ctx.get("conf_stars") is not None:
        A("\n| feature | per-SD coef [95% CI] | p (BH) | BH survives |")
        A("|---|---|---|---|")
        for _, r in ctx["conf_stars"].iterrows():
            A(f"| `{r['feature']}` | {fmt_ci(r)} | {r['p_bh']:.4f} | "
              f"{'YES' if r['bh_survives'] else 'no'} |")
    A("")

    A("## Exploratory Spearman screen (130 features, BH q=0.10 — EXPLORATORY, not headline)\n")
    A("Per D6 these are exploratory and must NOT be promoted to headline claims. Top 15 by |ρ|:\n")
    A("| feature | Spearman ρ | p (BH) | BH survives | confirmatory? |")
    A("|---|---|---|---|---|")
    conf_set = set(CONFIRMATORY_FEATURES)
    for _, r in ctx["screen"].head(15).iterrows():
        A(f"| `{r['feature']}` | {r['spearman_rho']:+.4f} | "
          f"{r['p_bh']:.4g} | {'YES' if r['bh_survives'] else 'no'} | "
          f"{'*' if r['feature'] in conf_set else ''} |")
    A(f"\n- BH-surviving screens (of 130): {int(ctx['screen']['bh_survives'].sum())}.")
    A("- Confirmatory features' screen ρ (highlighted, but confirmatory inference is the "
      "regression + BH-over-5, not this screen):")
    for _, r in ctx["screen"][ctx["screen"]["feature"].isin(conf_set)].iterrows():
        A(f"  - `{r['feature']}`: ρ={r['spearman_rho']:+.4f}, p_BH={r['p_bh']:.4g}")
    A("")

    A("## Selection-bias check (labeled vs unlabeled organic canonical docs — WS1 risk item)\n")
    sb = ctx["selbias"]
    A("| " + " | ".join(sb.columns) + " |")
    A("|" + "|".join(["---"] * len(sb.columns)) + "|")
    for _, r in sb.iterrows():
        A("| " + " | ".join(
            f"{v:.4g}" if isinstance(v, float) else str(v) for v in r.tolist()) + " |")
    A("\n**Platform share (row-normalized):**\n")
    ps = ctx["selbias_plat"].round(3)
    A("| group | " + " | ".join(str(c) for c in ps.columns) + " |")
    A("|" + "|".join(["---"] * (len(ps.columns) + 1)) + "|")
    for idx, r in ps.iterrows():
        label = "labeled" if idx else "unlabeled"
        A(f"| {label} | " + " | ".join(f"{v:.3f}" for v in r.tolist()) + " |")
    A("")

    A("## Calibrated summary\n")
    A(ctx["summary"])
    A("")
    return "\n".join(L)


# --------------------------------------------------------------------- main


def main() -> None:
    figdir = repo_root() / "paper" / "figures"
    figdir.mkdir(parents=True, exist_ok=True)

    df = load_population()
    feat_all = pq.read_table(data_dir() / FEATURES_NAME).to_pandas()
    labeled_ids = set(df["skill_id"])

    feature_cols = [c for c in feat_all.columns if c not in NON_FEATURE_COLUMNS
                    and pd.api.types.is_numeric_dtype(feat_all[c])]

    ctx: dict = {}
    ctx["join_coverage"] = df.attrs["join_coverage"]
    ctx["n_canonical"] = int((df["is_canonical"] == "true").sum())
    ctx["n_noncanonical"] = int((df["is_canonical"] == "false").sum())
    ctx["age_nonnull"] = int(df["skill_age_days"].notna().sum())
    ctx["age_median"] = float(df["skill_age_days"].median())
    ctx["n_clusters"] = int(df["near_dup_cluster_id"].dropna().nunique())

    # --- primary confirmatory regression -------------------------------------
    prim = df[df["installs_wk_mean"].notna()].copy()
    ctx["n_zero_series"] = int((prim["installs_wk_mean"] == 0).sum())
    y = np.log1p(prim["installs_wk_mean"])
    X, groups = _design(prim, CONFIRMATORY_FEATURES)
    res = fit_ols_cluster(y, X, groups)
    ctx["conf_primary"] = confirmatory_table(res, X, CONFIRMATORY_FEATURES)
    ctx["mde"] = min_detectable_effect(res, X, CONFIRMATORY_FEATURES)
    ctx["n_primary"] = int(len(prim))
    ctx["r2_primary"] = float(res.rsquared)
    names = list(X.columns)
    ctx["cov_len"] = (f"{res.params[names.index('log_desc_tokens')]:+.4f} "
                      f"[{res.conf_int()[names.index('log_desc_tokens')][0]:+.4f}, "
                      f"{res.conf_int()[names.index('log_desc_tokens')][1]:+.4f}]")
    ctx["cov_age"] = (f"{res.params[names.index('log1p_age')]:+.4f} "
                      f"[{res.conf_int()[names.index('log1p_age')][0]:+.4f}, "
                      f"{res.conf_int()[names.index('log1p_age')][1]:+.4f}]")

    # --- robustness (a) total installs ---------------------------------------
    tot = df[df["installs_total"].notna()].copy()
    yt = np.log1p(tot["installs_total"])
    Xt, gt = _design(tot, CONFIRMATORY_FEATURES)
    rt = fit_ols_cluster(yt, Xt, gt)
    ctx["conf_total"] = confirmatory_table(rt, Xt, CONFIRMATORY_FEATURES)
    ctx["n_total"] = int(len(tot))

    # --- robustness (b) canonical-only ---------------------------------------
    canon = prim[prim["is_canonical"] == "true"].copy()
    yc = np.log1p(canon["installs_wk_mean"])
    Xc, gc = _design(canon, CONFIRMATORY_FEATURES)
    rc = fit_ols_cluster(yc, Xc, gc)
    ctx["conf_canon"] = confirmatory_table(rc, Xc, CONFIRMATORY_FEATURES)
    ctx["n_canon"] = int(len(canon))

    # --- robustness (c) stars, single-skill repos ----------------------------
    df["_owner_repo"] = df["repo"].fillna("")
    repo_counts = df["_owner_repo"].value_counts()
    single_repos = set(repo_counts[repo_counts == 1].index) - {""}
    stars_pop = df[df["_owner_repo"].isin(single_repos) & df["stars_num"].notna()].copy()
    if len(stars_pop) >= 100 and stars_pop["near_dup_cluster_id"].dropna().nunique() >= 10:
        ys = np.log1p(stars_pop["stars_num"])
        Xs, gs = _design(stars_pop, CONFIRMATORY_FEATURES)
        rs = fit_ols_cluster(ys, Xs, gs)
        ctx["conf_stars"] = confirmatory_table(rs, Xs, CONFIRMATORY_FEATURES)
        ctx["stars_note"] = (
            f"Single-skill-repo labeled entries with `stars`: **{len(stars_pop)}**; "
            "outcome `log1p(stars)`, same RHS, CR1 cluster-robust SEs.")
    else:
        ctx["conf_stars"] = None
        ctx["stars_note"] = (
            f"Single-skill-repo labeled entries with `stars`: **{len(stars_pop)}** — "
            "too few / too few clusters for an informative cluster-robust regression; "
            "recorded here rather than over-claimed (ADR-0004 stars-on-single-skill-repos "
            "is a robustness outcome, not the primary).")

    # --- exploratory Spearman screen -----------------------------------------
    ctx["screen"] = spearman_screen(prim, feature_cols, y)

    # --- selection-bias check ------------------------------------------------
    selbias, plat_share = selection_bias_table(feat_all, labeled_ids)
    ctx["selbias"] = selbias
    ctx["selbias_plat"] = plat_share

    # --- calibrated summary --------------------------------------------------
    n_surv = int(ctx["conf_primary"]["bh_survives"].sum())
    surv_names = ctx["conf_primary"].loc[ctx["conf_primary"]["bh_survives"], "feature"].tolist()
    if n_surv == 0:
        summary = (
            f"RQ2 (confirmatory): of the 5 pre-frozen linguistic features, **NONE survive "
            f"BH q=0.10** for the primary outcome `log1p(installs_wk_mean)` (N={ctx['n_primary']}, "
            "cluster-robust on near_dup_cluster_id) after length + age covariates and platform "
            "FE. This is a **publishable null** — reported straight with per-feature MDEs above. "
            "Length and age carry the explainable adoption variance; the confirmatory linguistic "
            "features do not add detectable predictive signal at this coverage/window.")
    else:
        summary = (
            f"RQ2 (confirmatory): **{n_surv}/5** confirmatory features survive BH q=0.10 for the "
            f"primary outcome (survivors: {', '.join(surv_names)}), N={ctx['n_primary']}, "
            "cluster-robust on near_dup_cluster_id, after length + age covariates and platform FE. "
            "Effect sizes with CIs are in the table above; robustness reruns (total installs, "
            "canonical-only, stars) test durability.")
    summary += (
        " Hard limitations: domain FE omitted (no corpus domain labels, D8); 8-week single-anchor "
        f"outcome window ({ctx['n_zero_series']} all-zero series); labeled set is a curated ~1.74% "
        "skills.sh slice (selection-bias table above characterizes how it differs from the corpus).")
    ctx["summary"] = summary

    # --- figures + report + a small artifact table + manifest ----------------
    figs = make_figures(prim, ctx["conf_primary"], figdir)

    report_path = Path(__file__).resolve().parent / "step4_adoption.md"
    report_path.write_text(render_report(ctx))
    print(f"[report] {report_path.relative_to(repo_root())}")

    # persist the analysis rows (gitignored data artifact) for provenance + manifest hashing.
    out_cols = ["skill_id", "source", "platform", "near_dup_cluster_id", "is_canonical",
                "installs_wk_mean", "installs_total", "stars_num", "skill_age_days",
                "desc_tokens", *CONFIRMATORY_FEATURES]
    out = df[out_cols].copy()
    out_path = data_dir() / OUTPUT_NAME
    out.to_parquet(out_path, index=False)

    write_manifest(
        out_path,
        source="ws3_rq2_adoption",
        inputs=[
            {"name": FEATURES_NAME, "sha256": sha256_file(data_dir() / FEATURES_NAME)},
            {"name": WEEKLY_NAME, "sha256": sha256_file(data_dir() / WEEKLY_NAME)},
            {"name": CORPUS_NAME, "sha256": sha256_file(data_dir() / CORPUS_NAME)},
        ],
        n_rows=len(out),
        packages=["statsmodels", "scikit-learn", "pandas", "numpy", "scipy",
                  "matplotlib", "pyarrow"],
        extra={
            "seed": SEED,
            "crawl_anchor": "2026-07-08",
            "join_coverage_matched": ctx["join_coverage"][0],
            "join_coverage_population": ctx["join_coverage"][1],
            "n_all_zero_weekly_series": ctx["n_zero_series"],
            "primary_bh_survivors": surv_names,
            "primary_n": ctx["n_primary"],
            "primary_r2": ctx["r2_primary"],
            "report": "paper/code/ws3/step4_adoption.md",
            "figures": [str(p.relative_to(repo_root())) for p in figs],
        },
    )
    print(f"[done] RQ2 adoption — primary BH survivors: {surv_names or 'NONE'}")


if __name__ == "__main__":
    main()
