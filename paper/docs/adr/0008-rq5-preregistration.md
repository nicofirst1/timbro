# ADR-0008 — RQ5 pre-registration (human-baseline bracketing design, D10)

- **Status:** accepted — **BINDING pre-registration** (frozen 2026-07-08, before any RQ5 data
  was collected or any outcome computed). Secondary RQ: must not starve RQ1–RQ4.
- **Context:** RQ5 asks how instruction written *for agents* (SKILL.md) differs linguistically
  from instruction written *for humans* (README/CONTRIBUTING). Audience is perfectly collinear
  with era: essentially all provably-human instructional text pre-dates LLMs, all skills
  post-date them, so a two-cell comparison cannot identify an audience effect (complete
  separation, no common support — see D9 in [ADR-0007](0007-temporal-confounds-d9.md)). A
  dataset hunt (2026-07-08) confirmed `bigcode/the-stack` v1 provides a pre-ChatGPT human cell
  by construction (collected Nov 2021–Jun 2022). Frozen here before collection so the executing
  agent cannot tune cells or hypotheses to the data.

## Decision

### Design — three cells, bracketing estimand

| cell | audience | era | source |
|------|----------|-----|--------|
| C1 | human | pre-2023 | `bigcode/the-stack` v1, `README*`/`CONTRIBUTING*` `.md` files |
| C2 | human | post-2023 | current GitHub READMEs, created/updated ≥ 2023 (LLM-contaminated, expected) |
| C3 | agent | post-2023 | the existing skills corpus (WS1 canonical docs) |

**The algebra, stated honestly:** with no agent-pre cell, the textbook diff-in-diff
`(C3−C1) − (C2−C1)` reduces to `C3−C2`. The three-cell design is therefore a **bracketing
design**, not a classical DiD:

- **Lower bound (conservative):** `C3 − C2`. C2's LLM contamination pushes it *toward* the
  agent register, so this attenuates the audience effect — anything that survives it is real.
- **Upper bound:** `C3 − C1`. Includes the era shift; audience + era together.
- **Era shift itself:** `C2 − C1`, reported descriptively (a finding in its own right:
  how instructional register moved post-LLM).

The paper reports the audience effect as the bracket `[C3−C2, C3−C1]` per feature. Identifying
assumption, stated in the paper: contamination in C2 moves it toward C3's register (not away),
so the bracket contains the true audience effect. No parallel-trends language needed — the
bracketing argument replaces it.

### Data rules (frozen)

- **C1:** stream `bigcode/the-stack` (HF `streaming=True`, never a full download); keep files
  whose path basename matches `README*` or `CONTRIBUTING*` with `.md` extension; random sample
  ~20k docs, seed 42, sampling code committed.
- **C2:** READMEs from currently-active GitHub repos (GH API or a recent HF scrape), same
  filename filter, created or last-updated ≥ 2023. **Exclusion:** repos that contain a
  SKILL.md (or live in the skills corpus) are dropped from C2 — their READMEs blur audience.
- **C3:** the WS1 canonical skills corpus, unchanged.
- All cells: same dedup treatment as D1 (exact SHA256 + MinHash 0.9/5-gram); English-only
  filter (langdetect or equivalent, threshold logged) applied identically to all three cells;
  same `timbro analyze` feature extraction, no cell-specific preprocessing.
- **Floor:** ≥ 5,000 docs per human cell after dedup + language filter, else RQ5 downgrades to
  descriptive/exploratory and no hypothesis tests are reported.

### Confirmatory analysis (D10)

- **Feature family:** the same 5 confirmatory features as ADR-0004 (`dict_imperative_ratio`,
  `dict_hedge_per_1k`, `read_flesch_kincaid_grade`, `syn_mean_tree_depth`,
  `coh_lemma_overlap_adj`); `log(desc_tokens)` always a covariate, never a hypothesis.
- **Tests:** per feature, OLS `feature ~ cell + log_tokens`; the confirmatory contrast is
  `C3 vs C2` (the conservative bound), **two-sided** — no directional priors are
  pre-registered. BH at q=0.10 within the RQ5 family (its own family, separate from RQ1/RQ2/RQ4).
  Effect sizes standardized (Cohen's d on residualized features) with 95% CIs. Seeds 42.
- `C3−C1` and `C2−C1` are reported as descriptive brackets/context, not tested confirmatory.
- Everything beyond the 5 features is exploratory and labeled exploratory.
- **Register caveat, named in the paper:** README/CONTRIBUTING is a different *genre* than a
  skill file even for human audiences (announcement + orientation vs. pure procedure). The
  claim is scoped to "instructional/documentation register directed at humans vs. agents,"
  not to a genre-matched minimal pair. Genre-matched human procedure corpora (pre-2023
  wikiHow, SOPs) are named as future-work robustness, not collected now.

### Kill criteria (unchanged from PLAN.md)

If C1/C2 extraction fights back (license mess, dedup pain, coverage collapse) beyond ~2 days
of effort, RQ5 drops to a limitations paragraph ("a clean human comparison requires pre-2023
instructional corpora") and no partial results are reported.

## Consequences

- WS1 step 9 (`build_human_baseline.py`) implements the data rules above; WS3 step 7
  implements the analysis rules. Both cite this ADR; deviations go to
  `paper/code/ws3/DEVIATIONS.md` per D7.
- The era shift `C2−C1` doubles as a robustness input for D9's era-confound handling in RQ1
  ([ADR-0007](0007-temporal-confounds-d9.md)).
- Amendments require their own dated block or ADR before the corresponding analysis runs.
