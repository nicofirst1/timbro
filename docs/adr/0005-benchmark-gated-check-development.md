# 5. Benchmark-gated check development — a check's claim is capped by its evidence

- **Status:** Accepted (decided 2026-08-25)
- **Relates to:** #8, #15; killed #7, #38 and the assumptions half of #30 under this rule; spun off #74

## Context

Some proposed `check` rules want to reason about what a passage _means_ (unstated assumptions, thesis placement, filler sentences). The rubric is **recall-first** — it over-flags and the agent filters — so "the signal is plausible" is a dangerously low bar: a check that fires on nearly everything adds nothing and erodes trust in the others. `no-LLM-as-judge` bars the easy escape. So how do we know a semantic check is good enough to ship?

## Decision

A check earns its **claim tier** by benchmark, not plausibility. The benchmark gates the _claim_, not the `agent:mechanical` label — a fully-specced check can be mechanical to build yet ship at a low tier. "No benchmark" caps the claim; it does **not** forbid the check.

- **Tier A — validated:** a labelled benchmark exists and the signal **beats dumb baselines** (position, length, centrality). Default-on, high severity, can back a citable number (#15).
- **Tier B — optional:** no recall benchmark, but plausible and clean on the FP dashboard (`eval/rubric_dashboard.py`). Opt-in, low severity, labelled "unvalidated for recall."
- **Tier C — manual:** no deterministic signal reaches it. Documented (below), not shipped.

## Consequences

Three signals were spiked against real benchmarks and **all three failed** — the rule working, not a setback. A dumb position/length prior is the bar, and none cleared it:

| Signal                        | Benchmark                | Result                                         |
| ----------------------------- | ------------------------ | ---------------------------------------------- |
| centrality (thesis, #38)      | real blog post           | finds summaries, not the thesis                |
| "hinge" (thesis, #38)         | GUM + SciDTB (CC-BY)     | loses to a position prior; top-3 ≈ 0.13 / 0.26 |
| zlib compression (filler, #7) | CNN/DailyMail extractive | AUC ≈ 0.59; loses to sentence length           |

**Deliberately manual (Tier C)** — recorded so they aren't re-filed as new:

- Smuggled/unstated assumptions (#30) — the proxy fires on every confident sentence.
- Presupposition failure, "reader doesn't know X yet" (#30) — needs the reader's knowledge state. (The catchable slice ships as #74.)
- Thesis placement (#38) — both embedding proxies killed above.

## Summary (ASD-STE100 Simplified Technical English)

A check that looks correct is not good enough, because the rubric shows many findings on purpose. A check must prove it works on a data set with correct answers, and it must beat simple rules like word position. If it wins, it is a normal check. If there is no data set, it can ship only as an option, and you must say it is not proven. If no signal finds the answer, do the check by hand. The team tried three checks; all three lost to a simple position rule, so the team did not ship them.
