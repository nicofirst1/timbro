# ADR-0004 — WS3 pre-registered analysis rules (§8, D1–D8)

- **Status:** accepted — **BINDING pre-registration** (decided 2026-07-04 while capable-model
  access existed; amended 2026-07-07 before any analysis ran). Outcome list partially
  superseded by [ADR-0007](0007-temporal-confounds-d9.md) (§8 amendment 2).
- **Context:** analysis rules were frozen before touching the data so that a less capable
  executing agent cannot p-hack or silently substitute. The text below is the pre-registered
  §8 of the master plan, **moved verbatim** — amendments are dated blocks, never in-place
  edits. LEDGER/code references to "§8" and "D1"–"D8" resolve here.

## Decision (verbatim §8)

Every reported number follows the **`experiment-discipline` skill**: produced by a committed
script with a logged run manifest (git commit, data hash, seed). Seeds are always 42.

**Confirmatory feature family (5 + covariate):** `dict_imperative_ratio`, `dict_hedge_per_1k`,
`read_flesch_kincaid_grade`, `syn_mean_tree_depth`, `coh_lemma_overlap_adj`; `log(desc_tokens)`
is always a covariate, never a hypothesis. Everything else is exploratory and must be labeled
exploratory in the paper.
**Confirmatory outcomes:** ClawHub `downloads`; skills.sh installs (if the probe succeeds);
GitHub stars **only** on single-skill repos.
*(Superseded 2026-07-08 — see [ADR-0007](0007-temporal-confounds-d9.md): primary outcome is
now the trailing weekly install rate; ClawHub downloads removed.)*

Decision rules — follow literally, log any trigger in `paper/ws3/DEVIATIONS.md`:
- **D1 dedup:** if near-dup removal cuts skill-diffs by >60% (fork explosion), the unit of
  analysis becomes the near-dup cluster: one canonical doc + `cluster_size` as covariate.
  Never treat near-duplicates as independent observations.
- **D2 scale:** descriptives on the full canonical corpus; regressions/clustering on a
  platform-stratified 50K sample if the corpus exceeds 100K docs.
- **D3 clustering:** HDBSCAN (`min_cluster_size=200`) on PCA components covering 90% variance.
  If noise >50% or <3 clusters → k-means, k ∈ {4..12} by silhouette. If best silhouette <0.10 →
  declare "no discrete dialects" and report the top-5 PCA axes as continuous dimensions instead.
  That outcome is a finding, not a failure — do not keep re-clustering until something appears.
- **D4 platform confound:** if cluster↔platform Cramér's V >0.6, re-cluster within each
  platform and report both views.
- **D5 slop check:** organic-vs-stub logistic AUC. If AUC >0.99, run drop-one-feature ablation
  and report the ablated AUC alongside (template-leakage guard).
- **D6 adoption:** Benjamini–Hochberg at q=0.10 over the 5 confirmatory features only. If
  nothing survives → report the null with minimum detectable effect. No promoting exploratory
  hits to headline claims.
- **D7 spec/reality conflict** (schema changed, counts wildly off, endpoint gone): stop, log
  the discrepancy, ask the user. Do not silently substitute.

### §8 amendment (2026-07-07 — pre-registration amendment; analysis has not run. D1–D7 and the confirmatory family above are unchanged)

- **Construct-validity citations per confirmatory feature** (from
  `paper/literature/lit_review_psycholinguistics.md`): `dict_imperative_ratio` ← Vander Linden &
  Di Eugenio 1996 (COLING-96, imperatives in instructional text); `dict_hedge_per_1k` ←
  Hyland 1998/2005; `read_flesch_kincaid_grade` ← Kincaid et al. 1975 (Bailin & Grafstein 2001
  critique motivates pairing with `syn_*`/`coh_*`); `syn_mean_tree_depth` ← Gibson 1998
  (Dependency Locality Theory) + Lu 2010; `coh_lemma_overlap_adj` ← Grosz/Joshi/Weinstein 1995
  (Centering) + Barzilay & Lapata 2008 (entity grid).
