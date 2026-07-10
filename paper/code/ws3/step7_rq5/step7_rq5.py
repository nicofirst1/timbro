"""WS3 step 7 — RQ5 audience contrast (CONFIRMATORY C3-vs-C2 + descriptive bracket).

Faithful execution of the RQ5 pre-registration frozen VERBATIM in ADR-0008 (D10) and
pinned in ``paper/code/ws3/LEDGER_LOG.md#WS3-7-RQ5`` (PRE-REG 2026-07-10 09:14). Nothing
is decided at runtime — every rule below is a constant carried in from the ADR / PRE-REG.

  question        does instruction written FOR AGENTS (SKILL.md) differ linguistically from
                  instruction written FOR HUMANS (README/CONTRIBUTING)?
  design          three cells, bracketing estimand (NOT classical DiD — no agent-pre cell):
                    C1 human/pre-2023   (the-stack READMEs)         [features_human, era=pre]
                    C2 human/post-2023  (current GitHub READMEs)    [features_human, era=post]
                    C3 agent/post-2023  (WS1 organic-canonical skills) [features.parquet]
  estimand        per feature, the bracket [C3-C2, C3-C1]:
                    - lower bound  C3-C2  (CONFIRMATORY, conservative: C2 contamination
                                           pushes it toward the agent register)
                    - upper bound  C3-C1  (descriptive: audience + era together)
                    - era shift    C2-C1  (descriptive: how register moved post-LLM)
  confirmatory    C3 vs C2 ONLY, TWO-SIDED, on the 5 ADR-0004 confirmatory features.
                  C3-C1 and C2-C1 are DESCRIPTIVE, never tested confirmatory.
  model           per feature: OLS  feature ~ C(cell) + log_tokens.  log(desc_tokens) is
                  always a covariate, never a hypothesis. BH q=0.10 over the 5-feature RQ5
                  family (its own family, D6). Effect size = Cohen's d on the log_tokens-
                  residualized feature, 95% CI. Seed 42.
  dedup           ADR-0008 "same dedup treatment as D1 (exact SHA256 + MinHash 0.9/5-gram)",
                  applied PER CELL (audience-contrast reading; matches ADR-0009 "same
                  pipeline as every other cell: D1 dedup"):
                    C3  already D1-deduped upstream -> is_canonical=="true" & source!=slop_stub
                    C1,C2  NOT deduped upstream -> apply dedup.assign_clusters WITHIN each
                           era-cell, keep canonical rep, join back by doc_id.
                  Within-cell (not pooled) so the >=5,000 per-cell floor stays meaningful and
                  a cross-era/cross-audience near-dup never removes one cell's doc via another.
  floor           >=5,000 docs per human cell after dedup, else RQ5 downgrades to descriptive
                  (no hypothesis tests). Asserted below (STOP-and-downgrade on failure).

A null on any feature, or an effect in an unexpected direction (two-sided, no priors), is a
finding reported straight — never a stop. STOP only on a human cell below the 5,000 floor
(-> downgrade) or a material C3 drift.

Run (from repo root):
  uv run --with-requirements paper/code/ws3/requirements.txt \
      python paper/code/ws3/step7_rq5/step7_rq5.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import statsmodels.formula.api as smf

# WS1 provenance helpers + the D1 dedup machinery.
# __file__ = paper/code/ws3/step7_rq5/step7_rq5.py
sys.path.append(str(Path(__file__).resolve().parents[2] / "ws1"))
from _manifest import (  # noqa: E402
    SEED,
    data_dir,
    repo_root,
    sha256_file,
    write_manifest,
)
from dedup import assign_clusters  # noqa: E402  (exact SHA256 + MinHash 0.9/5-gram, seed 42)

# --- pre-registered constants (ADR-0008 D10 + LEDGER_LOG WS3-7-RQ5 PRE-REG) ---------

FEATURES_HUMAN_NAME = "features_human.parquet"     # C1/C2 feature vectors
HUMAN_BASELINE_NAME = "human_baseline.parquet"     # C1/C2 text (for within-cell D1 dedup)
FEATURES_NAME = "features.parquet"                 # C3 agent feature vectors
OUTPUT_NAME = "rq5_audience_contrast.parquet"

# ADR-0004 confirmatory feature family (FROZEN — 5 features).
CONFIRMATORY_FEATURES = [
    "dict_imperative_ratio",
    "dict_hedge_per_1k",
    "read_flesch_kincaid_grade",
    "syn_mean_tree_depth",
    "coh_lemma_overlap_adj",
]

CELL_C1 = "C1_human_pre"
CELL_C2 = "C2_human_post"
CELL_C3 = "C3_agent_post"

HUMAN_FLOOR = 5000  # ADR-0008 floor: >=5,000 docs per human cell after dedup
BH_Q = 0.10         # D6-style, over the 5-feature RQ5 family


# --------------------------------------------------------------------- pure seams


def is_true(series: pd.Series) -> pd.Series:
    """``is_canonical`` truthiness robust to the corpus STRING/bool split (ledger gotcha).

    ``features.parquet`` ships it as the STRING "true"/"false" (never naive truthiness).
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


