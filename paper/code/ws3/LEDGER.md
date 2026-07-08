# WS3 ledger — corpus analysis

Canonical results ledger for WS3 (experiment-discipline §4). Numbers are cited from
generated artifacts (`FINDINGS.md`, figures, manifests), never retyped. Newest on top.
Analysis rules are pre-registered in ADR-0004/0005 (D1–D9) and bind over this file.

## STATUS

- [~] `featurize.py` — step 1: corpus.parquet canonical docs → features.parquet.
      **Scaffolded + unit-tested** (TDD, ponytail) 2026-07-08. Pure seam `featurize_rows`
      filters `is_canonical`, carries all metadata forward (platform/era for the confound
      gates, installs/stars/age for RQ2), overlays `timbro.analyze.analyze_text`. `analyze`
      is injectable so tests skip spaCy (3 tests, <0.02s). **Run PENDING — blocked on WS1
      corpus.parquet** (dedup.py + merge.py not yet run, WS1 LEDGER).
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

## RESULTS

_(none yet — first entry lands when featurize.py runs against corpus.parquet)_
