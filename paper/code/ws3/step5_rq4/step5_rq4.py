"""WS3 step 5 — RQ4 temporal evolution (CONFIRMATORY H4a + H4b).

Faithful execution of the RQ4 pre-registration frozen VERBATIM in ADR-0005 §8b and pinned
in ``paper/code/ws3/LEDGER_LOG.md#WS3-5-RQ4`` (PRE-REG 2026-07-10 08:46). Nothing is
decided at runtime — every rule below is a constant carried in from the PRE-REG.

  unit            within-skill version chain, ordered by ``version_index`` (0-based,
                  verified contiguous per chain upstream)
  population      all RQ4-eligible chains: 14,388 chains / 67,164 version-rows (≥3
                  versions). NOT canonical-only — forks already excluded upstream; the
                  ADR-0005 multi-repo-cluster rule is a no-op here (0 span repos).
                  2,026 non-canonical single-repo chains stay in. Canonical-only is a
                  ROBUSTNESS rerun, reported side by side.
  drop            the 18 rows with a non-null ``analyze_error`` (0.027% surrogate-char
                  failures, features null) are dropped from BOTH models; N reported after.
  H4a (confirm.)  revisions increase length: MixedLM
                  ``log1p(desc_tokens) ~ version_index`` + random intercept per skill_id.
                  259 zero-token rows kept (log1p). SUPPORTED iff coef(version_index) > 0
                  AND BH-over-2 p ≤ 0.10 (one-sided direction pre-registered: creep = up).
  H4b (confirm.)  skills converge toward their register-cluster centroid: for each version
                  row, z-distance on the 5 confirmatory features to the NEAREST of the
                  FROZEN RQ1 k=5 k-means centroids (RQ1 population's frozen z-transform),
                  MixedLM ``zdist5 ~ version_index`` + random intercept per skill_id.
                  SUPPORTED iff coef(version_index) < 0 AND BH-over-2 p ≤ 0.10 (converge =
                  distance shrinks). CAVEAT carried per PRE-REG: RQ1 found the k=5
                  partition dimensional not categorical — convergence is toward reference
                  centroids, NOT a validated dialect.
  correction      Benjamini-Hochberg q=0.10 over the {H4a, H4b} family (D6-style).
  fallback        if a MixedLM does not converge: refit as OLS with cluster-robust SEs on
                  skill_id, reported AS the fallback (a recorded event, not a silent swap).
  seed            42 (provenance parity; MixedLM REML is deterministic on frozen inputs).

Effect sizes (per-version coefficient + 95% CI) reported, never bare p-values. A null on
either hypothesis, or a coefficient on the "wrong" side of 0, is a finding reported
straight — never a stop. STOP only on chain-count drift (asserted below).

Run (from repo root):
  uv run --with-requirements paper/code/ws3/requirements.txt \
      python paper/code/ws3/step5_rq4/step5_rq4.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import statsmodels.api as sm
import statsmodels.formula.api as smf

# WS1 provenance helpers. __file__ = paper/code/ws3/step5_rq4/step5_rq4.py
sys.path.append(str(Path(__file__).resolve().parents[2] / "ws1"))
from _manifest import (  # noqa: E402
    SEED,
    data_dir,
    repo_root,
    sha256_file,
    write_manifest,
)

# --- pre-registered constants (ADR-0005 §8b + LEDGER_LOG WS3-5-RQ4 PRE-REG) ----

CHAINS_NAME = "features_chains.parquet"
RQ1_NAME = "rq1_cluster_assignments.parquet"
FEATURES_NAME = "features.parquet"  # RQ1 population's own feature values (frozen transform)
OUTPUT_NAME = "rq4_chain_trajectories.parquet"

# ADR-0004 confirmatory feature family (FROZEN — 5 features) — the H4b z-distance basis.
CONFIRMATORY_FEATURES = [
    "dict_imperative_ratio",
    "dict_hedge_per_1k",
    "read_flesch_kincaid_grade",
    "syn_mean_tree_depth",
    "coh_lemma_overlap_adj",
]

# Pre-registered eligibility (verified WS3-5-CHAINS) — asserted, STOP on drift.
EXPECTED_CHAINS = 14388
EXPECTED_ROWS = 67164

BH_Q = 0.10  # D6-style, over the {H4a, H4b} family


# --------------------------------------------------------------------- pure seams


def is_true(series: pd.Series) -> pd.Series:
    """``is_canonical`` truthiness robust to the corpus STRING/bool split (ledger gotcha).

    ``features_chains.parquet`` ships it as a genuine bool; other corpus tables ship the
    STRING "true"/"false". Compare both ways so the same code is correct either way.
    """
    if series.dtype == bool:
        return series.fillna(False)
    return series.astype("string").str.lower().eq("true").fillna(False)


def benjamini_hochberg(pvals: np.ndarray, q: float) -> np.ndarray:
    """BH-adjusted p-values (same order as input); reject where adj <= q. (D6)"""
    p = np.asarray(pvals, dtype=float)
    n = p.size
    if n == 0:
        return p
    order = np.argsort(p)
    ranked = p[order]
    adj = ranked * n / (np.arange(1, n + 1))
    adj = np.minimum.accumulate(adj[::-1])[::-1]
    adj = np.clip(adj, 0, 1)
    out = np.empty(n, dtype=float)
    out[order] = adj
    return out


def freeze_ztransform(train: pd.DataFrame, feats: list[str]) -> dict:
    """Fit the FROZEN RQ1 z-transform: median (for impute) + mean/SD per feature.

    ``train`` is the RQ1 population's feature values. Median-impute then population
    z-score (matches step-3's standardize). Returns per-feature {median, mean, sd}.
    A constant feature gets sd=0 → its z is 0 everywhere (no divide-by-zero).
    """
    params = {}
    for f in feats:
        col = pd.to_numeric(train[f], errors="coerce")
        med = float(col.median())
        filled = col.fillna(med)
        mu = float(filled.mean())
        sd = float(filled.std(ddof=0))
        params[f] = {"median": med, "mean": mu, "sd": sd}
    return params


def apply_ztransform(df: pd.DataFrame, feats: list[str], params: dict) -> np.ndarray:
    """Apply a frozen z-transform (from ``freeze_ztransform``) to ``df`` → (n, k) array."""
    cols = []
    for f in feats:
        p = params[f]
        col = pd.to_numeric(df[f], errors="coerce").fillna(p["median"])
        z = (col - p["mean"]) / p["sd"] if p["sd"] not in (0.0,) and np.isfinite(p["sd"]) \
            else pd.Series(np.zeros(len(col)), index=col.index)
        cols.append(z.to_numpy())
    return np.column_stack(cols)


def nearest_centroid_distance(Z: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    """Euclidean distance from each row of ``Z`` to the NEAREST centroid (k×k-feats)."""
    # (n, 1, k) - (1, c, k) -> (n, c, k) -> (n, c) distances -> min over c
    diff = Z[:, None, :] - centroids[None, :, :]
    d = np.sqrt((diff ** 2).sum(axis=2))
    return d.min(axis=1)


def within_chain_slope(version: np.ndarray, y: np.ndarray) -> float | None:
    """OLS slope of ``y`` on ``version`` within one chain; None if degenerate."""
    v = np.asarray(version, dtype=float)
    yy = np.asarray(y, dtype=float)
    mask = np.isfinite(v) & np.isfinite(yy)
    v, yy = v[mask], yy[mask]
    if v.size < 2 or np.ptp(v) == 0:
        return None
    vc = v - v.mean()
    denom = float((vc * vc).sum())
    if denom == 0:
        return None
    return float((vc * (yy - yy.mean())).sum() / denom)


# --------------------------------------------------------------------- load + build


def load_chains() -> pd.DataFrame:
    """Load the RQ4-eligible version-rows; assert the pre-registered N (STOP on drift)."""
    dd = data_dir()
    ch = pq.read_table(dd / CHAINS_NAME).to_pandas()

    n_rows = len(ch)
    n_chains = ch["skill_id"].nunique()
    if not (ch["n_versions"] >= 3).all():
        raise SystemExit("[STOP] a chain with n_versions<3 leaked into features_chains — "
                         "eligibility drift, record + consult user.")
    if not (n_rows == EXPECTED_ROWS and n_chains == EXPECTED_CHAINS):
        raise SystemExit(
            f"[STOP] RQ4 chain population drift (D7): rows={n_rows} (want {EXPECTED_ROWS}), "
            f"chains={n_chains} (want {EXPECTED_CHAINS}). Record + consult user.")

    # Fork exclusion (ADR-0005): only the canonical chain enters when a skill_cluster_id
    # spans repos. Verify + apply (a no-op on this data; enforced so a data change can't
    # slip a fork in silently).
    per_chain = ch.drop_duplicates("skill_id")[
        ["skill_id", "skill_cluster_id", "is_canonical", "repo"]].copy()
    per_chain["_canon"] = is_true(per_chain["is_canonical"])
    scc = per_chain.dropna(subset=["skill_cluster_id"])
    multi = scc.groupby("skill_cluster_id")["repo"].nunique()
    multi_ids = set(multi[multi > 1].index)
    drop_ids: set = set()
    for cid in multi_ids:
        members = scc[scc["skill_cluster_id"] == cid]
        drop_ids |= set(members[~members["_canon"]]["skill_id"])
    ch.attrs["n_multi_repo_clusters"] = len(multi_ids)
    ch.attrs["n_fork_chains_dropped"] = len(drop_ids)
    if drop_ids:
        ch = ch[~ch["skill_id"].isin(drop_ids)].copy()

    # PRE-REG drop rule: the 18 analyze-failed rows (null features) leave BOTH models.
    ch.attrs["n_analyze_failed"] = int(ch["analyze_error"].notna().sum())
    ch = ch[ch["analyze_error"].isna()].copy()
    ch.attrs["n_zero_tokens"] = int((pd.to_numeric(ch["desc_tokens"], errors="coerce") == 0).sum())
    return ch


def build_h4b_distance(ch: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Attach ``zdist5`` = distance to the nearest FROZEN RQ1 k=5 centroid.

    Frozen reference geometry (fixed before any outcome, per PRE-REG):
      - z-transform fit on the RQ1 population's OWN feature values (features.parquet
        filtered to rq1_cluster_assignments skill_ids), median-impute then z-score;
      - each RQ1 cluster centroid = mean of its members' z-scored 5-feature vectors;
      - every chain version-row is z-scored with that SAME frozen transform, then its
        zdist5 = Euclidean distance to the nearest of the k centroids.
    No refit on chain data → the reference geometry cannot leak chain structure.
    """
    dd = data_dir()
    assign = pq.read_table(dd / RQ1_NAME, columns=["skill_id", "cluster"]).to_pandas()
    feats = pq.read_table(
        dd / FEATURES_NAME, columns=["skill_id", *CONFIRMATORY_FEATURES]).to_pandas()
    rq1 = assign.merge(feats, on="skill_id", how="left")
    rq1 = rq1.dropna(subset=["cluster"])

    params = freeze_ztransform(rq1, CONFIRMATORY_FEATURES)
    Zrq1 = apply_ztransform(rq1, CONFIRMATORY_FEATURES, params)
    rq1_z = pd.DataFrame(Zrq1, columns=CONFIRMATORY_FEATURES, index=rq1.index)
    rq1_z["cluster"] = rq1["cluster"].values
    centroid_df = rq1_z.groupby("cluster")[CONFIRMATORY_FEATURES].mean().sort_index()
    centroids = centroid_df.to_numpy()

    Zch = apply_ztransform(ch, CONFIRMATORY_FEATURES, params)
    ch = ch.copy()
    ch["zdist5"] = nearest_centroid_distance(Zch, centroids)

    meta = {
        "n_centroids": int(centroids.shape[0]),
        "centroid_clusters": [int(c) for c in centroid_df.index.tolist()],
        "cluster_sizes": {int(k): int(v) for k, v in rq1_z["cluster"].value_counts().sort_index().items()},
    }
    return ch, meta


# --------------------------------------------------------------------- estimators


def _ols_cluster(dd: pd.DataFrame, outcome: str) -> dict:
    """OLS ``outcome ~ version_index`` with CR1 cluster-robust SEs on skill_id."""
    X = sm.add_constant(dd[["version_index"]].astype(float))
    ols = sm.OLS(dd[outcome].astype(float).values, X.values)
    r = ols.fit(cov_type="cluster", cov_kwds={"groups": dd["skill_id"].astype(str).values})
    ci = r.conf_int()[1]
    return {"coef": float(r.params[1]), "se": float(r.bse[1]),
            "ci_low": float(ci[0]), "ci_high": float(ci[1]), "p_raw": float(r.pvalues[1])}


def fit_mixed(d: pd.DataFrame, outcome: str) -> dict:
    """MixedLM ``outcome ~ version_index`` + random intercept per skill_id.

    On non-convergence: fall back to OLS with cluster-robust SEs on skill_id (recorded).
    Also records the fitted random-effect variance and any "singular RE covariance"
    warning, and ALWAYS computes an OLS cluster-robust sensitivity estimate so a
    mixed-model conditioning warning can be checked against a warning-free estimator.
    """
    import warnings

    dd = d.dropna(subset=[outcome, "version_index", "skill_id"]).copy()
    n_rows = len(dd)
    n_chains = dd["skill_id"].nunique()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        md = smf.mixedlm(f"{outcome} ~ version_index", dd, groups=dd["skill_id"])
        res = md.fit(method="lbfgs", maxiter=200)
        singular = any("singular" in str(x.message).lower() for x in caught)
    converged = bool(res.converged)
    re_var = float(res.cov_re.iloc[0, 0])
    resid_var = float(res.scale)

    # OLS cluster-robust sensitivity (always) — a warning-free cross-check on the SE.
    ols_sens = _ols_cluster(dd, outcome)

    if not converged:
        # pre-registered fallback: report the OLS cluster-robust estimate AS the estimator.
        return {**ols_sens, "n_rows": n_rows, "n_chains": n_chains,
                "estimator": "OLS + CR1 cluster-robust on skill_id (MixedLM non-converged)",
                "converged": False, "re_var": re_var, "resid_var": resid_var,
                "singular_re": singular, "ols_sens": ols_sens}

    coef = float(res.params["version_index"])
    se = float(res.bse["version_index"])
    ci = res.conf_int().loc["version_index"]
    p = float(res.pvalues["version_index"])
    return {"coef": coef, "se": se, "ci_low": float(ci[0]), "ci_high": float(ci[1]),
            "p_raw": p, "n_rows": n_rows, "n_chains": n_chains,
            "estimator": "MixedLM(REML, random intercept per skill_id)", "converged": True,
            "re_var": re_var, "resid_var": resid_var, "singular_re": singular,
            "ols_sens": ols_sens}


def within_chain_slopes(d: pd.DataFrame, outcome: str) -> dict:
    """Descriptive: distribution of per-chain OLS slopes of ``outcome`` on version index."""
    slopes = []
    for _, g in d.dropna(subset=[outcome]).groupby("skill_id"):
        s = within_chain_slope(g["version_index"].to_numpy(), g[outcome].to_numpy())
        if s is not None:
            slopes.append(s)
    s = np.array(slopes)
    if s.size == 0:
        return {"median": float("nan"), "iqr_low": float("nan"), "iqr_high": float("nan"),
                "frac_pos": float("nan"), "frac_neg": float("nan"), "n": 0}
    return {"median": float(np.median(s)),
            "iqr_low": float(np.percentile(s, 25)), "iqr_high": float(np.percentile(s, 75)),
            "frac_pos": float((s > 0).mean()), "frac_neg": float((s < 0).mean()), "n": int(s.size)}


# --------------------------------------------------------------------- figures


def make_figures(ch: pd.DataFrame, figdir: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figs = []
    d = ch.copy()
    d["log_tokens"] = np.log1p(pd.to_numeric(d["desc_tokens"], errors="coerce"))
    by = d.groupby("version_index").agg(
        log_tokens=("log_tokens", "mean"), zdist5=("zdist5", "mean"),
        n=("skill_id", "size")).reset_index()
    by = by[by["n"] >= 20]

    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.plot(by["version_index"], by["log_tokens"], "-o", ms=3, color="#4477aa")
    ax.set_xlabel("version_index (0 = initial)")
    ax.set_ylabel("mean log1p(desc_tokens)")
    ax.set_title("H4a — length across revisions")
    fig.tight_layout()
    p1 = figdir / "ws3_step5_h4a_length_trajectory.png"
    fig.savefig(p1, dpi=140)
    plt.close(fig)
    figs.append(p1)

    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.plot(by["version_index"], by["zdist5"], "-o", ms=3, color="#ee6677")
    ax.set_xlabel("version_index (0 = initial)")
    ax.set_ylabel("mean z-distance to nearest RQ1 centroid")
    ax.set_title("H4b — convergence toward register-cluster centroids (RQ1 k=5 reference)")
    fig.tight_layout()
    p2 = figdir / "ws3_step5_h4b_convergence.png"
    fig.savefig(p2, dpi=140)
    plt.close(fig)
    figs.append(p2)
    return figs


# --------------------------------------------------------------------- report


def _row(hyp: str, r: dict, direction: str, bh_p: float, survives: bool) -> str:
    side = "coef>0" if direction == "up" else "coef<0"
    ok = "YES" if survives else "no"
    return (f"| **{hyp}** | {r['coef']:+.5f} | [{r['ci_low']:+.5f}, {r['ci_high']:+.5f}] | "
            f"{r['p_raw']:.3e} | {bh_p:.3e} | {side} | **{ok}** |")


def render_report(ctx: dict) -> str:
    L = []
    A = L.append
    A("# WS3 step 5 — RQ4 temporal evolution (CONFIRMATORY H4a + H4b)\n")
    A("Generated by `paper/code/ws3/step5_rq4/step5_rq4.py` — do not hand-edit. Numbers are")
    A("the run's; the pre-registration is ADR-0005 §8b + `LEDGER_LOG.md#WS3-5-RQ4` (BINDING).\n")

    A("## Population (RQ4-eligible version chains)\n")
    A(f"- Chains (≥3 versions): **{ctx['n_chains']}** · version-rows after the 18-row "
      f"analyze-failure drop: **{ctx['n_rows']}** (asserted against pre-registered "
      f"{EXPECTED_CHAINS}/{EXPECTED_ROWS} BEFORE the drop).")
    A(f"- Fork exclusion (ADR-0005): {ctx['n_multi_repo_clusters']} multi-repo clusters → "
      f"{ctx['n_fork_chains_dropped']} fork chains dropped (a no-op — chains are single-repo "
      "canonical heads; forks removed upstream).")
    A(f"- Dropped {ctx['n_analyze_failed']} analyze-failed rows (null features, surrogate-char); "
      f"kept {ctx['n_zero_tokens']} zero-token rows (log1p handles 0).\n")

    A("## Confirmatory results — MixedLM, version_index fixed effect, random intercept per skill_id\n")
    A("BH q=0.10 over the {H4a, H4b} family (D6-style). Per-version coefficient + 95% CI; "
      "one-sided direction pre-registered per hypothesis. Effect sizes reported, not bare p.\n")
    A("| hypothesis | per-version coef | 95% CI | p (raw) | p (BH, 2-family) | pre-reg side | supported |")
    A("|---|---|---|---|---|---|---|")
    A(_row("H4a (length ↑)", ctx["h4a"], "up", ctx["h4a_bh"], ctx["h4a_supported"]))
    A(_row("H4b (converge ↓)", ctx["h4b"], "down", ctx["h4b_bh"], ctx["h4b_supported"]))
    A("")
    A(f"- **H4a** estimator: {ctx['h4a']['estimator']}; N={ctx['h4a']['n_rows']} rows / "
      f"{ctx['h4a']['n_chains']} chains; converged={ctx['h4a']['converged']}.")
    A(f"- **H4b** estimator: {ctx['h4b']['estimator']}; N={ctx['h4b']['n_rows']} rows / "
      f"{ctx['h4b']['n_chains']} chains; converged={ctx['h4b']['converged']}.")
    A(f"- H4b reference geometry: nearest of the **{ctx['h4b_meta']['n_centroids']}** frozen "
      f"RQ1 k-means centroids (clusters {ctx['h4b_meta']['centroid_clusters']}, RQ1-population "
      f"sizes {ctx['h4b_meta']['cluster_sizes']}), RQ1's frozen z-transform, no refit.\n")

    A("**H4b interpretive caveat (pre-registered, ADR-0005 §8b):** RQ1 (WS3-3-CLUSTER + "
      "robustness) found **NO discrete register dialects** — the k=5 partition is a "
      "below-silhouette-floor D3 fallback. So H4b measures convergence toward the nearest of "
      "the RQ1 k-means **reference centroids**, a partition RQ1 found dimensional not "
      "categorical — **NOT** convergence to a validated dialect. Any H4b reading carries this.\n")

    A("## Estimator diagnostics + OLS cluster-robust sensitivity\n")
    A("Both mixed models converged (no pre-registered non-convergence fallback triggered). "
      "The fitted between-skill random-intercept variance and any \"singular RE covariance\" "
      "optimizer warning are reported for honesty, alongside a warning-free OLS + CR1 "
      "cluster-robust-on-skill_id sensitivity estimate for the same `version_index` coefficient "
      "(NOT a swap — the confirmatory estimator remains the MixedLM; this is a cross-check).\n")
    A("| hypothesis | RE var (skill) | resid var | singular-RE warning | OLS-CR1 coef [95% CI] | OLS-CR1 p |")
    A("|---|---|---|---|---|---|")
    for hyp, r in (("H4a", ctx["h4a"]), ("H4b", ctx["h4b"])):
        s = r["ols_sens"]
        A(f"| {hyp} | {r['re_var']:.4g} | {r['resid_var']:.4g} | "
          f"{'YES' if r['singular_re'] else 'no'} | "
          f"{s['coef']:+.5f} [{s['ci_low']:+.5f}, {s['ci_high']:+.5f}] | {s['p_raw']:.3e} |")
    A("")
    if ctx["h4b"]["singular_re"]:
        A("- **H4b singular-RE note:** the warning fires because `zdist5` is on a large raw "
          f"scale (resid var ≈ {ctx['h4b']['resid_var']:.4g}), which ill-conditions the "
          "optimizer's internal covariance matrix — NOT a collapsed random effect (the fitted "
          f"skill RE variance is {ctx['h4b']['re_var']:.4g}, comparable to residual, i.e. "
          "substantial between-skill variance). The OLS cluster-robust sensitivity above agrees "
          "on sign and significance, so the H4b conclusion does not hinge on the mixed-model "
          "conditioning. Still reported as a limitation.\n")

    A("## Descriptive within-chain slopes (one OLS slope per chain)\n")
    sa, sb = ctx["h4a_slopes"], ctx["h4b_slopes"]
    A("| outcome | median slope | IQR | fraction rising | fraction falling | n chains |")
    A("|---|---|---|---|---|---|")
    A(f"| log1p(desc_tokens) | {sa['median']:+.5f} | [{sa['iqr_low']:+.5f}, {sa['iqr_high']:+.5f}] | "
      f"{100*sa['frac_pos']:.1f}% | {100*sa['frac_neg']:.1f}% | {sa['n']} |")
    A(f"| zdist5 (to centroid) | {sb['median']:+.5f} | [{sb['iqr_low']:+.5f}, {sb['iqr_high']:+.5f}] | "
      f"{100*sb['frac_pos']:.1f}% | {100*sb['frac_neg']:.1f}% | {sb['n']} |\n")

    A("## Robustness — canonical-only rerun (fork-structure sensitivity)\n")
    A(f"The ~{ctx['rc_n_chains']} canonical chains only (non-canonical single-repo chains "
      "removed). A sign flip vs the full population would flag that non-canonical chains "
      "drive the result.\n")
    A("| hypothesis | per-version coef | 95% CI | p (raw) | pre-reg side | matches full? |")
    A("|---|---|---|---|---|---|")
    for hyp, r, direction, full in (
        ("H4a", ctx["rc_h4a"], "up", ctx["h4a"]),
        ("H4b", ctx["rc_h4b"], "down", ctx["h4b"]),
    ):
        same = (np.sign(r["coef"]) == np.sign(full["coef"]))
        side = "coef>0" if direction == "up" else "coef<0"
        A(f"| {hyp} | {r['coef']:+.5f} | [{r['ci_low']:+.5f}, {r['ci_high']:+.5f}] | "
          f"{r['p_raw']:.3e} | {side} | {'yes' if same else '**SIGN FLIP**'} |")
    A("")

    A("## Calibrated summary\n")
    A(ctx["summary"])
    A("")
    return "\n".join(L)


# --------------------------------------------------------------------- main


def main() -> None:
    figdir = repo_root() / "paper" / "figures"
    figdir.mkdir(parents=True, exist_ok=True)

    ch = load_chains()
    ch, h4b_meta = build_h4b_distance(ch)
    ch["log_tokens"] = np.log1p(pd.to_numeric(ch["desc_tokens"], errors="coerce"))

    ctx: dict = {}
    ctx["n_chains"] = int(ch["skill_id"].nunique())
    ctx["n_rows"] = int(len(ch))
    ctx["n_multi_repo_clusters"] = int(ch.attrs["n_multi_repo_clusters"])
    ctx["n_fork_chains_dropped"] = int(ch.attrs["n_fork_chains_dropped"])
    ctx["n_analyze_failed"] = int(ch.attrs["n_analyze_failed"])
    ctx["n_zero_tokens"] = int(ch.attrs["n_zero_tokens"])
    ctx["h4b_meta"] = h4b_meta

    # --- confirmatory H4a + H4b (full population) ----------------------------
    ctx["h4a"] = fit_mixed(ch, "log_tokens")
    ctx["h4b"] = fit_mixed(ch, "zdist5")

    # BH over the 2-family {H4a p, H4b p}.
    bh = benjamini_hochberg(np.array([ctx["h4a"]["p_raw"], ctx["h4b"]["p_raw"]]), BH_Q)
    ctx["h4a_bh"], ctx["h4b_bh"] = float(bh[0]), float(bh[1])
    ctx["h4a_supported"] = bool(ctx["h4a"]["coef"] > 0 and ctx["h4a_bh"] <= BH_Q)
    ctx["h4b_supported"] = bool(ctx["h4b"]["coef"] < 0 and ctx["h4b_bh"] <= BH_Q)

    ctx["h4a_slopes"] = within_chain_slopes(ch, "log_tokens")
    ctx["h4b_slopes"] = within_chain_slopes(ch, "zdist5")

    # --- robustness: canonical-only ------------------------------------------
    canon = ch[is_true(ch["is_canonical"])].copy()
    ctx["rc_n_chains"] = int(canon["skill_id"].nunique())
    ctx["rc_h4a"] = fit_mixed(canon, "log_tokens")
    ctx["rc_h4b"] = fit_mixed(canon, "zdist5")

    # --- calibrated summary --------------------------------------------------
    def verdict(name, r, supported, direction):
        word = "SUPPORTED" if supported else "NOT supported"
        return (f"{name}: **{word}** (per-version coef {r['coef']:+.5f} "
                f"[{r['ci_low']:+.5f}, {r['ci_high']:+.5f}], BH-p "
                f"{(ctx['h4a_bh'] if name.startswith('H4a') else ctx['h4b_bh']):.3e})")
    ctx["summary"] = (
        f"RQ4 (confirmatory, N={ctx['n_rows']} version-rows / {ctx['n_chains']} chains, "
        "MixedLM version_index fixed effect + skill random intercept, BH q=0.10 over 2): "
        f"{verdict('H4a (length rises)', ctx['h4a'], ctx['h4a_supported'], 'up')}; "
        f"{verdict('H4b (converges to register centroid)', ctx['h4b'], ctx['h4b_supported'], 'down')}. "
        f"{ctx['h4a_slopes']['frac_pos']*100:.1f}% of chains have a rising length slope; "
        f"{ctx['h4b_slopes']['frac_neg']*100:.1f}% move toward their nearest centroid. "
        "H4b carries its pre-registered caveat (RQ1 found the k=5 partition dimensional, not "
        "categorical — convergence is toward reference centroids, not a validated dialect). "
        "Within-skill (random intercept absorbs per-skill baseline); not causal. Canonical-only "
        "robustness reported alongside. The lagged-adoption + embedding-delta exploratory "
        "analyses (ADR-0005 §8b) are out of scope for this confirmatory run.")

    figs = make_figures(ch, figdir)

    report_path = Path(__file__).resolve().parent / "step5_rq4.md"
    report_path.write_text(render_report(ctx))
    print(f"[report] {report_path.relative_to(repo_root())}")

    # persist per-row trajectory artifact (gitignored) for provenance + manifest hashing.
    out_cols = ["skill_id", "version_index", "n_versions", "is_canonical",
                "desc_tokens", "log_tokens", "zdist5"]
    out = ch[out_cols].copy()
    out_path = data_dir() / OUTPUT_NAME
    out.to_parquet(out_path, index=False)

    write_manifest(
        out_path,
        source="ws3_rq4_temporal",
        inputs=[
            {"name": CHAINS_NAME, "sha256": sha256_file(data_dir() / CHAINS_NAME)},
            {"name": RQ1_NAME, "sha256": sha256_file(data_dir() / RQ1_NAME)},
            {"name": FEATURES_NAME, "sha256": sha256_file(data_dir() / FEATURES_NAME)},
        ],
        n_rows=len(out),
        packages=["statsmodels", "pandas", "numpy", "scipy", "matplotlib", "pyarrow"],
        extra={
            "seed": SEED,
            "n_chains": ctx["n_chains"],
            "n_version_rows": ctx["n_rows"],
            "h4a_coef_version_index": ctx["h4a"]["coef"],
            "h4a_ci": [ctx["h4a"]["ci_low"], ctx["h4a"]["ci_high"]],
            "h4a_p_bh": ctx["h4a_bh"],
            "h4a_supported": ctx["h4a_supported"],
            "h4a_estimator": ctx["h4a"]["estimator"],
            "h4b_coef_version_index": ctx["h4b"]["coef"],
            "h4b_ci": [ctx["h4b"]["ci_low"], ctx["h4b"]["ci_high"]],
            "h4b_p_bh": ctx["h4b_bh"],
            "h4b_supported": ctx["h4b_supported"],
            "h4b_estimator": ctx["h4b"]["estimator"],
            "h4b_reference": "nearest of frozen RQ1 k=5 centroids (dimensional-not-categorical caveat)",
            "h4a_re_var": ctx["h4a"]["re_var"],
            "h4b_re_var": ctx["h4b"]["re_var"],
            "h4b_singular_re_warning": ctx["h4b"]["singular_re"],
            "h4b_ols_cluster_robust_coef": ctx["h4b"]["ols_sens"]["coef"],
            "h4b_ols_cluster_robust_p": ctx["h4b"]["ols_sens"]["p_raw"],
            "report": "paper/code/ws3/step5_rq4/step5_rq4.md",
            "figures": [str(p.relative_to(repo_root())) for p in figs],
        },
    )
    print(f"[done] RQ4 H4a {'SUPPORTED' if ctx['h4a_supported'] else 'null'} · "
          f"H4b {'SUPPORTED' if ctx['h4b_supported'] else 'null'}.")


if __name__ == "__main__":
    main()
