# WS3 — Corpus analysis

Turns `paper/data/corpus.parquet` (WS1 output) into the paper's RQ1–RQ4 findings. Reads `main`'s Timbro (`timbro analyze`, #17/#18) — the `paper` branch predates that merge. Governed by the `experiment-discipline` skill; per-step results and the frozen analysis rules (D1–D9, ADR-0004/0005) are cited in [`LEDGER.md`](./LEDGER.md). ADRs win on any conflict.

WS1 is closed (2026-07-09); all four feature tables are extracted. Steps 1–4 are RUN✓, RQ4/RQ5 confirmatory analyses pending — see [`LEDGER.md`](./LEDGER.md).

## Reproducibility contract (inherited from WS1)

1. **Every number is produced by a committed script**, never hand-typed. `FINDINGS.md` (the acceptance memo) is generated, not authored by hand.
2. **Seed is 42 everywhere** (PCA/HDBSCAN/k-means init, any bootstrap/CV sampling).
3. **Data is never committed.** Features + figures land in `paper/data/` / `paper/figures/` (gitignored). Only scripts, `LEDGER.md`, `FINDINGS.md`, `DEVIATIONS.md` are tracked.
4. **Pre-registered rules bind.** Length AND age are always covariates; multiple-comparison correction (BH, D6) always; effect sizes with CIs. Any departure → `DEVIATIONS.md`.
5. **Redistribute derived features, never raw skill text** (ADR-0003).

## Layout (per-step dirs since 2026-07-10; older LEDGER entries cite the pre-reorg flat paths)

```
paper/code/ws3/
├── LEDGER.md            # scan-first INDEX (plain language, one row per experiment ID)
├── LEDGER_LOG.md        # full technical LOG, grep by ID: grep -n "^## WS3-" LEDGER_LOG.md
├── common/              # shared helpers (featurize.py)
├── step1_extraction/    # feature extraction: main / machine / chains / human tables
├── step2_descriptives/  # corpus descriptives + summary CSVs
├── step3_clustering/    # RQ1: clustering, dedup probe, machine projection, robustness
├── step4_adoption/      # RQ2: install-rate regression
├── tests/               # pure-seam unit tests (conftest.py wires the step dirs)
├── run_all.py           # (todo) re-runnable driver
├── FINDINGS.md          # (todo, generated) acceptance memo
└── DEVIATIONS.md        # (todo) any departure from the pre-registered rules
```

Upcoming analyses get their own dirs when they land: step5 (RQ4 temporal), step7 (RQ5 human).

## Steps (PLAN.md §4 WS3)

1. **featurize** — `timbro analyze` over canonical docs → `features.parquet`. _(scaffolded)_
2. **descriptives** — feature distributions per source/platform; organic-vs-slop AUC.
3. **RQ1 clustering** — standardize → PCA → HDBSCAN (fallback k-means); name clusters; confound gates platform (D4) / domain (D8) / era (D9).
4. **RQ2 adoption** — regress `log1p(installs_wk_mean)` (+ robustness outcomes) on features, log-length + log-age covariates, platform/domain FE, repo RE; BH per D6.
5. **RQ4 temporal** — chains ≥3 versions (ADR-0005), 14,388 eligible; embedding-delta explor.
6. **holdout** — characterize `rq2_holdout_candidates.parquet` novelty before scoring.

## Run

```bash
uv run pytest paper/code/ws3/tests/                 # pure seams, no data needed
uv run python paper/code/ws3/step1_extraction/extract_features.py   # needs corpus.parquet (WS1)
```
