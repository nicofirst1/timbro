# eval/benchmarks — benchmark-gating a new check

Before a semantic-leaning `check` ships as a first-class (Tier A) rule, it must beat dumb baselines on a real labelled benchmark. See `../../docs/adr/0005-benchmark-gated-check-development.md` for the tiered rule; this directory is the _how_.

## The recipe

1. **Find a labelled benchmark.** Prefer a permissively-licensed public dataset (HF / academic) whose labels map to what the check claims to find. Do **not** hand-cook synthetic positives — they flatter recall.
2. **Race the signal against dumb baselines.** The bar is not "better than nothing" — it's "better than the laziest rule."
   - _Locator_ check (find the one X — thesis, core insight): position priors (first / last / middle unit), centrality, random.
   - _Classifier_ check (is this unit X? — filler / not): sentence length, sentence position, base-rate. Use `race.py` for the top-k / MRR comparison.
3. **Read the verdict into a tier** (ADR-0005): beats the baselines on a real benchmark → Tier A; no benchmark but clean on the FP dashboard → Tier B (opt-in, "unvalidated for recall"); nothing works → Tier C (manual, documented in the ADR).

## Existing baseline-racers

- `../harness.py` — voice-model LOO-AUC vs a permutation baseline (Phase-1/2 gate).
- `../rubric_dashboard.py` — findings-per-1000-words on known-good prose (the FP / Tier-B sniff-test).
- `race.py` — generic top-k / MRR comparison for check locators.

## Worked examples (all KILLS — the gate working)

Three semantic-check signals were spiked and killed against real benchmarks (numbers in ADR-0005): embedding-centrality and the "hinge" signal for thesis placement (GUM / SciDTB, CC-BY), and zlib compression-cost for filler sentences (CNN/DailyMail extractive). Each lost to a position or length prior. The spike scripts are **not** vendored here (they pull external datasets and validated checks we then killed); reproduce from the ADR's description if the question is revisited.
