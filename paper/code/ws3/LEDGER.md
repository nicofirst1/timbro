# WS3 ledger — corpus analysis

Canonical results ledger for WS3 (experiment-discipline §4). Numbers are cited from
generated artifacts (`FINDINGS.md`, figures, manifests), never retyped. Newest on top.
Analysis rules are pre-registered in ADR-0004/0005 (D1–D9) and bind over this file.

## PENDING

- [x] machine-cell projection probe (ADR-0009 exploratory) — **Done 2026-07-09 13:37.**
      587 known-machine docs projected into the frozen step-3 geometry; 80% land blob/noise,
      20% in the diffuse island 8, 0 in any tight (template-farm) island. See RESULTS +
      `../ws1/manifests/step3_machine_projection.parquet.manifest.json`.
- [x] island dedup-linkage probe (exploratory follow-up) — **Done 2026-07-09 13:39.**
      0 duplicate near_dup_cluster_id in-population (canonical-by-construction confirmed);
      8/10 islands are 100%/99% single-repo template farms; 6,846 canonical heads = 12,595
      corpus footprint. See RESULTS + `../ws1/manifests/step3_island_dedup.parquet.manifest.json`.

## STATUS

- [x] `extract_features.py` — step 1 (production run), supersedes the `featurize.py`
      scaffold below. **Done 2026-07-09 11:01** (cleared from PENDING 2026-07-09 11:14).
      features.parquet 231,426 rows / 139 cols, gates passed — see RESULTS +
      `../ws1/manifests/features.parquet.manifest.json`. Parallel (multiprocessing Pool,
      per-worker spaCy load), resumable via `paper/data/features_parts/part-*.parquet`,
      per-doc `analyze_error`.
- [x→superseded] `featurize.py` — step 1 scaffold: corpus.parquet canonical docs →
      features.parquet. **Scaffolded + unit-tested** (TDD, ponytail) 2026-07-08. Pure seam
      `featurize_rows` filters `is_canonical`, carries metadata forward. **Superseded for
      the real run by `extract_features.py`** (2026-07-09): the scaffold was canonical-only,
      in-memory (`to_pylist()`), non-parallel, non-resumable, and deferred the manifest —
      `extract_features.py` adds all of those + the ADR-0010 install-labeled union scope
      needed for RQ2. Scaffold + its `test_featurize.py` kept as-is (pure-seam reference).
- [x] descriptives (step 2) — `descriptives.py`. **Done 2026-07-09 11:29.** Per-source/
      platform median/IQR + organic-vs-slop separability. FULL CV AUC 1.000 — perfect but
      **corpus-provenance separation, not a linguistic-dialect finding** (D5 ablation fired,
      stays 1.000). See RESULTS + `../ws1/manifests/step2_descriptives.md.manifest.json`.
- [x] machine-cell feature extraction (ADR-0009 exploratory prep) —
      `extract_features_machine.py`. **Done 2026-07-09 12:14.** 587/587 rows, 0 failures.
      See RESULTS + `../ws1/manifests/features_machine.parquet.manifest.json`.
- [x] machine-cell projection probe (ADR-0009 exploratory) — `step3_machine_projection.py`.
      **Done 2026-07-09 13:37.** Reproduced the step-3 geometry via `clustering.py` seams
      (asserted vs. manifest), projected the 587 machine docs; 80% blob/noise, 20% island 8,
      0 tight-island. Reading leans to a *refinement of* hyp. (b) — tight islands are
      template farms (organic repos), the known-machine cell is diverse (blob-like), so
      neither (a) nor (b) as stated holds. See RESULTS +
      `../ws1/manifests/step3_machine_projection.parquet.manifest.json`.
- [x] RQ1 clustering (step 3) — PCA → HDBSCAN; confound gates D4/D8/D9. **Done
      2026-07-09 13:00.** Weak structure (k-means k=5, silhouette 0.1129) after
      pre-registered HDBSCAN fallback; D4/D8/D9 gates un-fired. See RESULTS +
      `../ws1/manifests/rq1_cluster_assignments.parquet.manifest.json`.
- [x] RQ2 adoption (step 4) — regressions on `log1p(installs_wk_mean)`; BH per D6. **Done
      2026-07-09 15:32.** 9,686/9,686 weekly-join coverage; 1/5 confirmatory survives BH
      (`dict_imperative_ratio` +0.107 [+0.069, +0.145], durable across total-installs +
      canonical-only), other 4 null. See RESULTS + `../ws1/manifests/rq2_adoption_rows.parquet.manifest.json`.
- [ ] RQ4 temporal (step 5) — chains ≥3 versions (ADR-0005).
- [ ] holdout (step 6) — `rq2_holdout_candidates.parquet` drift characterization.
- [ ] `run_all.py` — re-runnable driver + generated `FINDINGS.md` (acceptance).

## PRE-REG — WS3 corpus analysis (2026-07-08)

- **Goal:** from the WS1 corpus, answer RQ1 (linguistic dialects), RQ2 (adoption), RQ4
  (temporal evolution) under the frozen ADR-0004/0005 rules. Confirmatory outcomes and
  covariates are fixed there; nothing below re-decides them.
- **Feature source:** `main`'s `timbro analyze` only (#17/#18) — deterministic, no LLM, no
  network (guardrail 5). Feature set is frozen by those closed issues; WS3 does not add
  features.
- **Binding rules carried in:** length + age always covariates; BH multiple-comparison
  correction (D6); effect sizes with CIs; platform (D4) / domain (D8) / era (D9) confound
  gates on any RQ1 cluster claim. Deviations logged in `DEVIATIONS.md`, not silently taken.

## PRE-REG — WS3 step 1 feature extraction (2026-07-09)

- **Goal:** produce one deterministic feature vector per RQ1/RQ3 canonical doc and per
  RQ2 install-labeled representative, for downstream analysis. This is **not** a hypothesis
  test — the "results" are counts, coverage, and failure rates (a corpus-construction step,
  like WS1). No claim ladder rung is at stake; the §2 gate here is drift + failure-rate +
  column-coverage, not confound/leakage.
- **Data:** `paper/data/corpus.parquet` (`../ws1/manifests/corpus.parquet.manifest.json`,
  output_sha256 `5b7f02f0…`, 672,022 rows, pyarrow 24.0.0, git `e73139c`). Feature function:
  `timbro.analyze.analyze_text` (repo `src/timbro/analyze.py`), a fixed spaCy
  `en_core_web_sm` + textdescriptives + lexicon computation. **No LLM, no network, no seed
  — deterministic** (satisfies WS3 guardrail 5; the seed-42 rule applies to downstream
  clustering/CV, not to this deterministic feature pass).
- **Scope rule (pre-registered):**
  `is_canonical == "true"` **UNION** `installs` non-null / non-empty.
  - `is_canonical` is a **STRING** column with literal values `"true"` / `"false"` (NOT
    bool). Naive truthiness would keep all 672,022 rows — the filter compares to the string
    `"true"`.
  - Expected Ns (from `corpus.parquet.manifest.json`, verified empirically before launch):
    canonical = **227,407** (`n_canonical`); install-labeled = **9,686** (`n_entries_matched`);
    labeled-only (labeled AND not canonical) = **4,019**; union = **231,426**
    (= 227,407 + 4,019, arithmetic reconciles).
- **Output:** `paper/data/features.parquet` — carry columns
  `skill_id, source, platform, near_dup_cluster_id, is_canonical, installs` + all 132
  `analyze_text` keys (flat) + `analyze_error` (null normally; per-doc exception message
  otherwise — one bad doc never crashes the run). Resumable parts under
  `paper/data/features_parts/`.
- **Confirms if:**
  - union row count matches the scope arithmetic computed from
    `corpus.parquet.manifest.json` (231,426);
  - analyze failures **< 1%** of selected rows;
  - all feature columns present on **> 99%** of rows.
- **Would NOT confirm / STOP if:**
  - `n_canonical` ≠ **227,407** (D7-style upstream drift — the corpus changed under us);
    the script asserts this and aborts. Record + consult user.
  - analyze failures **≥ 1%** — stop, record the failing docs' error messages, consult user.
- **Scope-deviation note (pre-run decision, dated 2026-07-09):** `PLAN.md §WS3.1` (and the
  `featurize.py` scaffold) scope feature extraction to "canonical docs". This run **extends**
  the scope to also include the ADR-0010 install-labeled entry-level representatives (the
  +4,019 labeled-but-non-canonical rows). Rationale: `is_canonical` is text-dedup-chosen and
  **install-blind** (ADR-0010), so a canonical-only extraction would leave the RQ2
  install-labeled representatives **without feature vectors** — RQ2 could not run. This is a
  scope *extension* (superset of the pre-registered canonical set), not a substitution;
  canonical docs are unaffected. Logged here per experiment-discipline §1 before the run;
  also belongs in `DEVIATIONS.md` when that file lands.
- **Repro:**
  ```
  git commit  e73139c (paper branch, -dirty: adds paper/code/ws3/extract_features.py)
  corpus sha  5b7f02f07961c86b57ee6e3b6da299e09b80566ed9f7896d1306f66e203c9011
  spacy 3.8.14 · en_core_web_sm 3.8.0 · pyarrow 24.0.0 · textdescriptives 2.8.2
  deterministic pipeline, no seed
  nohup env PYTHONUNBUFFERED=1 uv run --with-requirements paper/code/ws1/requirements.txt \
      python paper/code/ws3/extract_features.py
  ```

## PRE-REG — WS3 step 2 descriptives + slop separability (2026-07-09 11:22)

- **Goal / hypothesis:** Two goals. (a) **Descriptive** — how do the 130 numeric
  `analyze_text` features distribute per source and per platform (median/IQR), and what
  do a named set of headline features look like across organic vs. slop? (b) **Separability
  probe (validation, not a confirmatory RQ)** — can a simple logistic model tell organic
  SKILL.md docs from the `slop_stub` marketplace-listing corpus using the linguistic
  features? Expectation: some separability (the two corpora were built differently), but the
  honest question is **how much of it is just length** — slop stubs are short marketplace
  blurbs, so length features could carry the signal on their own. This step earns at most an
  **"Observed"** claim (§3); it is not a hypothesis test with an inferential test statistic,
  so no "significant"/"validated" language.
- **Data / population:** `paper/data/features.parquet` (manifest
  `../ws1/manifests/features.parquet.manifest.json`, `output_sha256` `b999c8e9…`,
  231,426 rows × 139 cols). **Analysis population = canonical rows only**
  (`is_canonical == "true"` — STRING comparison; the naive truthiness of the literal
  "false" would keep every row). Canonical = **227,407**. **The 4,019 labeled-only extras
  are RQ2-specific (ADR-0010 install representatives) and are EXCLUDED here.** Then **drop
  the rows with non-null `analyze_error`** (log the count; expected 4 in canonical from step
  1). Classes: positive = `source == "slop_stub"` (5,147 canonical before error-drop);
  organic = `source ∈ {skill_diffs, graph_of_skills}` (222,220 + 40 = 222,260 before drop).
  Verified empirically pre-run: canonical source counts = {skill_diffs 222220,
  graph_of_skills 40, slop_stub 5147}; canonical `analyze_error` non-null = 4.
- **Feature set for the probe:** the **130 numeric** `analyze_text` feature columns (all
  non-carry columns; carry/identity columns `skill_id, source, platform,
  near_dup_cluster_id, is_canonical, installs, analyze_error` and the two JSON string
  columns `frontmatter_json, dict_plain_replacements_json` are excluded — not features).
  34 of the 130 have some nulls (undefined metrics on short docs: SMOG needs ≥30 sentences,
  coherence/syntax need ≥2 sentences). **Null policy (pre-registered): median imputation
  fitted per-fold inside the CV pipeline** (`SimpleImputer(strategy="median")` →
  `StandardScaler` → `LogisticRegression`), so no rows are dropped and imputation never
  leaks across folds. No constant/zero-variance columns exist in the canonical set (checked).
- **Descriptives (pre-registered):** per-source and per-platform **median + IQR (Q1, Q3)**
  for every numeric feature, written to the summary table. Distribution figures (organic vs.
  slop overlaid) for this **named headline set of 10** spanning the feature families
  (named BEFORE running):
  1. `dict_imperative_ratio` (imperative)
  2. `dict_hedge_per_1k` (hedging)
  3. `dict_conditional_per_1k` (conditional/instructional)
  4. `dict_second_person_per_1k` (address / directive register)
  5. `read_flesch_kincaid_grade` (readability)
  6. `syn_mean_tree_depth` (syntactic complexity)
  7. `coh_lemma_overlap_adj` (cohesion)
  8. `lex_mtld` (lexical richness)
  9. `struct_code_char_ratio` (structure / code density)
  10. `desc_tokens` (document length)
- **Separability probe (pre-registered):** scikit-learn `LogisticRegression`
  (`class_weight="balanced"`, `max_iter=1000`), features standardized (per-fold), evaluated
  with **5-fold `StratifiedKFold`, seed 42 (D1)**. Primary metric: **ROC-AUC, reported as
  mean ± sd across the 5 folds**. Three models, all pre-registered:
  - **FULL** — all 130 numeric features.
  - **LENGTH-ONLY baseline** — the length family only:
    `desc_tokens, desc_unique_tokens, desc_characters, desc_sentences, struct_line_count`
    (raw document-size counts; named here before running).
  - **FULL − LENGTH** — the 125 features that remain after removing those 5 length columns.
- **MANDATORY confound guard (§2 + spirit of D5):** report all three AUCs side by side. If
  **FULL-model AUC ≈ LENGTH-ONLY AUC**, the honest reading is "separability is largely
  length-driven" and it is written that way, not as "the linguistic features separate the
  classes". D5's own rule also fires: **if FULL AUC > 0.99, run a drop-one-feature ablation**
  (template-leakage guard) and report the ablated AUC alongside.
- **Also report:** the **top-10 most-separating features** = the 10 largest `|coef|` on
  standardized inputs, from a single FULL logistic fit on the whole canonical set (same
  pipeline, refit on all rows — reported as a descriptive ranking, distinct from the CV AUC).
- **Confirms if:** class counts at split time match the manifest-derived expectations
  (canonical 227,407; slop_stub 5,147 minus any that carried an `analyze_error`; organic the
  remainder) AND the harness produces three finite AUCs. This "confirms" only the descriptive
  goal — there is no confirmatory hypothesis on the ladder here.
- **Would NOT confirm / STOP if:** canonical class counts do NOT match the above (e.g.
  slop_stub ≠ 5,147, or canonical ≠ 227,407) → **STOP, record, consult user** (D7-style
  drift under us). Also STOP if `analyze_error`-drop removes more than the expected 4 in
  canonical (upstream change).
- **Repro pins (fixed before the run):**
  ```
  git commit  <paper branch, -dirty: adds paper/code/ws3/descriptives.py + requirements.txt>
  input       features.parquet  sha256 b999c8e99df4349c432c118446c8250b7ad295b58971a4bdaee23b8de13f7b2e
  seed        42 (StratifiedKFold shuffle; D1)
  env         uv run --with-requirements paper/code/ws3/requirements.txt python paper/code/ws3/descriptives.py
  pins        scikit-learn / pandas / matplotlib / numpy / pyarrow versions recorded in the manifest
  ```

