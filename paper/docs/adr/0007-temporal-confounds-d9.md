# ADR-0007 — Temporal confounds: weekly-install outcome, age covariate, D9 (§8 amendment 2)

- **Status:** accepted — **BINDING pre-registration amendment** (2026-07-08; analysis has not
  run). Amends [ADR-0004](0004-ws3-preregistration.md); D1–D8 and the confirmatory feature
  family unchanged. LEDGER/code references to "§8 amendment 2" and "D9" resolve here.
- **Context:** skill creation date is a confounder through two distinct arrows:
  (1) **exposure** — cumulative installs/stars grow mechanically with age; an uncontrolled
  age→outcome path sits under every RQ2 regression on cumulative totals;
  (2) **cohort drift** — later-created skills are plausibly written differently
  (LLM-generated, template-scaffolded, post-dating published best practices), so features
  correlate with era; "dialects" could masquerade as era cohorts in RQ1.
  **Enabling discovery (2026-07-08):** every cached skills.sh detail page embeds the trailing
  weekly-install series in the sparkline `aria-label` ("Weekly installs: 18, 20, 30, …") —
  verified against the complete WS1 crawl cache: **19,906/19,906 skills carry it**. No
  re-crawl needed; WS1 re-parses the cache (PLAN.md WS1 step 8).

## Decision (verbatim §8 amendment 2)

- **Confirmatory RQ2 outcomes (supersedes the §8 outcome list):**
  - (a) **`log1p(installs_wk_recent)`** — mean of the skill's full available weekly-install
    series — **PRIMARY**. Exposure-normalized: old and new skills are compared on current
    velocity, not accumulated totals, which defuses arrow 1 at the outcome level.
  - (b) `log1p(total installs)` — retained as robustness, reported alongside.
  - (c) GitHub stars, single-skill repos only — unchanged.
  - ClawHub `downloads` is **removed** (source dropped 2026-07-08 —
    [ADR-0006](0006-drop-clawhub.md)).
- **Age covariate (mandatory — arrow 1 residual):** `log1p(skill_age_days)` at the skills.sh
  crawl date (2026-07-08), from the skill-diffs first commit date, enters **every RQ2
  regression** with the same standing as `log(desc_tokens)`: always a covariate, never a
  hypothesis. Rationale: weekly velocity still has lifecycle dynamics (older skills may be past
  their peak), so rate outcomes reduce but do not eliminate the age path.
- **D9 (era confound, mirrors D4/D8 — arrow 2):** bin `created_at` into calendar quarters.
  Compute Cramér's V between RQ1 register clusters and era bins; if V > 0.6, re-cluster within
  each of the two largest eras and report era-stratified results alongside the pooled view.
  Feature-drift-by-creation-quarter descriptives (do later-created skills carry different
  features?) are exploratory, never confirmatory.
- **§8b lagged exploratory now has data:** the weekly series is its basis. The window
  limitation (~8 weeks, single crawl anchor) must be stated wherever it is reported. An
  optional September re-crawl of the cached, resumable skills.sh recipe would extend the
  window — optional, not blocking.
- **Known limitation (for the manuscript):** skills.sh does not document how "weekly installs"
  is computed (dedup, bot filtering, week boundaries); carry the same install-noise caveat as
  Ling et al. The 9–16-value series must be inspected once before the re-parse is frozen
  (why longer? partial current week?) and the finding logged in the WS1 LEDGER.

### Correction (2026-07-08, post-inspection — does not modify the rules above)

The mandated inspection ran (WS1 LEDGER, "weekly-installs re-parse"): the "9–16 values on 975
pages" split in the enabling observation was a **parsing artifact** — skills.sh renders values
≥1,000 with a thousands-separator comma, so a naive `split(",")` overcounts. With the frozen
parse rule (separator `,\s+`, strip intra-value commas), **all 19,906 series are exactly 8
weekly values** (580 all-zero). The sparkline is always an 8-week window, single crawl anchor
2026-07-08. Output artifact: `skillssh_weekly.parquet` (owner/repo/skill-keyed join artifact,
not a `CORPUS_COLUMNS` field).

**Naming resolved (2026-07-08, user decision):** the pre-registered estimator stands — mean of
the full 8-week series. The column is named **`installs_wk_mean`** to match; the string
`installs_wk_recent` in the amendment text above denotes the same quantity (the pre-reg fixed
the estimator, not the column name).

## Consequences

- WS1 gains step 8 (`parse_weekly_installs` — cache re-parse, no re-crawl); `installs_wk_mean`
  becomes the primary RQ2 outcome in WS3 step 4.
- Guardrail update (PLAN.md §5.4): length AND age are always covariates.
- ~~Open naming flag from the LEDGER~~ resolved 2026-07-08: estimator = mean of the full
  8-week series, column renamed `installs_wk_mean` (see Correction above).