def dedup_cell_canonical(text_df: pd.DataFrame) -> set:
    """Apply the D1 dedup machinery to one cell's docs; return the canonical ``doc_id`` set.

    ``text_df`` has columns ``doc_id`` + ``text``. Reuses ``dedup.assign_clusters`` (exact
    normalized-text SHA256 then MinHashLSH 0.9-Jaccard over word 5-gram shingles,
    num_perm=128, seed 42) unchanged — the SAME machinery WS1 ran corpus-wide (D1), here
    applied within a single cell. ``skill_id`` slot carries the ``doc_id``; ``source`` is a
    constant (single cell) and ``n_revisions`` a constant 1 (README/CONTRIBUTING docs have
    no revision chain), so canonical selection reduces to smallest ``doc_id`` per cluster —
    a deterministic, cell-internal choice.
    """
    rows = [
        {"skill_id": r.doc_id, "source": "skill_diffs", "text": r.text, "n_revisions": 1}
        for r in text_df.itertuples(index=False)
    ]
    assigned = assign_clusters(rows)
    return {a["skill_id"] for a in assigned if a["is_canonical"] == "true"}


def median_impute(df: pd.DataFrame, feats: list[str]) -> tuple[pd.DataFrame, dict]:
    """Median-impute the feature columns over the POOLED analysis frame (steps 2/3/5 rule).

    Returns the imputed frame and a per-feature count of imputed cells. The 5 short-doc-
    undefined columns (SMOG/coherence) plus any sparse nulls in the others are filled with
    the pooled median. 0 rows dropped.
    """
    out = df.copy()
    n_imputed = {}
    for f in feats:
        col = pd.to_numeric(out[f], errors="coerce")
        n_imputed[f] = int(col.isna().sum())
        out[f] = col.fillna(col.median())
    return out, n_imputed