## PRE-REG — WS3 machine-cell feature extraction (2026-07-09 12:12) [ADR-0009 exploratory]

- **Goal:** NOT a hypothesis test. `paper/data/src_machine_cell.parquet` is a separate,
  standalone table (machine-authored SKILL.md cell, ADR-0009) — it is never merged into
  `corpus.parquet` and carries its own manifest. This step produces the same 132
  `analyze_text` feature vectors for it that `extract_features.py` produces for the main
  corpus, purely as descriptive prep for later exploratory comparison. No claim ladder rung
  is at stake here; the gate is row-count + failure-rate + column-coverage only, same as
  WS3 step 1.
- **Data:** `paper/data/src_machine_cell.parquet` (`../ws1/manifests/src_machine_cell.parquet.manifest.json`,
  `output_sha256` `28f022cc…`, **587 rows**, 18 cols = the corpus carry columns +
  `generator_model, domain, task_family`). Verified empirically pre-run: table has 587 rows.
- **Scope rule:** ALL 587 rows — no canonical filter. The cell is standalone (not merged
  into corpus.parquet), so `is_canonical`/`installs` scope logic from step 1 does not apply.
- **Feature source:** `timbro.analyze.analyze_text` (repo `src/timbro/analyze.py`) — same
  deterministic pipeline as step 1, reused via import (no logic duplication) from
  `extract_features.py`'s `_analyze_one` / `_rows_to_table` / `_feature_keys` /
  `_worker_init` seams.
- **Output:** `paper/data/features_machine.parquet` — carry columns `skill_id, source,
  generator_model, domain, task_family` + all 132 `analyze_text` feature keys (flat) +
  `analyze_error` (`pa.string()`, null normally). Manifest via WS1 `write_manifest`.
- **Confirms if:** output row count == **587** (assert against the machine-cell manifest's
  `n_rows`); analyze failures **< 1%** of 587; all feature columns present on **> 99%** of
  rows.
- **Would NOT confirm / STOP if:** row count read from `src_machine_cell.parquet` ≠ 587
  (upstream drift on a table this step does not own — stop, record, consult user); analyze
  failures **≥ 1%** — stop, record the failing docs' error messages, consult user.
- **Repro pins (fixed before the run):**
  ```
  git commit  <paper branch, -dirty: adds paper/code/ws3/extract_features_machine.py>
  input       src_machine_cell.parquet  sha256 28f022cc3406d5413d3df97c8628f732948dd0cd3481f2ec906ef8fcaa4afc
  spacy 3.8.14 · en_core_web_sm 3.8.0 · pyarrow 24.0.0 · textdescriptives 2.8.2
  deterministic pipeline, no seed
  uv run --with-requirements paper/code/ws1/requirements.txt \
      python paper/code/ws3/extract_features_machine.py
  ```

## PRE-REG — WS3 step 3 RQ1 clustering / instruction dialects (2026-07-09 12:14)

- **Goal / hypothesis (RQ1):** do the deterministic linguistic features of *organic* agent
  skill files cluster into distinct "instruction dialects" (imperative-dense vs.
  conditional-rich vs. narrative, per the original research-report heuristic table)? This is
  an **exploratory / descriptive** structure-discovery step (Biber-style
  standardize→PCA→cluster→name-by-deviant-features; Biber 1988, Biber & Egbert 2018), NOT a
  confirmatory hypothesis test. It earns at most an **"Observed"** claim (§3): "the corpus
  does / does not partition into k separable feature clusters." No "significant"/"validated"
  language; ADR-0004 D3 explicitly says "no discrete dialects" is itself a finding, not a
  failure, and forbids re-clustering until something appears.
- **Data / population:** `paper/data/features.parquet` (manifest
  `../ws1/manifests/features.parquet.manifest.json`, `output_sha256` `b999c8e9…`,
  231,426 rows × 139 cols). **Analysis population = organic canonical docs:**
  `is_canonical == "true"` (STRING comparison; ADR-0010 §2 — RQ1/RQ3 filter is_canonical,
  unit = near-dup cluster via its canonical representative) **AND** `analyze_error` is null
  **AND** `source != "slop_stub"`.
  - **Slop-exclusion justification (from ADR text, not silent):** RQ1 (PLAN §1) asks about
    dialects "across ecosystems (Claude Code, OpenClaw, OpenCode, Hermes)". `slop_stub` is not
    an ecosystem — it is the **synthetic marketplace-listing corpus that ADR-0004 D5 assigns
    to the separate organic-vs-stub AUC probe**, not to the dialect clustering population.
    Step 2 (2026-07-09 11:29) showed slop is a degenerate ~22-token provenance slice
    (CV AUC 1.000, provenance-driven) that would dominate any distance-based clustering.
    Including it would answer "does provenance separate?" (already answered by D5), not
    "do organic dialects exist?" (RQ1). ADR-0010 §2 does not re-add slop to RQ1; D5 owns it.
    Decision: **EXCLUDE slop_stub from RQ1 clustering.** (The 4,019 RQ2 install-labeled extras
    are also excluded — non-canonical, ADR-0010 §3 RQ2-only.)
  - Expected N (verified empirically pre-run against the manifest): canonical = 227,407;
    minus 4 `analyze_error`; minus 5,147 slop_stub (0 error-dropped) →
    **222,256 organic canonical error-dropped docs**. Source split at that N:
    `skill_diffs 222,216 + graph_of_skills 40`. Platform split:
    `claude_skill 152,806 · opencode_skill 33,007 · openclaw_skill 26,120 ·
    hermes_skill 10,283 · <null, the 40 graph_of_skills> 40`.
- **Feature set + preprocessing (pre-registered):** the **130 numeric** `analyze_text`
  feature columns (all non-carry, non-JSON columns — same 130 as step 2). **Null policy:**
  34/130 have nulls on short docs (SMOG needs ≥30 sentences, coherence/syntax ≥2). This is
  **unsupervised** (no folds), so imputation cannot leak: **median-impute (fit on the full
  organic canonical set) then StandardScaler (z-score, same fit set).** No rows dropped. Any
  zero-variance column appearing after subsetting is dropped before PCA (record which).
- **PCA (D3):** `sklearn.decomposition.PCA(random_state=42)` on the standardized matrix;
  **retain the smallest #components with cumulative explained variance ≥ 0.90** (D3: "PCA
  components covering 90% variance"). Record component count + top-axis loadings.
- **Sampling (D2 — MANDATORY, corpus > 100K):** ADR-0004 **D2**: "clustering on a
  platform-stratified 50K sample if the corpus exceeds 100K docs." 222,256 > 100,000 → **D2
  fires.** Draw a **platform-stratified sample of 50,000** (stratify on `platform`;
  proportional per-stratum allocation; the 40 null-platform graph_of_skills rows are their own
  tiny stratum, retained), **seed 42**. **PCA is fit on this 50K; HDBSCAN clusters the 50K.**
  The remaining ~172K docs are assigned by **nearest cluster centroid in PCA space**
  (centroid = mean PCA coords of each non-noise cluster's members; distance recorded so a
  "far from every centroid" tail is visible). Confound gates (D4/D8/D9) computed on the
  **full assigned set**; discovery diagnostics (silhouette, noise fraction) reported on the
  **50K clustered sample** (their pre-registered basis).
- **HDBSCAN (D3):** `sklearn.cluster.HDBSCAN` (sklearn ≥1.4 — no new dep) with
  **`min_cluster_size=200`** (D3 verbatim) and **`min_samples=None`** (library default; no
  per-project override is pre-registered, so take + record the default). Euclidean on the
  retained PCA components. HDBSCAN is deterministic given input; the 50K draw's seed=42 is the
  only stochastic pin.
- **k-means fallback trigger (D3, verbatim):** if **HDBSCAN noise fraction > 0.50 OR non-noise
  clusters < 3** → `KMeans(random_state=42)` over **k ∈ {4..12}**, pick k by **highest mean
  silhouette** (on the 50K sample, or a seeded 10K sub-sample of it if silhouette is too slow,
  stated). **If best silhouette < 0.10 → declare "no discrete dialects" and report the top-5
  PCA axes as continuous dimensions** (D3 verbatim — a finding, not a failure; do NOT
  re-cluster).
- **Cluster naming rule:** for each non-noise cluster, rank features by **|standardized median
  of the cluster|** (0 = global standardized median by z-scoring) and name by its **top
  deviant features** (report signed standardized median of the top ~8). Map onto the
  original-report heuristic table (imperative-dense / conditional-rich / narrative / …) where
  the deviant signature matches; where it does not, say so — do not force a label.
- **Confound gates (computed on the full assigned set):**
  - **D4 platform (verbatim):** cluster ↔ `platform` contingency; **Cramér's V**. **V > 0.6 →
    re-cluster within each platform, report both views.** "Merely platform-driven" = V > 0.6
    AND clusters map ~1:1 onto platforms — reported as an ecosystem effect, not a dialect.
  - **D8 domain (verbatim; ClawHub moot per ADR-0006 → TF-IDF path):** no marketplace category
    metadata survives (ADR-0006 routes D8 to TF-IDF). **Domain proxy = TF-IDF k-means on
    content-word lemmas, k=10, seed 42** (D8 verbatim), fit on raw `text` from
    `corpus.parquet` (join by `skill_id`; text 100% non-null). Content-word lemmas
    approximated by a deterministic `TfidfVectorizer` (English stop-words, lowercase,
    alphabetic tokens ≥3 chars, `max_features=20000`, `min_df=5`) — NOT a spaCy re-parse
    (deterministic, fast, no new dep; the lemma approximation is recorded as a limitation).
    D8's "hand-labeled ONCE before any outcome analysis and frozen" clause binds **RQ2** (it
    has an outcome); **RQ1 clustering is unsupervised with no outcome**, so here the k=10
    assignment is used **unlabeled** only to compute **Cramér's V between register clusters and
    the 10 domain labels**; top TF-IDF terms per domain reported for interpretability, no
    frozen taxonomy claimed at this step. **V > 0.6 → re-run register clustering within each of
    the two largest domains, report domain-stratified as the primary RQ1 finding** (D8
    verbatim).
  - **D9 era (verbatim, ADR-0007):** bin `created_at` (from `corpus.parquet`, join by
    `skill_id`; 99.98% non-null — null/unparseable excluded from the era gate only, count
    recorded) into **calendar quarters**; **Cramér's V** between register clusters and era
    bins. **V > 0.6 → re-cluster within each of the two largest eras** (2026Q1 ≈ 154.7K,
    2026Q2 ≈ 62.0K) **and report era-stratified alongside pooled** (D9 verbatim). Feature-drift
    -by-quarter is exploratory, not run unless a gate fires.
- **Seed:** 42 everywhere stochastic (D1): the 50K draw, TF-IDF k-means, any k-means register
  fallback. HDBSCAN + PCA deterministic given input.
- **Confirms if (descriptive goal met):** pipeline runs end-to-end on the pre-registered
  population at N=222,256 (asserted before running — mismatch → STOP), produces a component
  count for ≥90% variance, a clustering outcome (HDBSCAN clusters, D3 k-means fallback, or the
  D3 "no discrete dialects" declaration), and the three confound-gate Cramér's V values with
  triggered/not-triggered decisions. RQ1's answer is **whatever the pipeline reports** —
  discrete dialects, continuous dimensions, or confound-dominated structure are all valid
  Observed outcomes.
- **Would NOT confirm / STOP if:** organic canonical error-dropped N ≠ 222,256, OR slop leaks
  in, OR source/platform counts mismatch the manifest split (D7-style drift — the script
  asserts N and aborts; record + consult user). High noise, low silhouette, or a fired
  confound gate are **NOT** stop conditions — they are the pre-registered findings.
- **Robustness (§2) plan:** (a) degenerate slice — slop excluded by construction; watch for a
  residual short-doc cluster and name it honestly. (b) missing data — median impute, no rows
  dropped, N stated. (c) confound/leakage — this IS the D4/D8/D9 battery. (d) inferential test
  — N/A (unsupervised descriptive; Cramér's V + silhouette reported as association/cohesion
  descriptives, no significance claim). (e) n/subset — 50K stratified discovery + full ~222K
  assignment, both stated. (f) pilot vs full — full organic canonical corpus via the
  D2-mandated 50K discovery sample.
- **Subsample deviation note (pre-run, 2026-07-09 12:14):** the 50K discovery sample is **not**
  a taste choice — it is **ADR-0004 D2 verbatim**. The brief permitted a subsample only if
  pre-registered; D2 pre-registers exactly this. Nearest-centroid out-of-sample assignment is
  the added detail (D2 fixes the discovery sample, not the remainder's assignment); logged here
  and, when it lands, in `DEVIATIONS.md`.
- **Repro pins (fixed before the run):**
  ```
  git commit  <paper branch, -dirty: adds clustering.py + requirements bump + tests>
  input       features.parquet  sha256 b999c8e99df4349c432c118446c8250b7ad295b58971a4bdaee23b8de13f7b2e
  input       corpus.parquet     sha256 5b7f02f07961c86b57ee6e3b6da299e09b80566ed9f7896d1306f66e203c9011  (D8 text + D9 created_at, join by skill_id)
  seed        42 (50K stratified draw; TF-IDF k-means; k-means register fallback; D1)
  env         uv run --with-requirements paper/code/ws3/requirements.txt python paper/code/ws3/clustering.py
  pins        scikit-learn / pandas / numpy / matplotlib / pyarrow recorded in the manifest
  ```

## PRE-REG — WS3 machine-cell projection probe (2026-07-09 13:17) [ADR-0009 exploratory]

- **Framing (binding):** This is an **ADR-0009 EXPLORATORY** probe — descriptive only, no
  hypothesis test, no inferential statistic, and it may **never** become a headline claim
  (ADR-0009: "no promotion to headline claims"). It answers one narrow descriptive question:
  *where in the frozen step-3 cluster geometry do the 587 KNOWN-machine-authored docs land?*
  The organic corpus has **no authorship ground truth**; this probe does NOT label any
  organic doc as machine- or human-authored. It only projects docs that are provably
  machine-generated (SkillFlow 582 across 11 LLMs + Trace2Skill 5) and reports where they fall.
- **User's motivating hypothesis pair (stated both directions, neither is being tested — this
  is exploratory description, not a test that can confirm/refute either):**
  - **(a)** the 86.3%-noise HDBSCAN blob is AI-authored homogeneous text and the tight
    islands are distinct human voices → machine docs would land mostly IN the tight islands
    would be WRONG under (a); under (a) machine docs land in the blob/noise region and the
    islands are human. i.e. machine docs cluster with the blob.
  - **(b)** the inverse — the tight islands are template/generator families (machine text is
    the *more uniform* thing) and the blob is diverse human writing → machine docs would land
    concentrated IN a small number of tight islands, not spread across the blob.
  The probe reports the observed landing distribution; the write-up says which direction the
  evidence *leans*, calibrated and exploratory, and explicitly does not claim either is true.
