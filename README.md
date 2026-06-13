# Timbro

**Measure the *timbre* of your writing — the quality that makes a sentence recognizably yours — as a position in a metric space, and get an interpretable direction to move a draft toward your voice, without changing what it says.**

Not an LLM-as-judge. A statistical, white-box, local tool: seed a reference region from a few posts whose writing you love, then score any draft for (1) a **distance** from your voice and (2) a **signed, named revision direction** ("shorten sentences, fewer nominalizations, close the loop back to your opening"). Built to be called by an LLM over MCP mid-draft.

The name carries the idea: *timbre* (the acoustic quality distinguishing two voices at the same pitch) and Italian *timbro* (a stamp / seal — a signature).

## Status

Planning. See **[`PLAN.md`](./PLAN.md)** for the full vision, architecture, requirements, phased build, and evaluation protocol.

## At a glance

- **Two layers:** *style* (content-invariant word/sentence texture) and *flow* (content-bearing paragraph connection / the Schimel "circle-back").
- **Classical-first:** the literature (Valla benchmark) shows classical stylometry beats neural embeddings at small per-author sample sizes — and it's the more interpretable choice. Embeddings are a secondary lens.
- **Reuse-first:** ~300 lines of novel glue; everything else is `pip`-installable and local (LFTK, BiberPlus, Gram2Vec, faststylometry, sentence-transformers, TAACO, scikit-learn).
- **Falsifiable:** every build phase has an evaluation gate (leave-one-out AUC, shuffle test, direction sign test).

## Research provenance

The full literature + tooling research behind this plan lives in the wiki:

- **Synthesis (citations, reuse matrix, eval):** `claude_memory/wiki/research/voice-style-metric-space.md`
- **Raw agent reports (4):** `claude_memory/wiki/research/raw/`
  - `2026-06-13-style-metric-space-survey.md`
  - `2026-06-13-discourse-structure-survey.md`
  - `2026-06-13-literature-completeness-audit.md`
  - `2026-06-13-tools-and-evaluation-inventory.md`

## License

MIT (intended).
