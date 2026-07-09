# WS3 ledger — corpus analysis

Canonical results ledger for WS3 (experiment-discipline §4). Numbers are cited from
generated artifacts (`FINDINGS.md`, figures, manifests), never retyped. Newest on top.
Analysis rules are pre-registered in ADR-0004/0005 (D1–D9) and bind over this file.

## PENDING

(nothing pending — next up: RQ1 clustering, step 3)

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
- [ ] RQ1 clustering (step 3) — PCA → HDBSCAN; confound gates D4/D8/D9.
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

## RESULTS

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
