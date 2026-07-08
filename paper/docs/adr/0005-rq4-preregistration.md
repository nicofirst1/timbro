# ADR-0005 — RQ4 pre-registration (§8b) + frozen chain mechanics

- **Status:** accepted — **BINDING pre-registration** (added 2026-07-07; chain mechanics
  frozen same day after the skill-diffs schema probe; embedding-delta exploratory added
  2026-07-08). No analysis has run.
- **Context:** RQ4 (temporal evolution of individual SKILL.md files) was promoted from an
  ad-hoc "bonus" to a pre-registered analysis; its mechanics had to be frozen BEFORE any
  outcome was computed. The text below is the pre-registered §8b of the master plan,
  **moved verbatim**. LEDGER/code references to "§8b" resolve here.

## Decision (verbatim §8b)

**RQ4:** How do individual SKILL.md files evolve linguistically across revisions, and does
linguistic evolution relate to adoption? Positioning: the self-evolving-skills literature
(SkillForge, SkillClaw, SAGE, etc.) improves skills by outcome but never characterizes WHAT
changes in the text; we measure exactly that.

**Data:** within-skill version chains reconstructed from skill-diffs. **Caveat (explicit):
chain-reconstruction mechanics (grouping keys, ordering field, minimum metadata) are pending a
schema probe of the HF dataset and will be frozen in a dated addendum BEFORE any RQ4 outcome is
computed.** Placeholder rules that do not depend on schema:
- chains require ≥3 versions;
- forks are excluded from chains (a chain lives in one repo);
- if fewer than 1,000 valid chains exist, RQ4 downgrades to descriptive/exploratory and no
  hypothesis tests are reported.

**Confirmatory hypotheses (separate family, BH q=0.10 within family):**
- **H4a** — revisions increase length: log token count rises across versions
  (comprehensiveness creep).
- **H4b** — skills converge toward their register-cluster centroid over revisions: z-distance
  on the 5 confirmatory features decreases with version index.

**Analysis:** mixed-effects models with skill as random effect, version index as predictor,
seeds 42.

**Exploratory (explicitly non-confirmatory):** whether style deltas precede adoption changes
(lagged install/star growth) — correlational only, no causal language.

### §8b addendum — chain mechanics FROZEN (2026-07-07; skill-diffs schema verified via HF datasets-server /info, /search + dataset card)

The schema probe promised above has run; the open placeholder is now frozen:

- **Source tables:** `diffs.parquet` (986,515 rows / 36 cols, full commit-by-commit table);
  use `diffs_clean.parquet` (130,631 rows) for true before/after pairs (`is_initial` excluded)
  and `skills_initial.parquet` (664,872 rows) for chain roots. (`repos.parquet`, 5,891 rows,
  carries per-repo n_skills/n_records/n_diff_pairs/license_spdx/stars/pushed_at;
  `bundled.parquet`, 630,119 rows, is sibling files at HEAD.)
- **Keys:** `skill_id` = stable ID per (repo, skill_path); `pair_id` = SHA1 of
  (skill, before_sha, after_sha). Root row has `is_initial=True` with NULL `before_*`.
- **Chain definition:** group by `skill_id`, order by `commit_date` (ISO 8601 w/ tz), require
  link integrity `before_sha == previous after_sha`; broken links split the chain and **only
  the longest contiguous segment is kept** (log the count of split chains).
- **Version count for the ≥3 rule** = number of distinct content states in the longest
  contiguous segment (initial + ≥2 linked diffs).
- **Fork exclusion:** `skill_id` is already repo-scoped; additionally, when a
  `skill_cluster_id` (dataset-shipped MinHash linkage, Jaccard≥0.7) spans multiple repos, only
  the chain of the `is_canonical` member enters RQ4 — the others are forks/copies.
- **Per-edit labels** (`intent_class`, `intent_confidence`, `intent_source`, `quality_tags`,
  `quality_score`; PR metadata `pr_title`/`pr_body`/`merged_at` when matched) may be used ONLY
  in the exploratory edit-taxonomy analysis — never as confirmatory predictors.
- **Chain-depth evidence** (the ≥3-version rule is feasible): `repos.parquet` shows
  n_records ≫ n_skills as the norm (e.g. 31 skills / 242 diff pairs ≈ 8.8 versions/skill); one
  skill_id (c4ffff46268f3035) has 250+ commits over 5 days with semver-tagged messages.
- **Access gotcha for WS1 implementers:** datasets-server `/first-rows` and `/rows` fail on the
  large configs ("Scan size limit exceeded", no page index); `/filter` errors regardless of
  quoting. Use `/search` (needs ~10–20s index warmup) or **download the parquet files directly**
  for bulk work — do not burn time on the row APIs.

### §8b addendum 2 — exploratory embedding-delta analysis (added 2026-07-08; NEVER confirmatory)

**Question:** how much of a skill's version-to-version movement in a learned semantic space is
explained by the interpretable linguistic feature deltas we already compute — and does the
degree of overlap differ by domain?

- **No training.** Frozen off-the-shelf sentence encoder only (default:
  `sentence-transformers/all-MiniLM-L6-v2`, chunk + mean-pool for texts over its context
  window; pin the exact encoder + pooling in a dated line before results are computed).
  Deliberately NOT a trained encoder-decoder on (v1→v2) pairs: a seq2seq's loss is dominated
  by copying, so its latent space encodes content/domain rather than edit direction, and
  training our own skill representations would erode the no-overlap claim vs
  `skillstructure2026`.
- **Data:** the same before/after pairs as RQ4 (`diffs_clean.parquet`, chain rules above).
  Δemb = emb(after) − emb(before); Δfeat = Timbro feature-vector delta (features already
  computed for RQ4 — no new extraction).
- **Analysis:** CCA / linear probe from Δfeat to Δemb; report shared variance (R²), overall
  and split by domain (D8 domain labels). Correlational language only.
- **Purpose:** pilot for a possible follow-up paper (trained edit-representation model). If
  shared variance is high, linguistic features capture most of what a semantic space sees in
  skill edits; if low, that gap motivates the follow-up. Either way it stays out of the
  confirmatory families and out of the abstract's claims.

## Consequences

- WS1 emits the version-chain table per the frozen mechanics (done 2026-07-08 — LEDGER:
  289,145 version-rows / 218,626 chains / 14,388 RQ4-eligible, above the 1,000 floor, so RQ4
  stands as a real analysis).
- RQ4 hypothesis tests run only under these rules; the lagged-adoption exploratory uses the
  weekly-install series from [ADR-0007](0007-temporal-confounds-d9.md).
