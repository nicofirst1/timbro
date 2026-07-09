# WS3 ledger — corpus analysis

Canonical results ledger for WS3 (experiment-discipline §4). Numbers are cited from
generated artifacts (`FINDINGS.md`, figures, manifests), never retyped. Newest on top.
Analysis rules are pre-registered in ADR-0004/0005 (D1–D9) and bind over this file.

## PENDING

- [x] `extract_features.py` — **step 1 (production run), supersedes the `featurize.py`
      scaffold below.** Deterministic linguistic feature vectors over the WS1 corpus
      (canonical UNION install-labeled scope). **Done** 2026-07-09. Parallel (multiprocessing
      Pool, per-worker spaCy load), resumable via `paper/data/features_parts/part-*.parquet`,
      per-doc `analyze_error` (never crashes the run on one doc), writes `features.parquet` +
      manifest via ws1 `write_manifest`. Result lands in RESULTS +
      `features.parquet.manifest.json`. See the WS3.1 PRE-REG block below.

## STATUS

- [x→superseded] `featurize.py` — step 1 scaffold: corpus.parquet canonical docs →
      features.parquet. **Scaffolded + unit-tested** (TDD, ponytail) 2026-07-08. Pure seam
      `featurize_rows` filters `is_canonical`, carries metadata forward. **Superseded for
      the real run by `extract_features.py`** (2026-07-09): the scaffold was canonical-only,
      in-memory (`to_pylist()`), non-parallel, non-resumable, and deferred the manifest —
      `extract_features.py` adds all of those + the ADR-0010 install-labeled union scope
      needed for RQ2. Scaffold + its `test_featurize.py` kept as-is (pure-seam reference).
- [ ] descriptives (step 2) — per-source/platform distributions; organic-vs-slop AUC.
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

## RESULTS

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