def cohens_d(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    """Cohen's d (a vs b) with a pooled SD, plus a 95% CI (normal approx on d).

    Positive d means mean(a) > mean(b). CI uses the standard large-sample SE of d:
      SE = sqrt((na+nb)/(na*nb) + d^2 / (2*(na+nb))).
    """
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    na, nb = a.size, b.size
    va, vb = a.var(ddof=1), b.var(ddof=1)
    pooled = np.sqrt(((na - 1) * va + (nb - 1) * vb) / (na + nb - 2))
    if pooled == 0 or not np.isfinite(pooled):
        return 0.0, 0.0, 0.0
    d = (a.mean() - b.mean()) / pooled
    se = np.sqrt((na + nb) / (na * nb) + d * d / (2.0 * (na + nb)))
    return float(d), float(d - 1.96 * se), float(d + 1.96 * se)


# --------------------------------------------------------------------- load + build


def load_cells() -> tuple[pd.DataFrame, dict]:
    """Build the three-cell analysis frame with per-cell D1 dedup applied.

    Returns (frame, meta). ``frame`` has columns ``doc_id, cell, log_tokens`` + the 5
    confirmatory features (median-imputed). ``meta`` carries the pre/post-dedup counts,
    the floor-gate outcome, and the imputation counts.
    """
    dd = data_dir()

    # --- C1 / C2 (human): features + text, within-cell D1 dedup ---------------------
    hf = pq.read_table(
        dd / FEATURES_HUMAN_NAME,
        columns=["doc_id", "audience", "era", "desc_tokens", *CONFIRMATORY_FEATURES],
    ).to_pandas()
    ht = pq.read_table(dd / HUMAN_BASELINE_NAME, columns=["doc_id", "era", "text"]).to_pandas()

    meta: dict = {"n_pre_dedup": {}, "n_post_dedup": {}, "removal_rate": {}}
    human_frames = []
    for era, cell in (("pre", CELL_C1), ("post", CELL_C2)):
        text_cell = ht[ht["era"] == era][["doc_id", "text"]]
        n_pre = len(text_cell)
        canon_ids = dedup_cell_canonical(text_cell)
        feat_cell = hf[(hf["era"] == era) & (hf["doc_id"].isin(canon_ids))].copy()
        feat_cell["cell"] = cell
        n_post = len(feat_cell)
        meta["n_pre_dedup"][cell] = n_pre
        meta["n_post_dedup"][cell] = n_post
        meta["removal_rate"][cell] = (1 - n_post / n_pre) if n_pre else 0.0
        human_frames.append(feat_cell[["doc_id", "cell", "desc_tokens", *CONFIRMATORY_FEATURES]])

    # Floor gate (ADR-0008): >=5,000 per human cell after dedup, else DOWNGRADE.
    meta["floor"] = HUMAN_FLOOR
    meta["floor_cleared"] = bool(
        meta["n_post_dedup"][CELL_C1] >= HUMAN_FLOOR
        and meta["n_post_dedup"][CELL_C2] >= HUMAN_FLOOR
    )
    if not meta["floor_cleared"]:
        raise SystemExit(
            f"[STOP/DOWNGRADE] ADR-0008 floor breached: C1={meta['n_post_dedup'][CELL_C1]}, "
            f"C2={meta['n_post_dedup'][CELL_C2]} (need >={HUMAN_FLOOR} each after dedup). "
            "RQ5 downgrades to descriptive/exploratory — no hypothesis tests. Record + consult."
        )

    # --- C3 (agent): organic-canonical, already D1-deduped upstream -----------------
    af = pq.read_table(
        dd / FEATURES_NAME,
        columns=["skill_id", "is_canonical", "source", "desc_tokens", *CONFIRMATORY_FEATURES],
    ).to_pandas()
    c3 = af[is_true(af["is_canonical"]) & (af["source"] != "slop_stub")].copy()
    c3 = c3.rename(columns={"skill_id": "doc_id"})
    c3["cell"] = CELL_C3
    meta["n_c3_organic_canonical"] = len(c3)
    agent_frame = c3[["doc_id", "cell", "desc_tokens", *CONFIRMATORY_FEATURES]]

    frame = pd.concat([*human_frames, agent_frame], ignore_index=True)
    frame["log_tokens"] = np.log1p(pd.to_numeric(frame["desc_tokens"], errors="coerce").fillna(0.0))

    # Median-impute the 5 confirmatory features over the pooled frame (steps 2/3/5 rule).
    frame, n_imputed = median_impute(frame, CONFIRMATORY_FEATURES)
    meta["n_imputed"] = n_imputed
    meta["n_total"] = len(frame)
    return frame, meta


# --------------------------------------------------------------------- estimators


def fit_feature(frame: pd.DataFrame, feature: str) -> dict:
    """OLS ``feature ~ C(cell) + log_tokens`` with C2 as the reference level.

    Returns every pairwise cell contrast (coefficient + 95% CI + two-sided p) and the
    log_tokens-residualized Cohen's d for each contrast. C2 is the reference so the
    ``C(cell)[T.C3]`` coefficient IS the confirmatory C3-vs-C2 adjusted mean difference.
    """
    d = frame[["cell", feature, "log_tokens"]].copy()
    d[feature] = pd.to_numeric(d[feature], errors="coerce")
    d = d.dropna(subset=[feature, "log_tokens"])
    # Reference = C2 (post-dedup human/post) so [T.C3] = C3-C2, [T.C1] = C1-C2.
    d["cell"] = pd.Categorical(d["cell"], categories=[CELL_C2, CELL_C3, CELL_C1])

    model = smf.ols(f"Q('{feature}') ~ C(cell) + log_tokens", data=d).fit()
    tC3 = f"C(cell)[T.{CELL_C3}]"

    def _contrast(term: str) -> dict:
        ci = model.conf_int().loc[term]
        return {"coef": float(model.params[term]), "ci_low": float(ci[0]),
                "ci_high": float(ci[1]), "p_raw": float(model.pvalues[term])}

    c3_vs_c2 = _contrast(tC3)                          # CONFIRMATORY
    # C3-C1 (upper bound) + C2-C1 (era shift): refit with C1 reference for clean CIs/ps.
    d1 = d.copy()
    d1["cell"] = pd.Categorical(d1["cell"], categories=[CELL_C1, CELL_C3, CELL_C2])
    m1 = smf.ols(f"Q('{feature}') ~ C(cell) + log_tokens", data=d1).fit()
    tC3_1 = f"C(cell)[T.{CELL_C3}]"
    tC2_1 = f"C(cell)[T.{CELL_C2}]"
    ci31 = m1.conf_int().loc[tC3_1]
    c3_vs_c1 = {"coef": float(m1.params[tC3_1]), "ci_low": float(ci31[0]),
                "ci_high": float(ci31[1]), "p_raw": float(m1.pvalues[tC3_1])}
    ci21 = m1.conf_int().loc[tC2_1]
    c2_vs_c1 = {"coef": float(m1.params[tC2_1]), "ci_low": float(ci21[0]),
                "ci_high": float(ci21[1]), "p_raw": float(m1.pvalues[tC2_1])}

    # log_tokens-residualized Cohen's d per contrast (residualize on the covariate, then d).
    resid_model = smf.ols(f"Q('{feature}') ~ log_tokens", data=d).fit()
    d = d.assign(_resid=resid_model.resid)
    by = {c: d.loc[d["cell"] == c, "_resid"].to_numpy() for c in (CELL_C1, CELL_C2, CELL_C3)}
    d_c3c2 = cohens_d(by[CELL_C3], by[CELL_C2])
    d_c3c1 = cohens_d(by[CELL_C3], by[CELL_C1])
    d_c2c1 = cohens_d(by[CELL_C2], by[CELL_C1])

    return {
        "feature": feature,
        "n": int(len(d)),
        "c3_vs_c2": {**c3_vs_c2, "d": d_c3c2[0], "d_lo": d_c3c2[1], "d_hi": d_c3c2[2]},
        "c3_vs_c1": {**c3_vs_c1, "d": d_c3c1[0], "d_lo": d_c3c1[1], "d_hi": d_c3c1[2]},
        "c2_vs_c1": {**c2_vs_c1, "d": d_c2c1[0], "d_lo": d_c2c1[1], "d_hi": d_c2c1[2]},
    }


# --------------------------------------------------------------------- figures


def make_figures(results: list[dict], figdir: Path) -> list[Path]:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    feats = [r["feature"] for r in results]
    y = np.arange(len(feats))

    fig, ax = plt.subplots(figsize=(8, 3.6))
    # bracket [C3-C2 (lower), C3-C1 (upper)] as Cohen's d, per feature.
    lo = np.array([r["c3_vs_c2"]["d"] for r in results])
    hi = np.array([r["c3_vs_c1"]["d"] for r in results])
    for i in range(len(feats)):
        ax.plot([lo[i], hi[i]], [y[i], y[i]], "-", color="#bbbbbb", lw=2, zorder=1)
    ax.scatter(lo, y, color="#4477aa", label="C3-C2 (confirmatory, lower bound)", zorder=2)
    ax.scatter(hi, y, color="#ee6677", label="C3-C1 (upper bound)", zorder=2)
    ax.axvline(0, color="#333333", lw=0.8)
    ax.set_yticks(y)
    ax.set_yticklabels(feats, fontsize=8)
    ax.set_xlabel("audience effect (Cohen's d, agent vs human, log-length residualized)")
    ax.set_title("RQ5 audience-effect bracket [C3-C2, C3-C1] per confirmatory feature")
    ax.legend(fontsize=7, loc="best")
    fig.tight_layout()
    p1 = figdir / "ws3_step7_rq5_bracket.png"
    fig.savefig(p1, dpi=140)
    plt.close(fig)
    return [p1]


# --------------------------------------------------------------------- report


def _contrast_cells(c: dict) -> str:
    return (f"{c['coef']:+.4f} [{c['ci_low']:+.4f}, {c['ci_high']:+.4f}] | "
            f"d={c['d']:+.3f} [{c['d_lo']:+.3f}, {c['d_hi']:+.3f}]")


def render_report(ctx: dict) -> str:
    L = []
    A = L.append
    A("# WS3 step 7 — RQ5 audience contrast (CONFIRMATORY C3-vs-C2 + descriptive bracket)\n")
    A("Generated by `paper/code/ws3/step7_rq5/step7_rq5.py` — do not hand-edit. Numbers are")
    A("the run's; the pre-registration is ADR-0008 (D10) + `LEDGER_LOG.md#WS3-7-RQ5` (BINDING).\n")

    m = ctx["meta"]
    A("## Cells (three-cell bracketing design, per-cell D1 dedup)\n")
    A("| cell | audience / era | source | pre-dedup | post-dedup | removal |")
    A("|---|---|---|---|---|---|")
    A(f"| **C1** | human / pre-2023 | the-stack READMEs | {m['n_pre_dedup'][CELL_C1]} | "
      f"**{m['n_post_dedup'][CELL_C1]}** | {100*m['removal_rate'][CELL_C1]:.2f}% |")
    A(f"| **C2** | human / post-2023 | current GitHub READMEs | {m['n_pre_dedup'][CELL_C2]} | "
      f"**{m['n_post_dedup'][CELL_C2]}** | {100*m['removal_rate'][CELL_C2]:.2f}% |")
    A(f"| **C3** | agent / post-2023 | WS1 organic-canonical skills | (D1 upstream) | "
      f"**{m['n_c3_organic_canonical']}** | (is_canonical & !slop_stub) |")
    A("")
    A(f"- Dedup: ADR-0008 \"same dedup treatment as D1 (exact SHA256 + MinHash 0.9/5-gram)\", "
      f"applied **per cell** (audience-contrast reading). C1/C2 via `dedup.assign_clusters` "
      f"(num_perm=128, seed {SEED}) within each era-cell; C3 via its upstream WS1 D1 "
      "`is_canonical`.")
    A(f"- **Floor gate (ADR-0008, >= {m['floor']} per human cell after dedup):** "
      f"C1 {m['n_post_dedup'][CELL_C1]} and C2 {m['n_post_dedup'][CELL_C2]} — "
      f"**{'CLEARED' if m['floor_cleared'] else 'BREACHED — RQ5 DOWNGRADED'}**. RQ5 stands "
      "as a confirmatory analysis.")
    A("- Median imputation (short-doc-undefined columns, pooled frame, 0 rows dropped): "
      + ", ".join(f"`{k}`={v}" for k, v in m["n_imputed"].items()) + f" of {m['n_total']} rows.\n")

    A("## Estimand — bracketing, NOT classical DiD (ADR-0008)\n")
    A("The naive diff-in-diff `(C3-C1) - (C2-C1)` collapses to `C3-C2` (no agent-pre cell). "
      "Per feature the audience effect is the **bracket [C3-C2, C3-C1]**: the CONFIRMATORY "
      "lower bound `C3-C2` is conservative (C2's LLM contamination pushes it toward the agent "
      "register, so anything surviving is real); the upper bound `C3-C1` adds the era shift; "
      "`C2-C1` is the descriptive era shift itself. Contrasts are adjusted means from OLS "
      "`feature ~ C(cell) + log_tokens`; d is Cohen's d on the log_tokens-residualized feature.\n")

    A("## CONFIRMATORY — C3 vs C2 (two-sided, BH q=0.10 over the 5-feature RQ5 family)\n")
    A("| feature | C3-C2 coef [95% CI] | Cohen's d [95% CI] | p (raw) | p (BH) | survives |")
    A("|---|---|---|---|---|---|")
    for r in ctx["results"]:
        c = r["c3_vs_c2"]
        surv = "**YES**" if r["bh_survives"] else "no"
        A(f"| `{r['feature']}` | {c['coef']:+.4f} [{c['ci_low']:+.4f}, {c['ci_high']:+.4f}] | "
          f"{c['d']:+.3f} [{c['d_lo']:+.3f}, {c['d_hi']:+.3f}] | {c['p_raw']:.3e} | "
          f"{r['bh_p']:.3e} | {surv} |")
    A("")
    A(f"- {ctx['n_survive']} of 5 confirmatory features survive BH at q=0.10 on the C3-vs-C2 "
      "(conservative lower-bound) contrast.\n")

    A("## Descriptive bracket + era shift (NOT tested confirmatory)\n")
    A("| feature | C3-C1 (upper bound) coef [95% CI] · d | C2-C1 (era shift) coef [95% CI] · d |")
    A("|---|---|---|")
    for r in ctx["results"]:
        A(f"| `{r['feature']}` | {_contrast_cells(r['c3_vs_c1'])} | {_contrast_cells(r['c2_vs_c1'])} |")
    A("")

    A("## Calibrated summary\n")
    A(ctx["summary"])
    A("")
    A("## Register caveat (ADR-0008, carried into the paper)\n")
    A("README/CONTRIBUTING is a different *genre* than a skill file even for human audiences "
      "(announcement + orientation vs. pure procedure). The claim is scoped to "
      "\"instructional/documentation register directed at humans vs. agents,\" NOT a "
      "genre-matched minimal pair. Genre-matched human procedure corpora are named future-work.\n")
    return "\n".join(L)


# --------------------------------------------------------------------- main


def main() -> None:
    figdir = repo_root() / "paper" / "figures"
    figdir.mkdir(parents=True, exist_ok=True)

    frame, meta = load_cells()

    results = [fit_feature(frame, f) for f in CONFIRMATORY_FEATURES]

    # BH over the 5 C3-vs-C2 (confirmatory) p-values.
    bh = benjamini_hochberg(np.array([r["c3_vs_c2"]["p_raw"] for r in results]), BH_Q)
    for r, p in zip(results, bh):
        r["bh_p"] = float(p)
        r["bh_survives"] = bool(p <= BH_Q)
    n_survive = int(sum(r["bh_survives"] for r in results))

    survivors = [r["feature"] for r in results if r["bh_survives"]]
    summary = (
        f"RQ5 (confirmatory, TWO-SIDED C3-vs-C2 conservative lower bound, N={meta['n_total']} "
        f"docs: C1={meta['n_post_dedup'][CELL_C1]} / C2={meta['n_post_dedup'][CELL_C2]} / "
        f"C3={meta['n_c3_organic_canonical']}, OLS feature ~ C(cell) + log_tokens, BH q=0.10 "
        f"over 5): **{n_survive} of 5** confirmatory features show an audience effect that "
        f"survives BH on the conservative C3-vs-C2 contrast"
        + (f" — {', '.join('`'+s+'`' for s in survivors)}" if survivors else "")
        + ". Each surviving effect is bracketed by [C3-C2 (lower), C3-C1 (upper)]; the "
        "descriptive era shift C2-C1 is reported alongside. Observed-level only — audience is "
        "confounded with era by construction (the bracketing design's whole premise), so the "
        "effect is reported as a bracket, C3-C2 as the conservative bound, never as a "
        "clean audience main effect. No causal, 'validated', or genre-matched-minimal-pair "
        "language; the README-vs-SKILL genre caveat is carried."
    )

    ctx = {"meta": meta, "results": results, "n_survive": n_survive, "summary": summary}

    figs = make_figures(results, figdir)
    ctx_report = render_report(ctx)

    report_path = Path(__file__).resolve().parent / "step7_rq5.md"
    report_path.write_text(ctx_report)
    print(f"[report] {report_path.relative_to(repo_root())}")

    # persist per-contrast result rows (gitignored) for provenance + manifest hashing.
    rows = []
    for r in results:
        for cname, c in (("C3_vs_C2", r["c3_vs_c2"]), ("C3_vs_C1", r["c3_vs_c1"]),
                         ("C2_vs_C1", r["c2_vs_c1"])):
            rows.append({
                "feature": r["feature"], "contrast": cname, "n": r["n"],
                "coef": c["coef"], "ci_low": c["ci_low"], "ci_high": c["ci_high"],
                "p_raw": c["p_raw"], "cohens_d": c["d"], "d_lo": c["d_lo"], "d_hi": c["d_hi"],
                "bh_p": r["bh_p"] if cname == "C3_vs_C2" else float("nan"),
                "bh_survives": r["bh_survives"] if cname == "C3_vs_C2" else False,
                "confirmatory": cname == "C3_vs_C2",
            })
    out = pd.DataFrame(rows)
    out_path = data_dir() / OUTPUT_NAME
    out.to_parquet(out_path, index=False)

    write_manifest(
        out_path,
        source="ws3_rq5_audience_contrast",
        inputs=[
            {"name": FEATURES_HUMAN_NAME, "sha256": sha256_file(data_dir() / FEATURES_HUMAN_NAME)},
            {"name": HUMAN_BASELINE_NAME, "sha256": sha256_file(data_dir() / HUMAN_BASELINE_NAME)},
            {"name": FEATURES_NAME, "sha256": sha256_file(data_dir() / FEATURES_NAME)},
        ],
        n_rows=len(out),
        packages=["statsmodels", "datasketch", "pandas", "numpy", "scipy", "matplotlib", "pyarrow"],
        extra={
            "seed": SEED,
            "n_c1_post_dedup": meta["n_post_dedup"][CELL_C1],
            "n_c2_post_dedup": meta["n_post_dedup"][CELL_C2],
            "n_c3_organic_canonical": meta["n_c3_organic_canonical"],
            "floor_cleared": meta["floor_cleared"],
            "confirmatory_contrast": "C3_vs_C2 (two-sided, conservative lower bound)",
            "bh_survivors": survivors,
            "n_bh_survivors": n_survive,
            "c3_vs_c2_bh_p": {r["feature"]: r["bh_p"] for r in results},
            "c3_vs_c2_cohens_d": {r["feature"]: r["c3_vs_c2"]["d"] for r in results},
            "report": "paper/code/ws3/step7_rq5/step7_rq5.md",
            "figures": [str(p.relative_to(repo_root())) for p in figs],
        },
    )
    print(f"[done] RQ5 audience contrast — BH survivors ({n_survive}/5): {survivors or 'NONE'}")


if __name__ == "__main__":
    main()