- **New exploratory covariate (explicitly NOT confirmatory):** description-field
  completeness/quality — the practitioner review (`paper/literature/lit_review_practitioner.md` §6) argues
  the `description` frontmatter field is its own activation mechanic, distinct from body-prose
  linguistic features. Exploratory only; labeled exploratory in the paper.
- **WS3 method framing:** Biber's Multidimensional Analysis (Biber 1988; Biber & Egbert 2018 at
  web scale, with how-to/instructional pages as a register category) is the direct
  methodological precedent for the standardize→PCA→cluster→name-by-deviant-features pipeline —
  "established method, new corpus."
- **D8 (domain confound, mirrors D4 — added 2026-07-07):** each skill gets a deterministic
  domain label — use marketplace category metadata where present (ClawHub categories);
  otherwise TF-IDF k-means topic assignment on content-word lemmas, k=10, seed 42, clusters
  hand-labeled ONCE before any outcome analysis and frozen. Then: Cramér's V between register
  clusters and domain labels; if V > 0.6, re-run clustering within each of the two largest
  domains and report domain-stratified results as the primary RQ1 finding. Domain label also
  enters every RQ2 regression as a fixed effect.
- **D1 interaction note (added 2026-07-07 — does not modify D1's text):** the MinHash near-dup
  collapse (D1 / WS1 step 5) applies to the **RQ1–RQ3 cross-sectional corpus** (latest snapshot
  per skill); **RQ4 uses the pre-dedup version chains** keyed within a single repo.
  `build_skill_diffs.py` (WS1) must therefore emit BOTH: the deduped latest-snapshot table and
  a version-chain table (see PLAN.md WS1 step 1 and [ADR-0005](0005-rq4-preregistration.md)).
- **D1 shipped-dedup note (added 2026-07-07, post schema probe — does not modify D1's text):**
  the skill-diffs dataset ships its own MinHash clusters (`skill_cluster_id`, Jaccard≥0.7, plus
  `skill_semantic_cluster_id`, embedding cos≥0.85, with `is_canonical`/`is_semantic_canonical`
  flags) — MORE aggressive than D1's pre-registered 0.9. **Decision:** D1's own 0.9 / 5-gram
  dedup remains the pre-registered primary for the RQ1–RQ3 cross-sectional corpus; the shipped
  `skill_cluster_id`/`is_canonical` is used (a) as a robustness check reported alongside, and
  (b) as the fork-linkage tool for RQ4 exclusions ([ADR-0005](0005-rq4-preregistration.md)
  addendum). Rationale: preserves the pre-registration while not reimplementing fork detection.
- **Folk-advice feature family (added 2026-07-07 — exploratory, never confirmatory):**
  practitioner-tip features specced in issue #21 (`struct_` additions, `fm_desc_` group,
  `dict_` additions); used only in exploratory RQ2 analyses testing community advice;
  multi-file tips (progressive disclosure, one-folder-per-skill, auxiliary docs) are computed
  as corpus-level columns in WS1 from skill-diffs `bundled.parquet` (sibling files at HEAD),
  not in `timbro analyze`.
- **Plain-language feature family (exploratory, never confirmatory):** English ports of codified
  easy-language rules (issue #22), concepts from public doctrine (DIN SPEC 33429, CDC Clear
  Communication Index, plainlanguage.gov) — klartext (Fraunhofer, internal-use license) provided
  the audit map only; no code or lexicons from it. Enables the exploratory question: does the
  machine-directed SKILL.md register convergently adopt codified plain-language norms? Second
  reference register for RQ1 alongside Biber's dimensions.

## Consequences

- WS3 scripts implement these rules literally; every triggered decision rule is logged in
  `paper/analysis/DEVIATIONS.md`.
- Later amendments require their own dated ADR before the corresponding analysis runs
  ([ADR-0007](0007-temporal-confounds-d9.md) is the first).