- **Reproduction gate (STOP if any mismatch):** recompute the step-3 pipeline deterministically
  by IMPORTING `clustering.py`'s seams (no reimplementation): organic canonical error-dropped
  population **222,256**; median-impute + z-score fit on all 222,256; PCA fit on the seed-42
  platform-stratified **50K** discovery sample → **62 components / 0.9027** cum variance;
  HDBSCAN(min_cluster_size=200) on the 50K → **10 clusters, noise 0.86308, silhouette 0.6638**
  (the persisted `hdbscan_prefallback`); k-means fallback (noise>0.50 fired) → best k=**5**,
  full assigned-set sizes **{0:108698, 1:4, 2:30342, 3:218, 4:82994}**. Any deviation → STOP,
  report, do not project. (Verified against
  `../ws1/manifests/rq1_cluster_assignments.parquet.manifest.json`.)
- **Island-assignment rule for out-of-sample machine docs (fixed BEFORE projecting):** the
  "islands" are the **10 HDBSCAN non-noise clusters** discovered on the 50K sample (the
  geometry hypothesis (a)/(b) is about, NOT the post-fallback k-means partition). For each
  island *i*, in the retained-62-component PCA space:
  - centroid *c_i* = mean PCA coords of island *i*'s discovery-sample members;
  - radius *r_i* = the **90th percentile** of island-*i* members' Euclidean distance to *c_i*
    (each island's own member-radius, so a tight island has a tight acceptance ball).
  - A machine doc is assigned to the **nearest** island *i\** (min Euclidean distance to any
    island centroid); if that distance **≤ r_{i\*}** it is "in island i\*", else it is
    labelled **"blob/noise"** (outside every island's 90th-pct ball). Ties: lowest island id.
  This rule is a **descriptive locator**, not a classifier with a learned threshold; the 90th
  pct is a fixed non-tuned choice named here before the run.
- **Projection transform (no refit):** impute + standardize the 587 machine docs with the
  **organic-fit** `SimpleImputer` + `StandardScaler` (same 130 numeric feature columns, same
  column order), then apply the **organic-fit** 62-component PCA `transform` (fit on the 50K
  organic sample). No refit of imputer/scaler/PCA/HDBSCAN/k-means on machine data.
- **Reported (all descriptive):**
  1. k-means cluster (0–4) assignment distribution of the 587 (nearest of the 5 k-means
     centroids, same `nearest_centroid_labels` seam step-3 uses for the ~172K remainder);
  2. HDBSCAN-island assignment distribution (10 islands + "blob/noise") under the rule above;
  3. both, broken down per `generator_model` — the 11 SkillFlow models, and the 5 Trace2Skill
     rows (`machine:trace2skill:*`) reported **separately** (N too small for anything but a
     per-row note, ADR-0009).
  Plus a human-readable island-inspection file (uncommitted, raw text stays out of git) so the
  user can read example organic docs per island and judge (a) vs (b) by eye.
- **Confirms / STOP:** "confirms" only that the pipeline reproduced (the reproduction gate) and
  produced finite distributions; there is no confirmatory hypothesis. STOP if the reproduction
  gate mismatches, if machine features are missing any of the 130 columns, or if the imputer/
  scaler/PCA cannot be reused as-is (column mismatch).
- **Robustness (§2):** (a) degenerate slice — the machine cell is a whole standalone table,
  no subgroup filter; per-model breakdown surfaces any single-model dominance. (b) missing data
  — 130 features, organic-fit median imputation applied to machine docs (2 machine cols at
  98.5% coverage on short docs, same known SMOG/coherence pattern); no rows dropped. (c) leakage
  — none: nothing is refit on machine data; the geometry is frozen from step 3. (d) inferential
  test — N/A, exploratory descriptive, no p-value/AUC. (e) n/subset — 587 exact (582+5), per
  model. (f) pilot vs full — full machine cell.
- **Repro pins (fixed before the run):**
  ```
  git commit  <paper branch, -dirty: adds step3_machine_projection.py + step3_machine_projection.md>
  input       features.parquet          sha256 b999c8e99df4349c432c118446c8250b7ad295b58971a4bdaee23b8de13f7b2e
  input       features_machine.parquet  sha256 <hashed at run, from features_machine manifest 7d463b35…>
  input       corpus.parquet            sha256 5b7f02f07961c86b57ee6e3b6da299e09b80566ed9f7896d1306f66e203c9011  (island-inspection text join)
  seed        42 (50K stratified draw + all step-3 stochastic pins; reused via clustering.py)
  env         uv run --with-requirements paper/code/ws3/requirements.txt python paper/code/ws3/step3_machine_projection.py
  pins        scikit-learn / pandas / numpy / scipy / pyarrow recorded in the projection manifest
  ```

## PRE-REG — WS3 island dedup-linkage probe (2026-07-09 13:31) [exploratory follow-up]

- **Framing (binding):** **EXPLORATORY / descriptive only** — no hypothesis test, no
  inferential statistic, never a headline claim. Follow-up to the step-3 island analysis.
  The user read the per-island example docs (uncommitted `step3_islands_examples.md`) and
  saw template/copy-paste families (repos like `NeuralBlitz/Agent-Gateway`,
  `Sandeeprdy1729/skill_galaxy`, `zwright8/OpenClaw-Code`). This probe **quantifies** the
  relationship between the 10 HDBSCAN islands and the corpus dedup structure.
- **User's motivating hypothesis (NOT being tested — described, not confirmed):** the
  islands are **NOT a dedup leak** (the RQ1 population is canonical-by-construction — one
  canonical per near-dup cluster) but **STRUCTURAL template families** invisible to lexical
  MinHash (near-identical scaffold, domain noun swapped → different enough tokens to escape
  the near-dup threshold), and each island member may itself be the canonical head of a
  large lexical near-dup (fork) family.
- **Islands = the 10 HDBSCAN non-noise clusters** discovered on the D2 seed-42 50K
  platform-stratified sample (same object the (a)/(b) machine-projection probe used, NOT
  the post-fallback k-means partition). Reused via
  `step3_machine_projection._reproduce_step3` (imports `clustering.py` seams; no
  reimplementation). Island membership = `labels_hdb` mapped through `sample_idx` to `pop`
  rows (the discovery-sample members of each island).
- **Reproduction gate (STOP on any mismatch):** the imported seam already asserts the
  step-3 reproduction (organic canonical pop 222,256; PCA 62 comps / 0.9027 cum var;
  HDBSCAN 10 islands, noise 0.86308, silhouette 0.6638; k-means best k=5, full sizes
  `{0:108698,1:4,2:30342,3:218,4:82994}`) against
  `rq1_cluster_assignments.parquet.manifest.json`. Any deviation → STOP.
- **Data:** `paper/data/features.parquet` (`../ws1/manifests/features.parquet.manifest.json`,
  `output_sha256` `b999c8e9…`) for the population + island geometry;
  `paper/data/dedup_map.parquet` (`skill_id → near_dup_cluster_id, cluster_size,
  is_canonical`; 672,022 rows, one canonical per cluster, `cluster_size` = # lexical
  near-dup members of that cluster, verified pre-run) joined by `skill_id`;
  `paper/data/corpus.parquet` (`skill_id → repo`) joined by `skill_id` for the vendor-repo
  concentration. All joins on `skill_id`.
- **Computed per island (all descriptive):**
  - `n_members` (discovery-sample island members);
  - `n_distinct near_dup_cluster_id` — **expected == n_members** because the population is
    canonical-only (one canonical per cluster). **Any duplicate near_dup_cluster_id within
    the analysis population is a real anomaly → flag loudly** (would mean a non-canonical or
    duplicated row leaked into RQ1).
  - member `cluster_size` distribution (median, max, **sum**) from the dedup_map join.
    **"sum" = the island's true corpus footprint** including every lexical near-dup of its
    members (each island member is a canonical head; its cluster_size counts its fork
    family).
  - per-island **platform** split (from features carry column);
  - **vendor-repo concentration** — top-3 repos by island-member count (from corpus join);
    the share of members in the top repo tells the template-farm story.
- **Confirms / STOP:** "confirms" only that the reproduction gate passed and the join
  produced finite per-island descriptives. No confirmatory hypothesis. STOP if the
  reproduction gate mismatches, if any island member is missing from dedup_map (should be
  0 — every canonical is in dedup_map), or if the anomaly count (duplicate
  near_dup_cluster_id in-population) is > 0 (report it, do not silently proceed).
- **Robustness (§2):** (a) degenerate slice — per-island reporting surfaces any single-repo
  or single-platform island. (b) missing data — cluster_size is present for all 672,022
  dedup_map rows; report join coverage. (c) leakage — none refit; geometry frozen from
  step 3; the anomaly check IS the leak guard. (d) inferential test — N/A (exploratory
  descriptive; counts + medians only). (e) n/subset — 50K discovery-sample island members,
  exact per island. (f) pilot vs full — the D2 discovery sample is the pre-registered basis
  for island membership (the islands only exist on the 50K).
- **Repro pins (fixed before the run):**
  ```
  git commit  <paper branch, -dirty: adds step3_island_dedup.py + step3_island_dedup.md>
  input       features.parquet  sha256 b999c8e99df4349c432c118446c8250b7ad295b58971a4bdaee23b8de13f7b2e
  input       dedup_map.parquet sha256 <hashed at run>
  input       corpus.parquet    sha256 5b7f02f07961c86b57ee6e3b6da299e09b80566ed9f7896d1306f66e203c9011
  seed        42 (50K stratified draw + all step-3 stochastic pins; reused via clustering.py)
  env         uv run --with-requirements paper/code/ws3/requirements.txt python paper/code/ws3/step3_island_dedup.py
  pins        scikit-learn / pandas / numpy / scipy / pyarrow recorded in the manifest
  ```

## PRE-REG — WS3 step-3 robustness cut: farm-excluded recluster (2026-07-09 14:55)

- **Goal / hypothesis (RQ1 robustness):** Step 3 found weak, non-crisp k-means structure
  (k=5, silhouette 0.1129) and 10 tight HDBSCAN islands that the island-dedup + machine-
  projection probes characterized as **template farms** (8/10 single-repo scaffold families,
  bulk within-repo forking invisible to lexical MinHash). The pre-registered reframe is:
  **"skill style is dimensional/continuous; the only categorical clusters are template
  farms."** This robustness cut **tests that reframe head-on**: remove the industrial
  template output (the island members), then re-cluster the *remaining* organic corpus with
  the identical step-3 pipeline. If no categorical structure survives, the reframe is
  supported (the farms WERE the only clusters). If clear structure emerges once the farms
  are gone, that is a **real new finding** (hidden dialect structure the farms masked) and
  is reported straight. Exploratory / descriptive structure-discovery, same as step 3:
  **Observed**-level claims only (§3), no inferential statistic, no "significant"/"validated".
- **Reproduction gate (STOP on any mismatch):** rebuild the frozen step-3 geometry by
  IMPORTING `step3_machine_projection._reproduce_step3` (which imports `clustering.py`
  seams; no reimplementation). It already asserts against
  `rq1_cluster_assignments.parquet.manifest.json`: organic canonical error-dropped
  population **222,256**; median-impute + z-score fit on all 222,256; PCA fit on the seed-42
  platform-stratified **50K** discovery sample → **62 comps / 0.9027** cum var; HDBSCAN
  (min_cluster_size=200) on the 50K → **10 islands, noise 0.86308, silhouette 0.6638**;
  k-means fallback best k=**5**, full sizes **{0:108698,1:4,2:30342,3:218,4:82994}**. Any
  deviation → STOP, do not exclude/recluster.
- **Exclusion rule (fixed BEFORE running — the projection probe's island-assignment rule,
  LEDGER 2026-07-09 13:17, applied to ALL 222,256 organic docs):** project every organic
  canonical doc into the frozen 62-component step-3 PCA space (organic-fit imputer + scaler
  + PCA, no refit). For each of the 10 HDBSCAN islands, centroid *c_i* = mean PCA coords of
  island *i*'s discovery-sample members; radius *r_i* = the **90th percentile** of island-*i*
  members' Euclidean distance to *c_i* (each island's own member radius; ties → lowest island
  id). A doc is **excluded** iff its nearest island centroid is within that island's *r_i*
  (i.e. it falls in ANY island's 90th-pct acceptance ball). This is the exact `_assign_islands`
  rule the machine-projection probe used, now run over the full organic population instead of
  the 587 machine docs. **n_excluded expected ≳ 6,846** (the 6,846 discovery-sample island
  members from the dedup probe are a subset — most will re-land in their own island's ball —
  plus out-of-sample docs from the other ~172K that fall in an island radius). The exact
  n_excluded + its per-island and per-repo breakdown are recorded (not pre-known; the
  discovery-sample 6,846 is the floor, not the answer). Note: an island member sits at its
  centroid, so by construction ≈all 6,846 discovery members land within their 90th-pct ball;
  the out-of-sample tail is what makes n_excluded exceed 6,846.
- **Re-cluster population:** the **remainder = 222,256 − n_excluded** organic canonical docs
  (every doc NOT assigned to any island). Recorded: remainder N, source split, platform split.
- **Re-cluster pipeline (SAME pre-registered step-3 D-rules, applied to the reduced
  population — nothing re-decided):** via `clustering.py` seams —
  1. **Fresh** median-impute + z-score **fit on the remainder** (the frozen step-3 transforms
     are used ONLY for the exclusion projection; the recluster gets its own standardize fit on
     the reduced population, exactly as step 3 fit on its own population). Zero-variance columns
     appearing after subsetting are dropped before PCA (recorded).
  2. **PCA ≥ 0.90 variance** (D3) fit on the discovery basis (see D2 below); record comp count.
  3. **D2 (corpus > 100K):** remainder is ≳ 215K > 100K, so D2 fires — draw a **platform-
     stratified 50K discovery sample, seed 42** (`stratified_sample_idx`), fit PCA + run HDBSCAN
     on it, assign the remainder by nearest cluster centroid. (If the remainder ever came out
     ≤ 100K, D2 would not fire and PCA+HDBSCAN would run on the full remainder — but ≳215K
     means D2 fires; recorded either way.)
  4. **HDBSCAN(min_cluster_size=200)**, min_samples default (D3, same params as step 3).
  5. **k-means fallback** if noise > 0.50 OR non-noise clusters < 3 (D3); k ∈ {4..12} by best
     silhouette, seed 42. If best silhouette < 0.10 → declare "no discrete dialects" (D3).
  6. Report the **k-means silhouette-per-k table** side by side with step 3's.
  7. Confound gates D4/D8/D9 (Cramér's V, trigger > 0.6) on the reduced assigned set, for
     parity with step 3 (not the headline here, but recorded).
- **Confirms-if / reading rules (FIXED IN ADVANCE — do not massage either way):**
  - **SUPPORTS the dimensional reading** if the recluster again yields **HDBSCAN noise > 0.50
    AND/OR k-means best silhouette < 0.25**. Reading: "no hidden categorical structure behind
    the farms — once the template output is removed, the residual organic corpus is dimensional/
    continuous, not clustered." (0.25 is the pre-registered decision threshold for "clear
    structure" here, set above step 3's bare 0.10 floor: 0.10 is the D3 *no-dialects* floor;
    a robustness cut claiming the reframe needs the residual to be *at least as* unstructured,
    so anything short of a materially better silhouette — < 0.25 — does not overturn it.)
  - **REAL NEW FINDING** if **HDBSCAN noise < 0.50 with substantive (non-degenerate,
    size ≥ 200) clusters, OR k-means best silhouette ≥ 0.25.** Then hidden dialect structure
    emerged once the farms were removed; report it straight (name the clusters by deviant
    features, run the confound gates, do NOT explain it away).
  - The silhouette-per-k table and the HDBSCAN noise/silhouette are reported regardless; the
    reading follows the rule above mechanically.
- **Bonus deliverable (descriptive, cheap):** the **top-5 PCA components of the reduced
  population** — per component the **8 highest-|loading| features + a one-phrase axis name**
  (e.g. "imperative density vs narrative"). This is the dimensional-structure table the
  reframe needs; it is descriptive (loadings, no test), reported whichever way the reading goes.
- **Confirms if (descriptive goal met):** reproduction gate passes at N=222,256; the exclusion
  rule runs and yields a finite n_excluded ≥ 6,846 (floor); the recluster pipeline runs end to
  end on the remainder and produces a comp count, an HDBSCAN outcome, a k-means fallback (or the
  D3 no-dialects declaration), the silhouette-per-k table, the three confound Cramér's V, and
  the top-5 PCA axis table. The reframe's status (SUPPORTED vs REAL-NEW-FINDING) is read off the
  fixed rule above — whatever the numbers say.
- **Would NOT confirm / STOP if:** the reproduction gate mismatches (organic pop ≠ 222,256, PCA
  ≠ 62/0.9027, islands ≠ 10, noise ≠ 0.86308, k-means sizes ≠ the frozen set) → STOP, do not
  proceed; OR n_excluded < 6,846 (would mean the discovery-sample members did not re-land in
  their own islands — a geometry/rule bug) → STOP, record, consult. High recluster noise, low
  silhouette, or a fired confound gate are the pre-registered FINDINGS, never stop conditions.
- **Robustness (§2) plan:** (a) degenerate slice — the whole point is to remove the degenerate
  template farms; watch the remainder for a residual short-doc/code-only micro-cluster and name
  it honestly (island 2 was code-only, not a scaffold family — check whether a code-only slice
  survives). (b) missing data — median impute on the remainder, no rows dropped, N stated.
  (c) confound/leakage — the exclusion uses the FROZEN step-3 geometry (no refit on the
  remainder for the *exclusion*); the recluster then gets its own standardize+PCA fit on the
  reduced population (no cross-contamination); D4/D8/D9 battery reported. (d) inferential test —
  N/A (unsupervised descriptive; silhouette/noise/Cramér's V as cohesion/association
  descriptives). (e) n/subset — 222,256 → exclude n_excluded → remainder N, all stated; D2 50K
  discovery sample stated. (f) pilot vs full — full organic canonical remainder via the
  D2-mandated 50K discovery sample.
- **BLAS/thread cap (concurrency constraint):** background stack rerun (PID 97545) +
  possible chain-extraction job — leave 4 of 10 cores free. Cap
  `OMP_NUM_THREADS=OPENBLAS_NUM_THREADS=MKL_NUM_THREADS=VECLIB_MAXIMUM_THREADS=
  NUMEXPR_NUM_THREADS=4` and KMeans/HDBSCAN parallelism accordingly (sklearn respects the
  BLAS caps; k-means n_init loop is the main multi-core user). Deterministic; the caps do not
  change results, only core usage.
- **Repro pins (fixed before the run):**
  ```
  git commit  <paper branch, -dirty: adds step3_robustness.py + step3_robustness.md + test>
  input       features.parquet  sha256 b999c8e99df4349c432c118446c8250b7ad295b58971a4bdaee23b8de13f7b2e
  input       corpus.parquet    sha256 5b7f02f07961c86b57ee6e3b6da299e09b80566ed9f7896d1306f66e203c9011  (D8 text + D9 created_at + repo breakdown, join by skill_id)
  seed        42 (step-3 50K draw for the frozen geometry + the recluster's own 50K draw, TF-IDF k-means, k-means fallback; all reused via clustering.py)
  env         OMP/BLAS threads capped to 4; uv run --with-requirements paper/code/ws3/requirements.txt python paper/code/ws3/step3_robustness.py
  pins        scikit-learn / pandas / numpy / scipy / matplotlib / pyarrow recorded in the manifest
  ```

## PRE-REG — WS3 step-3 SURGICAL farm-only recluster (2026-07-09 15:20)

- **Goal / hypothesis (RQ1 robustness, variant of the 14:55 cut):** the committed farm-excluded
  recluster (LEDGER RESULT 2026-07-09 15:14) excluded ALL 10 HDBSCAN islands = **59,124** docs,
  but **35,413** of those (59.9%) fell into **island 8's** ball. Island 8 is the ONE island the
  dedup + machine-projection probes characterized as the **diffuse, genuinely-diverse,
  hand-written-looking** island (90th-pct radius **6.37** vs ~0.5–2.45 for the tight farms
  0–7). So the committed cut is honestly "farms **plus** a large diverse tail", which leaves a
  reviewer hole: *"you removed the most diverse slice, of course the rest looks homogeneous."*
  This variant closes it by excluding **only the 9 tight single-repo/template-scaffold islands
  (0–7 and 9)** — the ones `step3_island_dedup.md` shows are 100%/99% single-repo template
  farms — and **explicitly RETAINING island 8** (it is diverse hand-written-looking content, not
  a template farm; its radius 6.37 is the tell). If the residual (farms removed, but the diverse
  island 8 KEPT) still shows no categorical structure, the dimensional reading is supported
  **without** the "you deleted diversity" objection. Exploratory / descriptive, same as step 3:
  **Observed**-level only, no inferential statistic, no "significant"/"validated".
- **Reproduction gate (STOP on any mismatch):** identical to the 14:55 cut — rebuild the frozen
  step-3 geometry via `step3_machine_projection._reproduce_step3` (imports `clustering.py`
  seams), asserted against `rq1_cluster_assignments.parquet.manifest.json`: organic pop
  **222,256**; PCA **62 comps / 0.9027**; HDBSCAN **10 islands, noise 0.86308, silhouette
  0.6638**; k-means best k=**5**, full sizes **{0:108698,1:4,2:30342,3:218,4:82994}**. Any
  deviation → STOP.
- **Exclusion rule (fixed BEFORE running — SAME island-radius assignment as the 14:55 cut, only
  the excluded island SET changes):** project every organic canonical doc into the frozen
  62-comp PCA space; `_assign_islands` gives each doc its nearest island id (or -1 if outside
  every 90th-pct ball). A doc is **excluded** iff its assigned island ∈ **{0,1,2,3,4,5,6,7,9}**
  (the 9 tight islands) — **island 8 members are RETAINED in the recluster population.** Every
  other choice (radius rule, ties → lowest id, frozen transforms for the projection) is
  identical to the 14:55 cut; the ONLY change is dropping island 8 from the exclusion set.
  **n_excluded expected ≈ 59,124 − 35,413 ≈ 23,711** (the exact number is derived + recorded,
  not pre-known). Note island 2 (code-only snippets, `vamseeachanta/workspace-hub` 64%) is a
  borderline case but is a tight island (radius 1.94) the dedup probe flags as a template family,
  so it stays in the exclusion set; only island 8 is retained.
- **Re-cluster population:** the **remainder = 222,256 − n_excluded** organic canonical docs
  (every doc NOT assigned to a tight island; island-8-ball docs are IN the remainder). Recorded:
  remainder N, source split, platform split.
- **Re-cluster pipeline (IDENTICAL to the 14:55 cut — the same `recluster_population` seam, no
  new machinery):** fresh median-impute + z-score fit on the remainder; PCA ≥ 0.90 (D3); D2 50K
  stratified discovery sample seed 42 if remainder > 100K; HDBSCAN(min_cluster_size=200);
  k-means fallback if noise > 0.50 OR non-noise clusters < 3, k ∈ {4..12} by best silhouette,
  seed 42; D3 "no discrete dialects" if best silhouette < 0.10; k-means silhouette-per-k table
  side by side with step 3 AND the all-islands cut; D4/D8/D9 confound gates on the reduced set.
- **Reading rule (FIXED IN ADVANCE — identical thresholds to the 14:55 cut, read off
  mechanically):** recluster HDBSCAN noise > **0.50** AND/OR k-means best silhouette < **0.25**
  → **SUPPORTS the dimensional reframe** (no hidden categorical structure behind the farms, and
  now with the diverse island 8 KEPT so "you removed diversity" is off the table). HDBSCAN noise
  < 0.50 with substantive (size ≥ 200) clusters OR k-means silhouette ≥ 0.25 → **REAL NEW
  FINDING**, reported straight (name clusters, run confound gates, do not explain away).
- **Confirms if (descriptive goal met):** reproduction gate passes at N=222,256; the surgical
  exclusion yields a finite n_excluded ≈ 23.7k (island 8 retained); the recluster runs end to
  end on the remainder and produces a comp count, HDBSCAN outcome, k-means fallback (or D3
  no-dialects), the silhouette-per-k table, three confound Cramér's V, and the top-5 PCA axis
  table. The reframe's status (SUPPORTED vs REAL-NEW-FINDING) is read off the fixed rule.
- **Would NOT confirm / STOP if:** reproduction gate mismatches (pop ≠ 222,256, PCA ≠ 62/0.9027,
  islands ≠ 10, k-means sizes ≠ frozen set) → STOP; OR n_excluded ≥ the 14:55 cut's 59,124
  (would mean island 8 was NOT actually retained — a rule bug) → STOP, record, consult. High
  recluster noise, low silhouette, or a fired confound gate are the pre-registered FINDINGS,
  never stop conditions.
- **Robustness (§2) plan:** (a) degenerate slice — the whole point is a SURGICAL farm-only cut
  that keeps the diverse island 8; watch the remainder for the same n=4 structural-outlier
  micro-cluster and name it honestly. (b) missing data — median impute on the remainder, no rows
  dropped, N stated. (c) confound/leakage — exclusion uses the FROZEN step-3 geometry (no refit
  for the cut); the recluster gets its own standardize+PCA fit on the reduced population; D4/D8/D9
  reported. (d) inferential test — N/A (unsupervised descriptive). (e) n/subset — 222,256 →
  exclude n_excluded (island 8 retained) → remainder N, all stated; D2 50K discovery sample
  stated. (f) pilot vs full — full organic remainder via the D2 50K discovery sample.
- **BLAS/thread cap (concurrency constraint):** background stack rerun (PID 97545) + an RQ2
  analysis agent (step4/adoption) — leave 4 of 10 cores free. Cap
  `OMP/OPENBLAS/MKL/VECLIB/NUMEXPR_NUM_THREADS=4`. Deterministic; caps do not change results.
- **Repro pins (fixed before the run):**
  ```
  git commit  <paper branch, -dirty: extends step3_robustness.py (--tight-only) + step3_robustness.md + test>
  input       features.parquet  sha256 b999c8e99df4349c432c118446c8250b7ad295b58971a4bdaee23b8de13f7b2e
  input       corpus.parquet    sha256 5b7f02f07961c86b57ee6e3b6da299e09b80566ed9f7896d1306f66e203c9011  (D8 text + D9 created_at + repo breakdown, join by skill_id)
  seed        42 (frozen step-3 50K draw + recluster's own 50K draw + TF-IDF k-means + k-means fallback; reused via clustering.py)
  env         OMP/BLAS threads capped to 4; uv run --with-requirements paper/code/ws3/requirements.txt python paper/code/ws3/step3_robustness.py --tight-only
  ```

## RESULTS

### Step-3 SURGICAL farm-only recluster — island 8 retained (2026-07-09 15:49)

- **Reproduction gate PASSED:** frozen step-3 geometry rebuilt via
  `step3_machine_projection._reproduce_step3`, asserted against
  `rq1_cluster_assignments.parquet.manifest.json`: organic pop **222,256**; PCA **62 comps /
  0.9027**; HDBSCAN **10 islands, noise 0.86308, silhouette 0.6638**; k-means best k=**5**,
  full sizes **{0:108698,1:4,2:30342,3:218,4:82994}** — all matched.
- **Surgical exclusion (Observed):** the SAME island-radius assignment rule as the 15:14
  all-islands cut (`_assign_islands`, nearest island centroid within its 90th-pct member
  radius, frozen 62-comp PCA space), but excluding **only the 9 tight template-farm islands
  {0,1,2,3,4,5,6,7,9}** and **RETAINING island 8** (the diffuse, genuinely-diverse,
  hand-written-looking island, radius 6.37). **n_excluded = 23,711** of 222,256 (10.7%) —
  exactly the all-islands 59,124 **minus** island 8's **35,413**-doc ball, which is now kept in
  the remainder (per-island excluded: 0:3,100 · 1:3,374 · 2:943 · 3:2,455 · 4:891 · 5:7,349 ·
  6:1,283 · 7:2,609 · **8:0 (RETAINED)** · 9:1,707). Top excluded repos are the template-farm
  repos only: `zwright8/OpenClaw-Code` 8,239 · `Sandeeprdy1729/skill_galaxy` 7,536 ·
  `NeuralBlitz/Agent-Gateway` 3,100 · `membranedev/application-skills` 2,591 · no diverse
  island-8 repos appear (they are retained). **This closes the all-islands cut's honest hole:**
  the diverse slice is IN the recluster population, so "you removed the most diverse docs" is
  off the table.
- **Recluster (Observed, remainder N = 198,545; source skill_diffs 198,505 + graph_of_skills
  40; platforms claude 132,466 / opencode 29,764 / openclaw 25,997 / hermes 10,278):** fresh
  standardize + PCA on the reduced population retained **64 comps for 0.9017** cum var
  (0 zero-variance drops); D2 fired (> 100K) → seed-42 50K stratified discovery sample;
  **HDBSCAN(min_cluster_size=200) gave 2 clusters, noise 0.99014** (> the all-islands cut's
  0.90364 and step 3's 0.863 — the residual is the *least* HDBSCAN-clusterable of the three),
  so the D3 fallback fired; **k-means best k=4 at silhouette 0.09355 — below the D3 0.10 floor,
  so the pipeline emitted the "NO DISCRETE DIALECTS" declaration.** Assigned sizes
  {0:95,748, 1:27,946, **2:213**, 3:74,638} — cluster **2 (n=213)** is the same degenerate
  structural-outlier micro-cluster (deviant `struct_line_count`/`struct_heading_count`) step 3
  and the all-islands cut produced, so effectively **3 substantive groupings**. Confound gates
  on the reduced set: **D4 platform V 0.044, D8 domain 0.217, D9 era 0.086 — none fired** (> 0.6).
- **Three-way k-means silhouette per k (step 3 / all-islands / surgical):** k=4 0.1117 / 0.093 /
  **0.0935**; k=5 0.1129 / 0.0697 / 0.0672; every k in the surgical cut is at or below the
  all-islands cut and well below step 3 — the farm-only remainder (island 8 kept) is **no more
  clusterable** than the aggressive cut, and less than the full corpus.
- **Reading (FIXED-IN-ADVANCE rule, read off mechanically — same thresholds as the 15:14 cut):**
  recluster HDBSCAN noise > 0.50 AND/OR k-means silhouette < 0.25 → SUPPORTS the dimensional
  reframe. Here noise **0.99014 > 0.50** AND silhouette **0.09355 < 0.25** (and < the 0.10 D3
  floor). **VERDICT: SUPPORTS-DIMENSIONAL** — same verdict as the all-islands cut, now WITHOUT
  the diversity-removal caveat.
- **Claim (Observed level only, exploratory):** removing **only** the template-farm structure —
  and **keeping** the diverse island 8 — leaves an organic residual that is *even less clustered*
  than the full corpus: HDBSCAN noise rose 0.863→0.990, k-means silhouette fell 0.1129→0.0935
  (below the D3 no-dialects floor), no confound gate fired. This **supports the pre-registered
  reframe** — *skill style is dimensional/continuous; the only categorical clusters in the corpus
  were the template farms* — and does so **more cleanly than the all-islands cut**, because the
  most-diverse slice (island 8, 35,413 docs) is retained in the reclustered population, so the
  null result cannot be attributed to having deleted the diversity. Not "distinct dialects"; no
  "validated"/"significant" language; no inferential test (unsupervised descriptive). Top-5 PCA
  axes of the surgical remainder are continuous register dimensions — **PC1 POS/dependency mix;
  PC2 readability vs syntactic complexity; PC3 length/size vs POS/dependency mix; PC4
  structure/formatting vs frontmatter completeness; PC5 length/size** (8 loadings each in
  `step3_robustness.md`).
- **Robustness (§2):** (a) degenerate slice — the surgical cut is the farm-only removal; the
  n=213 structural-outlier micro-cluster is named honestly (same as step 3 / all-islands), and
  the diverse island 8 is now KEPT (the whole point). (b) missing data — median impute on the
  remainder, 0 rows dropped, N=198,545 stated. (c) confound/leakage — exclusion uses the FROZEN
  step-3 transforms (no refit for the cut); the recluster gets its OWN standardize+PCA fit on the
  reduced population; D4/D8/D9 battery reported, none fired. (d) inferential test — N/A
  (unsupervised descriptive; noise/silhouette/Cramér's V as cohesion/association descriptives).
  (e) n/subset — 222,256 → exclude 23,711 (island 8 retained) → remainder 198,545, all stated;
  D2 50K discovery sample stated. (f) pilot vs full — full organic remainder via the D2 50K
  discovery sample. Determinism: the surgical exclusion set + island-8-retention logic
  unit-tested (2 new tests), `recluster_population` seam unchanged (its tests still pass); all
  14 ws3 robustness/projection/clustering tests pass. All numbers above cited from
  `step3_robustness.md` / the surgical manifest, not retyped from the run log.
- **Artifact:** table `paper/data/step3_robustness_surgical_assignments.parquet` (gitignored);
  summary `paper/code/ws3/step3_robustness.md` (SURGICAL section appended, three-way side by
  side); figure `paper/figures/ws3_step3_robustness_surgical_pca_scatter.png`; manifest
  `../ws1/manifests/step3_robustness_surgical_assignments.parquet.manifest.json`
  (`output_sha256` `3f190afb…`, `variant` surgical_tight_only, `excluded_island_set`
  [0-7,9], `retained_diverse_island` 8, `n_island8_ball_retained_in_remainder` 35413,
  `n_excluded` 23711, `n_remainder` 198545, `reading` SUPPORTS-DIMENSIONAL,
  `recluster_no_discrete_dialects` true, `recluster_silhouette` 0.09355,
  `recluster_hdbscan_prefallback.noise_fraction` 0.99014).
- **Repro:**
  ```
  git commit  <paper branch, -dirty: extends step3_robustness.py (--tight-only) + step3_robustness.md + test>
  input       features.parquet  sha256 b999c8e99df4349c432c118446c8250b7ad295b58971a4bdaee23b8de13f7b2e
  input       corpus.parquet    sha256 5b7f02f07961c86b57ee6e3b6da299e09b80566ed9f7896d1306f66e203c9011
  output      step3_robustness_surgical_assignments.parquet  sha256 3f190afbebdd491c03d2961f0e8eae20279f7278910154691a05880a8b970072
  seed        42 (frozen step-3 50K draw + recluster's own 50K draw + TF-IDF k-means + k-means fallback; reused via clustering.py)
  pins        scikit-learn 1.9.0 · pandas 3.0.3 · numpy 2.4.6 · scipy 1.17.1 · matplotlib 3.11.0 · pyarrow 24.0.0
  env         OMP/BLAS threads capped to 4
  uv run --with-requirements paper/code/ws3/requirements.txt python paper/code/ws3/step3_robustness.py --tight-only
  ```

### Step-3 robustness cut — farm-excluded recluster (2026-07-09 15:14)

- **Reproduction gate PASSED:** the frozen step-3 geometry was rebuilt by importing
  `step3_machine_projection._reproduce_step3` and asserted against
  `rq1_cluster_assignments.parquet.manifest.json`: organic pop **222,256**; PCA **62 comps /
  0.9027**; HDBSCAN **10 islands, noise 0.86308, silhouette 0.6638**; k-means best k=**5**,
  full sizes **{0:108698,1:4,2:30342,3:218,4:82994}** — all matched.
- **Exclusion (Observed):** the machine-projection probe's island-assignment rule (nearest
  island centroid within that island's 90th-pct member radius, frozen 62-comp PCA space)
  applied to all 222,256 organic docs excluded **n_excluded = 59,124** (26.6% of the corpus;
  well above the 6,846 discovery-member floor). Per-island counts (island: n): 0:3,100 ·
  1:3,374 · 2:943 · 3:2,455 · 4:891 · 5:7,349 · 6:1,283 · 7:2,609 · **8:35,413** · 9:1,707.
  Top excluded repos: `zwright8/OpenClaw-Code` 8,239 · `Sandeeprdy1729/skill_galaxy` 7,805 ·
  `NeuralBlitz/Agent-Gateway` 3,100 · `membranedev/application-skills` 2,595 ·
  `LJT-520/openClaw-backup` 1,711 (the template-farm repos the dedup probe named, plus their
  out-of-sample scaffold siblings).
- **CAVEAT (honest, load-bearing for interpretation):** **59.9% of the excluded set (35,413
  docs) fell into island 8's ball** — and island 8 is the ONE island the prior probes
  characterized as the *diffuse, genuinely-diverse, hand-written-looking* island (90th-pct
  radius **6.37**, ~3–12x the tight farm islands 0–7 whose radii are 0.53–2.45). So the
  literal pre-registered rule did **not** excise only template farms: the 8 tight farm islands
  contributed ~22,300 exclusions (clean template removal), but island 8's huge acceptance ball
  swept in ~35K *diverse* organic docs that are not template output. The exclusion is therefore
  a **conservative-to-aggressive** cut (removes the farms AND a large diverse slice), not a
  surgical farm-only removal. This makes the recluster's null result **stronger, not weaker**:
  even after removing the tight farms plus 35K of the most-diverse docs, no hidden categorical
  structure appears in what remains.
- **Recluster (Observed, remainder N = 163,132; source skill_diffs 163,102 + graph_of_skills
  30; platforms claude 109,775 / opencode 24,129 / openclaw 20,597 / hermes 8,601):** fresh
  standardize + PCA on the reduced population retained **64 comps for 0.9039** cum var; D2
  fired (remainder > 100K) → seed-42 50K stratified discovery sample; **HDBSCAN
  (min_cluster_size=200) gave 2 clusters, noise 0.90364** (> step 3's 0.863), so the D3
  fallback fired; **k-means best k=4 at silhouette 0.09298** — **below the D3 0.10 floor, so
  the pipeline emitted the D3 "NO DISCRETE DIALECTS" declaration** (step 3's 0.1129 was just
  above it). Assigned cluster sizes {0:28,029, 1:4, 2:63,719, 3:71,380} — cluster **1 (n=4)**
  is the same degenerate `struct_line_count`/`struct_heading_count` structural-outlier
  micro-cluster step 3 produced (its deviant medians are +162/+160 SD), so effectively **3
  substantive groupings**, less separated than step 3's. Confound gates on the reduced set:
  **D4 platform V 0.039, D8 domain 0.200, D9 era 0.079 — none fired** (> 0.6).
- **k-means silhouette per k (vs step 3):** k=4 **0.093** (5 0.070, 6 0.070, 7 0.068, 8 0.058,
  9 0.066, 10 0.057, 11 0.053, 12 0.067). Every k is *lower* than step 3's (step 3 k=4 0.1117,
  k=5 0.1129) — the farm-excluded remainder is **less** clusterable than the full organic
  corpus at every k.
- **Reading (FIXED-IN-ADVANCE rule, read off mechanically — not massaged):** recluster HDBSCAN
  noise > 0.50 AND/OR k-means silhouette < 0.25 → SUPPORTS the dimensional reframe. Here noise
  **0.904 > 0.50** AND silhouette **0.093 < 0.25** (and < the 0.10 D3 floor). **VERDICT:
  SUPPORTS-DIMENSIONAL.**
- **Claim (Observed level only, exploratory):** removing the categorical template-farm structure
  (and, per the caveat, a large diverse slice with it) leaves an organic residual that is **even
  less clustered** than the full corpus — HDBSCAN noise rose (0.863→0.904), k-means silhouette
  fell below the D3 no-dialects floor (0.1129→0.093), and no confound gate fired. This **supports
  the pre-registered reframe**: *skill style is dimensional/continuous; the only categorical
  clusters in the corpus were the template farms* — no hidden dialect structure emerges once the
  farms are excluded. Not "distinct dialects"; no "validated"/"significant" language; no
  inferential test (unsupervised descriptive). The top-5 PCA axes of the reduced population are
  continuous register dimensions — **PC1 POS/dependency mix; PC2 readability vs syntactic
  complexity; PC3–PC5 structure/formatting vs length/size** (8 loadings each in
  `step3_robustness.md`), the dimensional-structure table the reframe rests on.
- **Robustness (§2):** (a) degenerate slice — the n=4 structural-outlier micro-cluster is named
  honestly (same as step 3); the diverse-island-8 over-inclusion is surfaced as the load-bearing
  caveat above, not hidden. (b) missing data — median impute on the remainder, no rows dropped,
  N=163,132 stated. (c) confound/leakage — exclusion uses the FROZEN step-3 transforms (no refit
  for the cut); the recluster gets its OWN standardize+PCA fit on the reduced population (no
  cross-contamination); D4/D8/D9 battery reported, none fired. (d) inferential test — N/A
  (unsupervised descriptive; noise/silhouette/Cramér's V as cohesion/association descriptives).
  (e) n/subset — 222,256 → exclude 59,124 → remainder 163,132, all stated; D2 50K discovery
  sample stated. (f) pilot vs full — full organic remainder via the D2 50K discovery sample.
  Determinism: `recluster_population` seam unit-tested (2 tests), all ws3 tests pass; the
  reproduction gate asserts the frozen geometry. All numbers above are cited from
  `step3_robustness.md` / the manifest, not retyped from the run log.
- **Artifact:** table `paper/data/step3_robustness_assignments.parquet` (gitignored);
  summary `paper/code/ws3/step3_robustness.md`; figure
  `paper/figures/ws3_step3_robustness_pca_scatter.png`; manifest
  `../ws1/manifests/step3_robustness_assignments.parquet.manifest.json`
  (`output_sha256` `000c0b91…`, `n_excluded` 59124, `n_remainder` 163132, `reading`
  SUPPORTS-DIMENSIONAL, `recluster_no_discrete_dialects` true, `recluster_silhouette`
  0.09298, `recluster_hdbscan_prefallback.noise_fraction` 0.90364).
- **Repro:**
  ```
  git commit  <paper branch, -dirty: adds step3_robustness.py + step3_robustness.md + test>
  input       features.parquet  sha256 b999c8e99df4349c432c118446c8250b7ad295b58971a4bdaee23b8de13f7b2e
  input       corpus.parquet    sha256 5b7f02f07961c86b57ee6e3b6da299e09b80566ed9f7896d1306f66e203c9011
  output      step3_robustness_assignments.parquet  sha256 000c0b918ea4afc057f87dc019a8dfed396e1d28857aa1841bfa84f69e053e00
  seed        42 (frozen step-3 50K draw + recluster's own 50K draw + TF-IDF k-means + k-means fallback; reused via clustering.py)
  pins        scikit-learn 1.9.0 · pandas 3.0.3 · numpy 2.4.6 · scipy 1.17.1 · matplotlib 3.11.0 · pyarrow 24.0.0
  env         OMP/BLAS threads capped to 4
  uv run --with-requirements paper/code/ws3/requirements.txt python paper/code/ws3/step3_robustness.py
  ```

### Island dedup-linkage probe (2026-07-09 13:39) [EXPLORATORY follow-up]

- **Result (descriptive):** For the 10 step-3 HDBSCAN islands (discovered on the D2 seed-42
  50K sample; geometry reproduced via `step3_machine_projection._reproduce_step3`, asserted
  against `rq1_cluster_assignments.parquet.manifest.json` before computing):
  - **Anomaly check: 0 duplicate `near_dup_cluster_id`** among all 6,846 island members —
    `n_distinct near_dup_cluster_id == n_members` for every island. The RQ1 population is
    **canonical-by-construction** (one canonical head per near-dup cluster); the islands are
    **not a dedup leak**.
  - **Repo concentration (template-farm signature): 8 of 10 islands are single-repo at
    100% / 99%** of members — island 0 `NeuralBlitz/Agent-Gateway` (100%), 1/3/9
    `Sandeeprdy1729/skill_galaxy` (100%), 4/5 `zwright8/OpenClaw-Code` (100%/99.9%), 7
    `membranedev/application-skills` (99.1%). Only islands **2** (`vamseeachanta/workspace-hub`
    64%) and **8** (`BetterPromptme/skills` 24%, 4 platforms) are repo/platform-diverse —
    island 8 is the same diffuse, genuinely-diverse island the machine-projection probe
    flagged (radius 6.37, ~7x the tight islands).
  - **Corpus footprint (sum of member `cluster_size`, incl. lexical near-dups):** the 6,846
    canonical heads stand in for **12,595 total docs**. Per island (n_members → footprint):
    0: 726→730 · 1: 824→830 · 2: 238→269 · 3: 583→583 · 4: 244→244 · 5: 1,864→2,049 ·
    **6: 348→3,739** (median cluster_size **19**, the only heavily-lexically-forked island) ·
    7: 671→680 · **8: 913→3,034** (max cluster_size **298**, one canonical head with a
    298-member fork family) · 9: 435→437.
- **Claim (Observed level only, exploratory):** the islands are **structural template
  families, not a dedup artifact** — near-identical scaffolds with domain nouns swapped
  differ in enough tokens to escape the lexical MinHash near-dup threshold, so each surfaces
  as a tight linguistic-feature island despite being one repo's forked scaffold. Two
  orthogonal propagation modes coexist: **within-repo structural forking** (what builds the
  8 single-repo template islands, invisible to lexical dedup) and **lexical near-duplication**
  (what dedup catches — visible only in islands 6 and 8's cluster_size sums). No hypothesis
  test; never a headline claim (ADR-0009-style exploratory).
- **Robustness (§2):** (a) degenerate slice — per-island reporting surfaces the single-repo
  concentration directly (that IS the finding). (b) missing data — 0 island members missing
  from dedup_map; features vs dedup_map `near_dup_cluster_id` agree on 100% of rows (asserted).
  (c) leakage — the anomaly check (0 duplicate in-population ndc) is the dedup-leak guard;
  nothing refit, geometry frozen from step 3. (d) inferential test — N/A (descriptive counts
  + medians). (e) n/subset — 6,846 discovery-sample island members, exact per island.
  (f) pilot vs full — the D2 50K discovery sample is the pre-registered basis on which the
  islands exist.
- **Artifact:** table `paper/data/step3_island_dedup.parquet`; summary
  `paper/code/ws3/step3_island_dedup.md`; manifest
  `../ws1/manifests/step3_island_dedup.parquet.manifest.json` (`output_sha256` `122b1470…`,
  `anomaly_duplicate_ndc_in_population` 0, `corpus_footprint_total` 12595). All numbers above
  are cited from that parquet/manifest, not retyped from the run log.
- **Repro:**
  ```
  git commit  <paper branch, -dirty: adds step3_island_dedup.py + step3_island_dedup.md>
  input       features.parquet  sha256 b999c8e99df4349c432c118446c8250b7ad295b58971a4bdaee23b8de13f7b2e
  input       dedup_map.parquet sha256 0c8f7320382f5f6c27212a95dc5231cb109fedf28b799c9116a38bbf72104699
  input       corpus.parquet    sha256 5b7f02f07961c86b57ee6e3b6da299e09b80566ed9f7896d1306f66e203c9011
  output      step3_island_dedup.parquet  sha256 122b1470b76ea03e182b48216f9df3b7745dda0482d6a17db88f98a2fcbbde2b
  seed        42 (50K stratified draw + all step-3 stochastic pins; reused via clustering.py)
  pins        scikit-learn 1.9.0 · pandas 3.0.3 · numpy 2.4.6 · scipy 1.17.1 · pyarrow 24.0.0
  uv run --with-requirements paper/code/ws3/requirements.txt python paper/code/ws3/step3_island_dedup.py
  ```

### Machine-cell projection probe (2026-07-09 13:37) [ADR-0009 EXPLORATORY]

- **Framing (binding):** ADR-0009 **exploratory** — descriptive locator, **no hypothesis
  test**, no inferential statistic, and per ADR-0009 this **never becomes a headline claim**.
  It reports only where 587 KNOWN-machine-authored docs (SkillFlow 582 across 11 LLMs +
  Trace2Skill 5) fall in the frozen step-3 geometry. It does **not** attribute authorship to
  any organic doc (no ground truth exists).
- **Reproduction gate PASSED:** the step-3 pipeline was recomputed by importing
  `clustering.py`'s seams (no reimplementation) and asserted against the persisted manifest:
  organic pop **222,256**; PCA **62 comps / 0.9027**; HDBSCAN **10 islands, noise 0.86308,
  silhouette 0.6638091411557737**; k-means fallback best k=**5**, full sizes
  **{0:108698, 1:4, 2:30342, 3:218, 4:82994}** — all matched (asserts held). Same imputer +
  scaler (fit on all 222,256) + PCA (fit on the 50K sample) reused to transform the machine
  docs with **no refit**.
- **Result (Observed, descriptive):** the 587 machine docs land —
  - **k-means (0–4):** {0: 400 (68.1%), 2: 3 (0.5%), 4: 184 (31.3%)} — i.e. split between the
    two large substantive step-3 clusters (0, 4), essentially none in the degenerate
    structural micro-clusters 1/3.
  - **HDBSCAN island (nearest island ≤ its 90th-pct member radius, else blob/noise):**
    **blob/noise 469 (79.9%), island 8 118 (20.1%), every other tight island 0.** SkillFlow
    only (582): blob/noise 464, island 8 118. Per-model: the in-island landings are almost
    entirely **Claude-family** models (e.g. `claude-code-minimax2dot7-skill` 41/93 in island 8,
    `claude-code-sonnet4dot6-skill` 25/51); the **Qwen** models land ~entirely blob/noise
    (`qwen-coder-480b` 0/104 in-island, `qwen-coder-next` 2/109). The 5 **Trace2Skill** rows
    (incl. the human Anthropic baseline) all fall in blob/noise (nearest island 8 or 7).
  - **Island character (by-eye, from the uncommitted inspection file):** the 10 tight HDBSCAN
    islands are **bulk-generated template/generator families** from *organic-corpus* repos
    (islands 0/1/3/9 = skill_galaxy scaffolds; 4/5 = OpenClaw-Code scaffolds; 6 = Rube-MCP;
    7 = Membrane-CLI; 2 = code-only snippets) — one scaffold, many number/noun-swapped
    variants. The exception is **island 8** (loosest, 90th-pct radius 6.37 vs. ~2 for the tight
    islands), which holds genuinely diverse hand-written-looking skills.
- **Claim (Observed / exploratory only — NOT a headline, ADR-0009):** the known-machine docs
  do **not** occupy the corpus's tightest, most template-like structure; they miss every crisp
  template island and pool in the **diffuse island 8 + blob**. This **leans toward a
  *refinement of* the user's hypothesis (b), not (a):** the tight islands are template farms
  (uniform generation) — but they are *organic-corpus* template farms, a distinct phenomenon
  from our machine cell — while the SkillFlow/Trace2Skill machine text is diverse enough to
  read as ordinary blob prose. **Neither (a) nor (b) as originally stated is confirmed:** (a)
  is unsupported (tight islands are demonstrably templates, not human voices); (b) is only
  half-supported (template-farm generation is uniform, our known-machine cell is not). No
  claim of authorship-by-geometry is made.
- **Robustness (§2):** (a) degenerate slice — whole machine table, per-model breakdown surfaces
  the Claude-vs-Qwen split. (b) missing data — organic-fit median imputation applied to machine
  docs, no rows dropped, N=587 (582+5) stated. (c) leakage — none, nothing refit on machine
  data; geometry frozen from step 3, reproduction asserted. (d) inferential test — N/A
  (exploratory descriptive; distributions only, no p-value/AUC). (e) n/subset — 587 exact,
  per model. (f) pilot vs full — full machine cell. Determinism: `_assign_islands` seam
  unit-tested (2 tests), 20/20 ws3 tests pass; reproduction asserts are the pipeline gate.
- **Artifact:** `paper/code/ws1/manifests/step3_machine_projection.parquet.manifest.json`
  (`output_sha256` `1e4029c5…`); summary `paper/code/ws3/step3_machine_projection.md`;
  uncommitted island-inspection file `paper/data/step3_islands_examples.md` (raw organic text —
  never committed). All numbers above are cited from the manifest/summary, not the run log.
- **Repro:**
  ```
  git commit  <paper branch, -dirty: adds step3_machine_projection.py + .md + test>
  input       features.parquet          sha256 b999c8e99df4349c432c118446c8250b7ad295b58971a4bdaee23b8de13f7b2e
  input       features_machine.parquet  sha256 7d463b35…  (from the machine-cell manifest)
  input       corpus.parquet            sha256 5b7f02f07961c86b57ee6e3b6da299e09b80566ed9f7896d1306f66e203c9011
  output      step3_machine_projection.parquet  sha256 1e4029c5…
  seed        42 (step-3 50K draw + all stochastic pins, reused via clustering.py)
  pins        scikit-learn 1.9.0 · pandas 3.0.3 · numpy 2.4.6 · scipy 1.17.1 · pyarrow 24.0.0
  uv run --with-requirements paper/code/ws3/requirements.txt python paper/code/ws3/step3_machine_projection.py
  ```

### Step 3 — RQ1 clustering / instruction dialects (2026-07-09 13:00)

- **Result (Observed):** On the **222,256**-row organic canonical error-dropped population,
  PCA retained **62 components** for **0.9027** cumulative variance; the **D2** 50K
  platform-stratified discovery sample fed **HDBSCAN(min_cluster_size=200)**, which found
  **10 clusters** with **noise fraction 0.863** and discovery-sample silhouette **0.6638**
  (now persisted in the manifest's `hdbscan_prefallback` block and `step3_clusters.md`,
  alongside the post-fallback numbers, so the pre-registered trigger evidence survives the
  run). Noise **0.863 > 0.50** fired the **pre-registered D3 fallback** to k-means (k ∈
  {4..12}); best k = **5** at silhouette **0.1129** — **below the D3 "no discrete dialects"
  floor is 0.10, so 0.1129 clears it, but only barely: WEAK cluster structure**, not crisp
  dialects. Full assigned-set cluster sizes: **{0: 108,698, 1: 4, 2: 30,342, 3: 218,
  4: 82,994}** — clusters **1 (n=4)** and **3 (n=218)** are degenerate outlier clusters (their
  deviant-feature signatures are dominated by extreme structural counts —
  `struct_line_count`/`struct_heading_count` for cluster 1, `struct_name_format_valid`/
  `fm_desc_present` for cluster 3), so there are **effectively 3 substantive groupings**
  (0, 2, 4). Confound gates: **D4 platform Cramér's V 0.056, D8 domain 0.254, D9 era
  0.066 — none fired** (trigger > 0.6).
- **Claim (Observed level only):** the organic corpus shows **weak, non-crisp dialect
  structure** — a k=5 partition with silhouette just above the pre-registered floor, two of
  the five clusters degenerate on structural metadata rather than dialect, and none of the
  three confound gates firing. This is **not** "distinct dialects" — no claim of clean,
  well-separated instruction dialects is made. See `step3_clusters.md`'s top-5 PCA axes for
  the continuous register dimensions (readability/structure/lexical) that underlie the weak
  partition.
- **Robustness (§2):** confound gates D4/D8/D9 computed on the full assigned set (none
  fired); determinism verified — 8/8 `tests/test_clustering.py` pass, seed 42 throughout
  (50K draw, TF-IDF k-means, k-means fallback), rerun reproduced a byte-identical output
  parquet (sha match, see Repro). All numbers above are read from the regenerated manifest
  and `step3_clusters.md`, not retyped from the run log.
- **Artifact:** `paper/code/ws1/manifests/rq1_cluster_assignments.parquet.manifest.json`
  (`output_sha256` `edebcc74…`); summary `paper/code/ws3/step3_clusters.md`; figures
  `paper/figures/ws3_step3_pca_scatter.png`, `paper/figures/ws3_step3_cluster_platform_heatmap.png`.
- **Repro:**
  ```
  git commit  cb7fa649 (paper branch, -dirty: clustering.py defect fixes)
  input       features.parquet  sha256 b999c8e99df4349c432c118446c8250b7ad295b58971a4bdaee23b8de13f7b2e
  input       corpus.parquet    sha256 5b7f02f07961c86b57ee6e3b6da299e09b80566ed9f7896d1306f66e203c9011
  output      rq1_cluster_assignments.parquet  sha256 edebcc744b38d8d4b68cc46b8b4ce2f43913d17cc2dc7459d235b9a3c11257a7
  seed        42 (50K stratified draw; TF-IDF k-means; k-means register fallback; D1)
  pins        scikit-learn 1.9.0 · pandas 3.0.3 · matplotlib 3.11.0 · numpy 2.4.6 · pyarrow 24.0.0 · scipy 1.17.1
  uv run --with-requirements paper/code/ws3/requirements.txt python paper/code/ws3/clustering.py
  ```

### Machine-cell feature extraction (2026-07-09 12:14) [ADR-0009 exploratory]

- **Result:** `features_machine.parquet` — **587 / 587 rows** (matches the machine-cell
  manifest's `n_rows`), **138 columns** (5 carry columns `skill_id, source,
  generator_model, domain, task_family` + 132 `analyze_text` feature keys +
  `analyze_error`). `analyze_error` non-null on **0 / 587 rows (0.0000%)** — well under the
  < 1% gate. Two feature columns (`read_smog`, `coh_second_order_coherence`) sit at 98.5%
  coverage (9/587 short docs undefined, same expected pattern noted in step 2's PRE-REG —
  SMOG needs ≥30 sentences); every other feature column is ≥99% covered.
- **Claim:** Descriptive prep only — no hypothesis, no claim ladder rung. This just confirms
  the extraction ran clean over the standalone machine-cell table.
- **Robustness (§2):** (a) contamination — N/A, whole-table run, no subgroup filter.
  (b) missing data — 2 columns below 99% on short docs, consistent with step 1/2's known
  null pattern (undefined SMOG/coherence on short docs), not a new failure mode.
  (c) confound/leakage — N/A, no model fit here. (d) inferential test — N/A (descriptive).
  (e) n/subset — exact, 587/587 stated. (f) pilot vs full — full table (587 is the whole
  machine cell).
- **Artifact:** `paper/data/features_machine.parquet` (gitignored);
  `../ws1/manifests/features_machine.parquet.manifest.json` (`output_sha256` `7d463b35…`).
- **Repro:**
  ```
  git commit  1afa1d2 (paper branch, -dirty: adds extract_features_machine.py)
  input       src_machine_cell.parquet  sha256 28f022cc7a3406d5413d3df97c8628f732948dd0cd3481f2ec906ef8fcaa4afc
  spacy 3.8.14 · en_core_web_sm 3.8.0 · pyarrow 24.0.0 · textdescriptives 2.8.2
  deterministic pipeline, no seed
  uv run --with-requirements paper/code/ws1/requirements.txt \
      python paper/code/ws3/extract_features_machine.py
  ```

### Step 2 — descriptives + organic-vs-slop separability (2026-07-09 11:29)

- **Result (Observed):** On the canonical analysis population — **227,403** docs after
  dropping **4** rows with a non-null `analyze_error` (RQ2 install-labeled extras excluded
  per PRE-REG), split **slop_stub = 5,147** (positive) vs **organic = 222,256**
  (`skill_diffs 222,216` after error-drop + `graph_of_skills 40`) — a `class_weight=
  "balanced"`, standardized, median-imputed logistic (5-fold stratified CV, seed 42) gives:
  - **FULL (130 numeric features): ROC-AUC 1.0000 ± 0.0000** (exact mean 0.999993, sd 1.4e-5).
  - **LENGTH-ONLY baseline (5 length counts): ROC-AUC 0.9734 ± 0.0008.**
  - **FULL − LENGTH (125 features): ROC-AUC 1.0000 ± 0.0000** (exact 0.999992, sd 1.4e-5).
  - Top-10 most-separating features (|coef| on standardized inputs, FULL fit on all rows):
    `struct_max_heading_depth` (+3.08 → slop), `struct_prose_ratio` (+1.98 → slop),
    `posdep_dep_ROOT` (−1.38 → organic), `desc_proportion_unique_tokens` (+1.20 → slop),
    `struct_bullet_list_ratio` (−1.12 → organic), `coh_lemma_overlap_adj` (−0.99 → organic),
    `struct_list_item_ratio` (−0.91 → organic), `struct_inline_code_char_ratio` (−0.88 →
    organic), `struct_code_char_ratio` (−0.86 → organic), `read_long_sentence_ratio`
    (−0.78 → organic).
  - Descriptives (median [Q1,Q3]) make the gap concrete: slop `desc_tokens` 22 [20,26] vs
    organic 252 [120,476]; slop FKG 7.6 vs 11.8; slop `dict_hedge_per_1k` / `dict_conditional_
    per_1k` / `dict_second_person_per_1k` / `coh_lemma_overlap_adj` all median 0.
- **Claim (Observed, calibrated):** The linguistic-feature set separates the two **corpora**
  essentially perfectly — but this is **corpus-provenance separation, NOT evidence of a
  subtle organic-vs-slop linguistic dialect**. slop_stub is a corpus of ~22-token
  marketplace blurbs; organic docs are full multi-hundred-token procedures. The classes
  differ on nearly every structural feature at once, so the AUC is over-determined. This
  **validates only that the feature extractor discriminates a trivially different corpus**;
  it does not license any claim about Timbro capturing a nuanced dialect. No
  "significant"/"validated" language — no inferential test was run (mean±sd across folds only).
- **Length-confound guard (PRE-REG §2 / D5):** the pre-registered length hypothesis is
  **refuted, but not exonerating**. Length-only already reaches 0.9734, yet FULL − LENGTH
  stays 1.0000 (gap FULL − length-only = +0.0266) — so length is *sufficient-ish but not
  necessary*: separation persists after removing all 5 length counts because the corpora also
  differ on structure/readability/cohesion. Honest reading: **the separation is not merely
  length-driven — it is provenance-driven across many correlated structural features.**
- **Robustness (§2):** (a) **Contamination/degenerate slice** — YES, and this IS the finding:
  slop is a degenerate ~22-token slice; the perfect AUC is a corpus artifact, flagged in the
  claim above. (b) **Missing data** — 34/130 features have nulls on short docs (SMOG/coherence
  undefined); handled by per-fold median imputation, **no rows dropped**, N=227,403 stated.
  (c) **Leakage/confound** — **D5 ablation FIRED** (FULL CV AUC > 0.99): dropping the top
  feature `struct_max_heading_depth` leaves AUC **0.99997 ± 3e-5** — separation is
  over-determined, consistent with provenance leakage, not a single-feature template tell.
  (d) **Inferential test** — N/A (descriptive/validation step); reported as mean±sd, no
  significance claimed. (e) **n/subset** — exact, stated. (f) **Pilot vs full** — full corpus.
- **Artifact:** table `paper/code/ws3/step2_descriptives.md`; full per-feature per-group
  median/IQR CSVs `step2_source_summary.csv` / `step2_platform_summary.csv`; figure
  `paper/figures/ws3_step2_headline_distributions.png`; manifest
  `../ws1/manifests/step2_descriptives.md.manifest.json` (`output_sha256` `4cfc2f60…`).
  All numbers above are cited from that manifest/table, not retyped from the run log.
- **Repro:**
  ```
  git commit  b1c2ce8 (paper branch, -dirty: adds descriptives.py + requirements.txt + tests)
  input       features.parquet  sha256 b999c8e99df4349c432c118446c8250b7ad295b58971a4bdaee23b8de13f7b2e
  seed        42 (StratifiedKFold shuffle; D1)
  pins        scikit-learn 1.9.0 · pandas 3.0.3 · matplotlib 3.11.0 · numpy 2.4.6 · pyarrow 24.0.0
  uv run --with-requirements paper/code/ws3/requirements.txt python paper/code/ws3/descriptives.py
  ```

### Step 1 — `extract_features.py` production run (2026-07-09)

- **Result:** `features.parquet` — 231,426 rows (227,407 canonical + 4,019 labeled-only,
  9,686 labeled total; arithmetic reconciles: 227,407 + 4,019 = 231,426), 139 columns
  (5 carry columns + 132 `analyze_text` feature keys + `analyze_error`).
  `analyze_error` non-null on **4 / 231,426 rows (0.0017%)** — well under the < 1% §2 gate.
  All 4 are `TypeError: Object of type date is not JSON serializable` (a
  `textdescriptives`/serialization edge case on 4 specific docs, not a scope or corpus
  problem): `skill_id` = `sd:0da1512055387f63`, `sd:55c24539c6a3200e`, `sd:5797f69a8872d2b5`,
  `sd:b1136098fb8e9148`.
  `lex_mtld` non-null on 99.998% of rows (> 99% spot-check gate).
- **Incident + fix:** the initial run crashed at the final `pa.concat_tables(tables)` step —
  parts where every doc succeeded had `analyze_error` inferred as pyarrow **null** type
  (all-`None` column), while parts with ≥1 failure had it inferred as **string** type;
  pyarrow refused to concat mismatched types for the same column name. Fixed by (a)
  explicitly casting `analyze_error` to `pa.string()` when each per-part table is built
  (`_rows_to_table`), so future parts are typed consistently, and (b) concatenating with
  `pa.concat_tables(tables, promote_options="permissive")` to unify null→string across the
  116 **existing** on-disk parts (reused as-is, not regenerated).
- **Artifact:** `paper/code/ws1/manifests/features.parquet.manifest.json`
  (`output_sha256` `b999c8e9…`).
- **Repro:**
  ```
  git commit  c1da527 (paper branch, -dirty: concat/dtype fix on extract_features.py)
  corpus sha  5b7f02f07961c86b57ee6e3b6da299e09b80566ed9f7896d1306f66e203c9011
  spacy 3.8.14 · en_core_web_sm 3.8.0 · pyarrow 24.0.0 · textdescriptives 2.8.2
  uv run --with-requirements paper/code/ws1/requirements.txt \
      python paper/code/ws3/extract_features.py
  ```

_Earlier steps (descriptives → holdout) follow once run._

## PRE-REG — WS3 step 5 prep: RQ4 chain feature extraction (2026-07-09 14:54)

- **Goal:** produce one deterministic feature vector per RQ4-eligible version-row
  (temporal evolution analysis, ADR-0005) so step 5 can run mixed-effects models over
  linguistic-feature trajectories across a skill's revisions. **Not a hypothesis test** —
  the "results" are counts, coverage, and failure rates (a corpus-construction step, like
  step 1/machine-cell extraction). No claim ladder rung at stake; the §2 gate is
  drift + failure-rate + column-coverage.
- **Data:** `paper/data/skill_diffs_chains.parquet`
  (`../ws1/manifests/skill_diffs_chains.parquet.manifest.json`, `output_sha256`
  `9d92df6337ab05215837c206bb14c929558356c3e2bf284c56f10b0b8aa0d5c8`, **289,145
  version-rows across 218,626 chains**, schema: `skill_id, version_index, commit_date,
  after_sha, text, intent_class, intent_confidence, quality_score, n_versions,
  skill_cluster_id, is_canonical, repo`).
- **Scope rule (pre-registered, derived from the chains table itself, not invented):**
  the table already carries a per-chain `n_versions` column. Verified empirically
  pre-run: `n_versions` is **constant within every `skill_id`** and equals that chain's
  row count (0 mismatches across all 218,626 chains) — so it is exactly the ADR-0005
  chain-length count, safe to filter on directly (no need to recompute a groupby-count).
  RQ4-eligible = **`n_versions >= 3`** (ADR-0005 §8b: "chains require ≥3 versions").
  Derived, verified pre-run: **eligible chains = 14,388** (matches the WS1 LEDGER's
  14,388 RQ4-eligible figure exactly) → **eligible version-rows = 67,164**. This is
  the pre-registered, asserted N for this run — the script asserts both numbers and
  aborts on drift.
- **Rationale for scoping (not extracting all 289,145):** extracting features over
  every version-row would waste ~4x compute (289,145 / 67,164 ≈ 4.3x) on chains RQ4
  can never use (chain length < 3 is excluded from RQ4 by ADR-0005's frozen eligibility
  rule). Scope is derived directly from that frozen rule, not a new invented filter.
- **Feature source:** `timbro.analyze.analyze_text` (repo `src/timbro/analyze.py`) —
  same deterministic pipeline as step 1, reused via import (no logic duplication) from
  `extract_features.py`'s `_analyze_one` / `_worker_init` / `_feature_keys` seams.
- **Output:** `paper/data/features_chains.parquet` — carry columns `skill_id,
  version_index, commit_date, after_sha, n_versions, skill_cluster_id, is_canonical,
  repo` (the chain/version identifiers present in `skill_diffs_chains.parquet`'s own
  schema) + all 132 `analyze_text` feature keys (flat) + `analyze_error` (`pa.string()`,
  null normally). Resumable parts under `paper/data/features_chains_parts/`. Manifest
  via WS1 `write_manifest`.
- **Confirms if:** eligible-chain count == **14,388** and eligible version-row count ==
  **67,164** (asserted against the derivation above before the run; the script aborts on
  mismatch); analyze failures **< 1%** of 67,164; all feature columns present on **> 99%**
  of rows.
- **Would NOT confirm / STOP if:** eligible-chain count ≠ 14,388 or eligible-row count ≠
  67,164 (chains-table drift under us — the script asserts and aborts; record + consult
  user); analyze failures **≥ 1%** — stop, record the failing docs' error messages,
  consult user.
- **Pool size:** `max(1, cpu_count()-5)` — two other heavy jobs run concurrently
  (the background stack rerun, PID 97545, plus a second concurrent job), so 5 cores are
  left free on this 10-core machine (pool size 5).
- **Repro pins (fixed before the run):**
  ```
  git commit  cb7fa64 (paper branch, -dirty: adds extract_features_chains.py + test)
  input       skill_diffs_chains.parquet  sha256 9d92df6337ab05215837c206bb14c929558356c3e2bf284c56f10b0b8aa0d5c8
  spacy 3.8.14 · en_core_web_sm 3.8.0 · pyarrow 24.0.0 · textdescriptives 2.8.2
  deterministic pipeline, no seed
  uv run --with-requirements paper/code/ws1/requirements.txt \
      python paper/code/ws3/extract_features_chains.py
  ```

## PRE-REG — WS3 step 4 RQ2 adoption (2026-07-09 15:23)

- **Goal / hypothesis (RQ2, CONFIRMATORY):** do the deterministic linguistic features of a
  skill predict its adoption, controlling for length, age, and ecosystem? This is the paper's
  **confirmatory** analysis. Outcome, covariates, feature family, and correction rule are
  **pre-frozen in ADR-0004 (§8, D1–D8), ADR-0007 (§8 amendment 2, D9), and ADR-0010** — this
  block is faithful execution, not design. Earns up to a **"Supported"/"Refuted"** claim on
  the 5 confirmatory features (§3), guarded by BH (D6). A **null is publishable and reported
  straight** with the minimum detectable effect (D6).
- **BINDING rules carried in (not re-decided here):**
  - **Primary outcome (ADR-0007):** `log1p(installs_wk_mean)` — mean of the 8-week weekly
    install series. **Robustness outcomes:** (a) `log1p(total installs + 1)` (the corpus
    `installs` total); (b) GitHub `stars` on single-skill repos only.
  - **Confirmatory feature family (ADR-0004, FROZEN — 5 features, NOT open):**
    `dict_imperative_ratio`, `dict_hedge_per_1k`, `read_flesch_kincaid_grade`,
    `syn_mean_tree_depth`, `coh_lemma_overlap_adj`. Everything else is exploratory and
    labeled exploratory. Because ADR-0004 fixes the confirmatory family, the task's
    "pre-register your own feature choice" branch does **not** apply.
  - **Mandatory covariates:** `log(desc_tokens)` (length, ADR-0004) AND `log1p(skill_age_days)`
    (age, ADR-0007) — always covariates, never hypotheses, in **every** RQ2 regression.
  - **D6 correction:** Benjamini–Hochberg at **q=0.10 over the 5 confirmatory features only**
    (the primary-outcome regression's 5 feature coefficients). No promoting exploratory hits
    to headline claims. If nothing survives → report the null + MDE.
  - **ADR-0010 population + SEs:** RQ2 population = the **entry-level install-labeled
    representatives** (one representative row per distinct loose `(owner,repo,name)` entry,
    already materialized as the 9,686 `installs`-labeled rows in `features.parquet`);
    **cluster-robust SEs on `near_dup_cluster_id`**; **canonical-only sensitivity rerun** (the
    5,667-entry `is_canonical=="true"` subset).
- **Estimator (pre-registered choice, per the task's "pre-register which"):** **statsmodels
  OLS with cluster-robust (CR1) SEs clustered on `near_dup_cluster_id`** — this is the literal
  ADR-0010 §4 requirement ("RQ2 models cluster standard errors on `near_dup_cluster_id`").
  NOT mixedlm repo-random-effects: ADR-0010 §4 names `near_dup_cluster_id` as the
  non-independence unit, not repo; a repo RE would cluster on a different unit than the ADR
  fixes. (New dep: `statsmodels>=0.14`, added to ws3 requirements — regression is this issue's
  explicit scope; guardrail "no new dependency unless the issue says so" is satisfied by the
  task brief naming statsmodels.) Platform enters as **fixed effects** (dummies). **Domain FE:
  corpus rows carry NO domain labels** (ADR-0006 dropped ClawHub categories; D8's TF-IDF proxy
  is an unlabeled RQ1 clustering tool, not a frozen RQ2 taxonomy) — so domain FE is **omitted
  and stated as a limitation per D8**, not invented.
- **Data / population:** `paper/data/features.parquet` (manifest
  `../ws1/manifests/features.parquet.manifest.json`, `output_sha256` `b999c8e9…`) — the
  **9,686** `installs` non-null/non-empty entry-level representative rows (verified pre-run:
  9,686 rows, all `source==skill_diffs`, 5,667 canonical + 4,019 non-canonical, 9,009 distinct
  `near_dup_cluster_id`). Feature vectors + `platform` + `near_dup_cluster_id` + `is_canonical`
  from features.parquet; **outcome, age, stars, repo joined from `corpus.parquet`** by
  `skill_id` (features.parquet's `frontmatter_json` is JSON-normalized to `{}`, so the raw
  `name:` needed for the weekly join lives only in corpus.parquet).
- **Outcome join (loose key, merge.py convention):** weekly outcome from
  `paper/data/skillssh_weekly.parquet` (`installs_wk_mean`), joined on the loose key
  `re.sub(r"[^a-z0-9]","",s.lower())` applied to `(owner, reponame)` split from corpus `repo`
  and the frontmatter `name:` (skills.sh `(owner, repo, skill)` on the weekly side; per-key max
  on the weekly side for the ~8 duplicate keys, mirroring merge.py's `_skillssh_lookup`).
  **Verified pre-run: 9,686/9,686 (100%) labeled representatives match a weekly row** — join
  coverage reported in the summary. **8-week single-anchor window limitation (ADR-0007) and the
  580 all-zero-series caveat stated wherever the outcome is reported.**
- **Age:** `skill_age_days` = (crawl anchor **2026-07-08** − `created_at` first-commit date from
  corpus.parquet). Verified pre-run: `created_at` 100% non-null on the labeled set, all ages
  positive (min 68.5d, median 140.2d, max 276.4d). Covariate enters as `log1p(skill_age_days)`.
- **Length:** `log(desc_tokens)` (`desc_tokens` present in features.parquet, the document-length
  feature).
- **Missing feature values:** the 34/130 features with nulls on short docs — for the 5
  confirmatory features specifically, **median-impute** (fit on the RQ2 population) and record
  the imputed count per feature; no rows dropped (N stated). Confirmatory features are all
  numeric analyze outputs; report their coverage on the 9,686.
- **Analysis (all pre-registered):**
  1. **Spearman screen (EXPLORATORY, D6-labeled exploratory):** Spearman ρ of each of the 130
     numeric features vs `log1p(installs_wk_mean)`, BH q=0.10 across the 130 — reported as an
     **exploratory screen only** (D6 forbids promoting these to headline claims). The 5
     confirmatory features' screen values are highlighted but the confirmatory inference is the
     regression + D6-over-5, not this screen.
  2. **Primary confirmatory regression:** OLS
     `log1p(installs_wk_mean) ~ z(dict_imperative_ratio) + z(dict_hedge_per_1k) +
     z(read_flesch_kincaid_grade) + z(syn_mean_tree_depth) + z(coh_lemma_overlap_adj) +
     log(desc_tokens) + log1p(skill_age_days) + C(platform)`, features **z-scored** (fit on the
     RQ2 population) so coefficients are per-SD effect sizes; **CR1 cluster-robust SEs on
     `near_dup_cluster_id`**. Report each confirmatory coefficient with a **95% CI** and the
     **BH-adjusted p over the 5** (D6). Never bare p-values.
  3. **Robustness reruns (all pre-registered, reported side by side with the primary):**
     - (a) outcome = `log1p(total installs + 1)` (corpus `installs`), same RHS;
     - (b) **canonical-only population** (the 5,667 `is_canonical=="true"` entries, ADR-0010
       sensitivity) — same primary spec; a coefficient-sign flip vs the full set would indicate
       cluster/fork structure drives the result;
     - (c) outcome = `stars` on **single-skill repos only** (repos contributing exactly one
       labeled entry; verified feasible — 375 such entries, `stars` present with 330 nulls on
       the full set). `log1p(stars)`, same RHS minus the repo-level collinear terms as needed;
       if N or `stars` coverage makes it uninformative, record why rather than over-claim.
  4. **Selection-bias check (pre-registered WS1 risk item):** compare the **labeled** organic
     canonical docs (the 5,667 canonical labeled) vs the **unlabeled** organic canonical docs
     (canonical, not install-labeled) on **length (`desc_tokens`), platform mix, and the 5
     confirmatory headline features** — medians/IQR + platform shares, to characterize how the
     skills.sh-indexed subset differs from the corpus. Descriptive (Observed), no inferential
     claim.
- **Seed:** 42 only where stochastic (none of OLS/Spearman is stochastic; seed recorded for
  provenance parity — the analysis is deterministic given the frozen inputs).
- **Confirms if (execution goal met):** join coverage computed (expected 9,686/9,686); the
  primary OLS fits and yields 5 finite confirmatory coefficients with CR1 SEs and CIs; BH-over-5
  applied; the three robustness reruns + the selection-bias table produced. RQ2's **answer is
  whatever the regression reports** — supported features (BH-surviving, CI excluding 0), a null
  (nothing survives → report MDE), or mixed, are all valid confirmatory outcomes reported
  straight.
- **Would NOT confirm / STOP if:** labeled population ≠ 9,686 OR its source/canonical split ≠
  {skill_diffs 9,686; canonical 5,667 + non-canonical 4,019} (D7-style drift — the script
  asserts and aborts; record + consult user); OR weekly-join coverage falls materially below
  ~100% (the merge.py key should reproduce the 9,686 matches — a large miss means a key/schema
  change under us → STOP, record). A null result, a fired-nothing BH, or a robustness flip are
  **findings, not stop conditions**.
- **Robustness (§2) plan:** (a) degenerate slice — the 580 all-zero weekly series are kept
  (log1p handles 0) and their count is reported; canonical-only rerun surfaces fork-structure
  sensitivity. (b) missing data — median-impute the 5 confirmatory features, count reported, no
  rows dropped. (c) confound/leakage — length + age covariates (both mandatory arrows,
  ADR-0007), platform FE, cluster-robust SEs on near_dup_cluster_id; domain FE omitted +
  flagged (D8). (d) inferential test — OLS with CR1 cluster-robust SEs, effect sizes with 95%
  CIs, BH q=0.10 over the 5 (D6). (e) n/subset — full 9,686 primary; 5,667 canonical-only;
  375 single-skill-repo stars; all Ns stated. (f) pilot vs full — full RQ2 labeled population.
- **Selection-bias / coverage caveat (RISK item, PLAN §6):** install-labeled skills are a
  curated skills.sh slice (~1.74% of the corpus); coverage is RQ2's denominator and the
  labeled-vs-unlabeled check is the pre-registered guard — both reported straight.
- **Repro pins (fixed before the run):**
  ```
  git commit  58e27fa (paper branch, -dirty: adds adoption.py + statsmodels req + test)
  input       features.parquet         sha256 b999c8e99df4349c432c118446c8250b7ad295b58971a4bdaee23b8de13f7b2e
  input       skillssh_weekly.parquet  sha256 <hashed at run>
  input       corpus.parquet           sha256 5b7f02f07961c86b57ee6e3b6da299e09b80566ed9f7896d1306f66e203c9011  (outcome-join name, age, stars, repo; join by skill_id)
  crawl anchor 2026-07-08 (age from created_at first-commit date)
  seed        42 (provenance parity; OLS/Spearman deterministic)
  env         OMP/BLAS threads capped to 4; uv run --with-requirements paper/code/ws3/requirements.txt python paper/code/ws3/adoption.py
  pins        statsmodels / scikit-learn / pandas / numpy / scipy / matplotlib / pyarrow recorded in the manifest
  ```

### Step 4 — RQ2 adoption (CONFIRMATORY) (2026-07-09 15:32)

- **Population + join coverage (asserted, D7 gate passed):** RQ2 population =
  **9,686** entry-level install-labeled representatives (ADR-0010; 5,667 canonical +
  4,019 non-canonical, all `skill_diffs`; **9,009** distinct `near_dup_cluster_id`).
  Weekly outcome (`installs_wk_mean`) joined via the loose merge.py key (owner/repo from
  corpus `repo` + frontmatter `name:`, each `re.sub(r"[^a-z0-9]","",lower)`): **9,686/9,686
  (100.0%)** matched. Age from first-commit `created_at` → crawl anchor **2026-07-08**:
  9,686/9,686 non-null, median 140.2 d. **8-week single-anchor window** (ADR-0007); **58 of
  the 9,686 labeled skills carry an all-zero weekly series** (kept; log1p handles 0 — the
  corpus-wide 580 all-zero figure is the full skills.sh table, not this labeled subset).
- **Primary confirmatory regression (Supported/Refuted per feature) —
  `log1p(installs_wk_mean)`:** OLS, z-scored 5 confirmatory features (per-SD effects) +
  `log(desc_tokens)` + `log1p(skill_age_days)` + platform FE; **CR1 cluster-robust SEs on
  `near_dup_cluster_id`** (9,009 clusters); BH q=0.10 over the 5 (D6). N=9,686, R²=0.0390.
  **1 of 5 survives BH: `dict_imperative_ratio` +0.1068 [+0.0691, +0.1445], p_BH 3e-8** —
  more-imperative skills have higher weekly install velocity, ~0.11 log-units per feature-SD.
  The other four do NOT survive: `dict_hedge_per_1k` +0.0224 [-0.0055, +0.0502] (p_BH 0.288),
  `read_flesch_kincaid_grade` -0.0170 [-0.0683, +0.0344] (0.709), `syn_mean_tree_depth`
  +0.0089 [-0.0454, +0.0632] (0.748), `coh_lemma_overlap_adj` -0.0100 [-0.0442, +0.0242]
  (0.709). Covariates behave as expected: `log(desc_tokens)` +0.1090 [+0.0706, +0.1475];
  `log1p(age)` **-0.7269 [-0.8355, -0.6183]** (older skills past peak velocity — the age
  arrow ADR-0007 controls for is real and large).
- **Robustness (all pre-registered, side by side):**
  - (a) `log1p(total installs+1)`: `dict_imperative_ratio` **survives** (+0.0626 [+0.0216,
    +0.1036], p_BH 0.014); `coh_lemma_overlap_adj` also survives (+0.0316 [+0.0015, +0.0617],
    p_BH 0.099, borderline); the rest do not.
  - (b) canonical-only (5,667 entries, ADR-0010 sensitivity): `dict_imperative_ratio`
    **survives, same sign/magnitude** (+0.1114 [+0.0736, +0.1493], p_BH 4e-8) — **no flip**,
    so the imperative effect is not a cluster/fork artifact.
  - (c) stars on single-skill repos (**359** labeled entries with `stars`; the primary
    outcome is installs, not stars — this is a weak secondary): `dict_imperative_ratio` NOT
    significant (+0.2358 [-0.0358, +0.5074], p_BH 0.222); `dict_hedge_per_1k` the only BH
    survivor here (+0.4463 [+0.1362, +0.7564], p_BH 0.024). Underpowered (N=359, wide CIs);
    reported, not over-claimed.
- **Durability read:** `dict_imperative_ratio` is the one confirmatory feature that survives
  BH on the primary outcome AND both install-based robustness cuts (total installs;
  canonical-only) with a stable positive sign — the durable RQ2 signal. Stars (single-skill,
  N=359) is too thin to corroborate it.
- **Exploratory Spearman screen (130 features, BH q=0.10 — EXPLORATORY, NOT headline per
  D6):** 105/130 survive BH (large-N corpus, tiny ρ). Top by |ρ| are POS/dependency-mix and
  coherence features (`posdep_dep_det` +0.143, `posdep_pos_DET` +0.142,
  `coh_first_order_coherence` -0.135, …), all ρ ≈ 0.11–0.14 — **larger raw correlations than
  any confirmatory feature, and D6 explicitly forbids promoting them to headline claims.**
  The 5 confirmatory features' own screen ρ: imperative +0.080, hedge +0.075, FKG -0.071,
  tree-depth -0.032, cohesion -0.012. Confirmatory inference is the regression + BH-over-5,
  not this screen.
- **Selection-bias check (labeled 5,667 canonical vs unlabeled 216,589 organic canonical —
  the pre-registered WS1 risk item):** the skills.sh-indexed labeled slice is **longer**
  (`desc_tokens` median 370 vs 250), **more imperative** (0.25 vs 0.20), **far more hedged**
  (`dict_hedge_per_1k` 2.93 vs 0), and **overwhelmingly Claude-platform** (93.5% vs 68.1%
  claude_skill; hermes/openclaw/opencode all under-represented in the labeled set). So RQ2's
  population is a curated, Claude-skewed, somewhat-longer slice — the coverage/selection
  caveat (PLAN §6, ~1.74% of the corpus) is concrete, not hypothetical.
- **Claim (calibrated, confirmatory):** Under the frozen ADR-0004/0007/0010 rules, **of the
  5 pre-registered confirmatory linguistic features, only `dict_imperative_ratio` predicts
  the primary adoption outcome** (weekly install velocity) after length + age + platform,
  cluster-robust on near-dup clusters — a small but durable positive effect (~+0.11 log-units
  per SD, surviving BH on the primary and both install robustness cuts). The other four
  (hedging, readability, syntactic depth, cohesion) are **null at q=0.10** with the CIs above.
  Model R² 0.039: linguistic style adds a small, mostly-imperative-driven increment over the
  dominant length and (negative) age covariates. **Limitations (stated straight):** domain FE
  omitted (no corpus domain labels — ADR-0006 dropped ClawHub categories, D8); 8-week
  single-anchor outcome window (ADR-0007); labeled set is a curated, Claude-skewed ~1.74%
  skills.sh slice (selection-bias table above). No "significant" language beyond the BH gate;
  effect sizes are reported with 95% CIs throughout.
- **Robustness (§2):** (a) degenerate slice — 58 all-zero weekly series kept (log1p),
  canonical-only rerun surfaces fork-structure sensitivity (no flip). (b) missing data — the
  5 confirmatory features median-imputed on the population, 0 rows dropped, N stated.
  (c) confound/leakage — length + age covariates (both ADR-0007 arrows), platform FE,
  CR1 cluster-robust SEs on near_dup_cluster_id; domain FE omitted + flagged (D8).
  (d) inferential test — OLS with cluster-robust SEs, effect sizes with 95% CIs, BH q=0.10
  over the 5 (D6). (e) n/subset — 9,686 primary; 5,667 canonical-only; 359 single-skill-repo
  stars; all stated. (f) pilot vs full — full RQ2 labeled population. Determinism: rerun
  reproduced the same BH survivor and output sha (`d98abe6f…`); the D7 population assert is
  the drift gate; 7/7 `tests/test_adoption.py` pass (join-key seam + BH-over-5); ruff clean.
  All numbers above are cited from `step4_adoption.md` / the manifest, not retyped from the
  run log.
- **Artifact:** table `paper/data/rq2_adoption_rows.parquet` (gitignored); summary
  `paper/code/ws3/step4_adoption.md`; figures
  `paper/figures/ws3_step4_confirmatory_forest.png`,
  `paper/figures/ws3_step4_outcome_hist.png`; manifest
  `../ws1/manifests/rq2_adoption_rows.parquet.manifest.json` (`output_sha256` `d98abe6f…`,
  `join_coverage_matched` 9686, `n_all_zero_weekly_series` 58, `primary_bh_survivors`
  `["dict_imperative_ratio"]`, `primary_r2` 0.0390).
- **Repro:**
  ```
  git commit  9db59b6 (paper branch, -dirty: adds adoption.py + step4_adoption.md + test + statsmodels req)
  input       features.parquet         sha256 b999c8e99df4349c432c118446c8250b7ad295b58971a4bdaee23b8de13f7b2e
  input       skillssh_weekly.parquet  sha256 d64d7395e2df8070...
  input       corpus.parquet           sha256 5b7f02f07961c86b57ee6e3b6da299e09b80566ed9f7896d1306f66e203c9011
  output      rq2_adoption_rows.parquet  sha256 d98abe6f1c3cc53c44a7c446e931b8f6521a22479c6cff6385b845c290b67e96
  crawl anchor 2026-07-08 (age from created_at first-commit date)
  seed        42 (provenance parity; OLS/Spearman deterministic)
  pins        statsmodels 0.14.6 · scikit-learn 1.9.0 · pandas 3.0.3 · numpy 2.4.6 · scipy 1.17.1 · matplotlib 3.11.0 · pyarrow 24.0.0
  env         OMP/BLAS threads capped to 4
  uv run --with-requirements paper/code/ws3/requirements.txt python paper/code/ws3/adoption.py
  ```
