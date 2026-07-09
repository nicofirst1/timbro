# WS3 ledger — corpus analysis (INDEX)

Scan-first status matrix for WS3 (experiment-discipline §4, references-ledger layout).
One row per experiment: `ID · what it tests · STATUS · one-line result (pointer)`. Full
PRE-REG + RESULT detail lives in `LEDGER_LOG.md`, joined by ID — this file is a pointer,
not the evidence.

## Format & conventions

- **Numbers cited, never retyped:** every number in the LOG is cited from a generated
  artifact (`FINDINGS.md`, figures, manifests) — the ledger never retypes a number by hand.
- **Timestamps:** `YYYY-MM-DD HH:MM`.
- **`is_canonical` gotcha:** it is a **STRING** column with literal values `"true"` /
  `"false"` (NOT bool). Naive truthiness keeps every row — always compare to the string
  `"true"`.
- **Seed:** 42 everywhere stochastic (D1) — the 50K discovery draws, TF-IDF k-means,
  k-means fallback, CV shuffles. Deterministic steps (PCA, HDBSCAN, OLS, Spearman) carry
  no seed but are pinned by their frozen inputs.
- **Manifests** live in `../ws1/manifests/`.
- **ADR-0004/0005/0007/0008/0009/0010 bind over this file** — analysis rules (D1–D10),
  confound gates, and exploratory-vs-confirmatory framing are pre-registered there; this
  ledger records execution and results, not analysis-rule decisions.
- **STATUS vocabulary:** `RUN✓` (RESULT on record, gate cleared) · `RUN–SUPERSEDED` (ran,
  replaced by a later run) · `PRE-REG` (designed, not run) · `PENDING` (running now) ·
  `BLOCKED` (waiting on humans/access/compute) · `WON'T-RUN` (closed, decided-not-to).
- **No separate PENDING/backlog section** — the to-run backlog IS the `PRE-REG` /
  `PENDING` / `BLOCKED` rows below; a duplicate list would drift out of sync.
- **Retrieval:** to see how an experiment actually went, grep the LOG by ID —
  `grep -n "^## <ID>" LEDGER_LOG.md`. Never summarize from the INDEX line below; it is a
  pointer, not evidence.

## Status matrix

| ID | What it tests | STATUS | One-line result |
|---|---|---|---|
| WS3-0-PREREG | Umbrella pre-registration: RQ1/RQ2/RQ4 under frozen ADR-0004/0005 rules | PRE-REG | Scope/binding-rules doc; no result of its own — see child experiments below |
| WS3-1-EXTRACT | Step 1: deterministic feature vectors for canonical + RQ2-labeled docs | RUN✓ | 231,426 rows (227,407 canonical + 4,019 labeled-only), 4 failures (0.0017%) — `LEDGER_LOG.md#WS3-1-EXTRACT` |
| WS3-2-DESC | Step 2: per-source/platform descriptives + organic-vs-slop separability probe | RUN✓ | FULL CV AUC 1.000 — corpus-provenance separation, not a linguistic-dialect finding (D5 ablation fired, stays 1.000) — `LEDGER_LOG.md#WS3-2-DESC` |
| WS3-3-CLUSTER | Step 3 / RQ1: PCA → HDBSCAN → k-means fallback clustering, D4/D8/D9 confound gates | RUN✓ | Weak structure only: k-means k=5, silhouette 0.1129 (just above the 0.10 no-dialects floor); no confound gate fired — `LEDGER_LOG.md#WS3-3-CLUSTER` |
| WS3-3-PROJ | ADR-0009 exploratory: project 587 known-machine docs into the frozen step-3 geometry | RUN✓ | 80% land blob/noise, 20% in diffuse island 8, 0 in any tight template island — leans toward a refinement of hyp. (b) — `LEDGER_LOG.md#WS3-3-PROJ` |
| WS3-3-DEDUP | Exploratory follow-up: island membership vs. corpus dedup structure | RUN✓ | 0 duplicate `near_dup_cluster_id` in-population; 8/10 islands are 100%/99% single-repo template farms; 6,846 canonical heads = 12,595 corpus footprint — `LEDGER_LOG.md#WS3-3-DEDUP` |
| WS3-3-ROBUST | Robustness cut: recluster after excluding ALL 10 HDBSCAN islands | RUN✓ | Remainder N=163,132; noise 0.904, silhouette 0.093 (below D3 floor) — SUPPORTS-DIMENSIONAL, but 59.9% of exclusions fell in diverse island 8 (caveat) — `LEDGER_LOG.md#WS3-3-ROBUST` |
| WS3-3-ROBUST-SURG | Surgical robustness cut: exclude only the 9 tight template-farm islands, retain diverse island 8 | RUN✓ | Remainder N=198,545; noise 0.990, silhouette 0.0935 (below D3 floor) — SUPPORTS-DIMENSIONAL, cleanly (diversity not removed) — `LEDGER_LOG.md#WS3-3-ROBUST-SURG` |
| WS3-M-MACHINE | ADR-0009 exploratory prep: feature extraction over the 587-row machine-authored cell | RUN✓ | 587/587 rows, 0 failures, 132 feature keys — `LEDGER_LOG.md#WS3-M-MACHINE` |
| WS3-4-RQ2 | Step 4 / RQ2 (CONFIRMATORY): does linguistic style predict adoption, controlling for length/age/platform? | RUN✓ | 1/5 confirmatory features survives BH: `dict_imperative_ratio` +0.107 [+0.069, +0.145], durable across total-installs + canonical-only; other 4 null — `LEDGER_LOG.md#WS3-4-RQ2` |
| WS3-5-CHAINS | Step 5 prep: feature extraction over RQ4-eligible (≥3 version) chains | RUN✓ | 67,164/67,164 eligible version-rows, 18 failures (0.0268%, surrogate-char, not the date-frontmatter bug) — `LEDGER_LOG.md#WS3-5-CHAINS` |
| WS3-5-RQ4 | Step 5 / RQ4: temporal evolution modeling over chain features (ADR-0005) | PRE-REG | Not yet run — depends on WS3-5-CHAINS (done) |
| WS3-6-HOLDOUT | Step 6: `rq2_holdout_candidates.parquet` drift characterization | PRE-REG | Not started |
| WS3-7-HUMAN | Step 7 prep: feature extraction over the RQ5 human-baseline corpus (C1+C2 cells) | RUN✓ | 20,137/20,137 rows, 0 failures, 132 feature keys — `LEDGER_LOG.md#WS3-7-HUMAN` |
| WS3-7-RQ5 | Step 7 / RQ5: confirmatory OLS + BH battery vs. human baseline (ADR-0008 D10) | PRE-REG | Not yet run — depends on WS3-7-HUMAN (done) |
| WS3-8-MACHINE-ANALYSIS | Confirmatory/promotable analysis of the machine cell beyond ADR-0009 exploratory probes | PRE-REG | Not started |
| WS3-9-RUNALL | `run_all.py` re-runnable driver + generated `FINDINGS.md` (acceptance) | PRE-REG | Not started |

## Graveyard (superseded)

- **`featurize.py` step-1 scaffold** — superseded by WS3-1-EXTRACT (`extract_features.py`).
  See `LEDGER_LOG.md`'s graveyard section for detail.
