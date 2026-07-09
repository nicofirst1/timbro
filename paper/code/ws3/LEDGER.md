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
- [ ] RQ2 adoption (step 4) — regressions on `log1p(installs_wk_mean)`; BH per D6.
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

## RESULTS

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
