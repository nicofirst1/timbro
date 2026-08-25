# 4. No built-in rewrite engine — Timbro judges, the agent rewrites

- **Status:** Accepted (as-built 2026-06-13)
- **Supersedes:** the initial build plan's Phase 4 rewrite engine, TinyStyler (now retired)

## Context

The plan's Phase 4 was to ship a rewrite engine: TinyStyler plus a content-preservation guard. TinyStyler proved **not pip-installable** and **domain-mismatched on long essays**. More fundamentally, an LLM agent is already a better rewriter than any bundled small model — and Timbro's job is _measurement_, not _generation_.

## Decision

Timbro ships **no rewrite engine**. It scores (distance + named direction) and guards content; the **calling agent does the rewriting**, in a `score → edit → re-score` loop. The **content guard** is a semantic cosine from a _general_ model (all-MiniLM) that checks meaning held, independent of voice.

## Consequences

- **Clean separation:** Timbro is the judge, the agent is the engine — delivered as an MCP accept-rewrite loop.
- No dependency on TinyStyler or any generation model / weights; stays **CPU-only, inference-only**.
- Content preservation is enforced as a **gate** (semantic cosine), not assumed.

## Summary (ASD-STE100 Simplified Technical English)

The plan included a rewrite engine in Phase 4. The engine used TinyStyler and a content guard. TinyStyler did not install with pip. TinyStyler did not work well on long essays. An LLM agent rewrites text better than a small model. Timbro measures text. Timbro does not make new text. For this reason, Timbro has no rewrite engine. Timbro gives a score and a direction. Timbro also guards the content. The agent rewrites the text. The agent uses a loop: score, edit, and score again. The content guard uses a semantic cosine. The guard makes sure the meaning stays the same.
