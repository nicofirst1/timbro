# Timbro — Context & Ubiquitous Language

> Starter glossary, grounded in `README.md` and `docs/adr/`. Extend it via `/domain-modeling` as terms get resolved — don't let code and docs drift to synonyms this file avoids.

Timbro measures how far a draft sits from a target writing **voice** and returns a named, content-preserving revision **direction**. It does not rewrite — the calling agent does. Local, CPU-only, no LLM-as-judge.

Two independent questions, two entry points:

- **Voice alignment** (`score`) — "does this sound like the target voice?" Needs a voice corpus.
- **Prose quality** (`check`) — "is this good prose?" Needs no corpus; runs a rubric.

Why the architecture is what it is: `docs/adr/`.

## Glossary

- **Voice** — the recognizable, content-independent texture of a body of writing; what Timbro measures distance from. Prefer "voice" over loose "style" or "tone".
- **Timbre** — the naming metaphor: the quality that tells two voices apart at the same pitch. Italian _timbro_ = a stamp / seal.
- **Scalar** — the distance number, "how far" a draft sits from the voice. A pre-trained StyleDistance embedding scored by kNN ([ADR 0001](docs/adr/0001-neural-style-embedding-for-the-scalar.md), [ADR 0002](docs/adr/0002-multimodal-knn-region.md)).
- **Direction** — the named, signed revision guidance ("more conjunctions, fewer abstract nouns"); POS-unigram rates, z-scored and R²-weighted. Answers "which way", not "how far" ([ADR 0003](docs/adr/0003-classical-white-box-direction.md)).
- **Flow** — the global-architecture layer: paragraph-embedding trajectory (speed, volume, circuitousness) + the Schimel circle-back, `cos(first, last)`.
- **Exemplars** — the corpus that defines the target voice (`TIMBRO_EXEMPLARS`); the "toward" set.
- **Contrast** — the "not-this-voice" corpus (`TIMBRO_CONTRAST`); the "away" set that sharpens the boundary.
- **Profile** — a named exemplars + contrast pair on disk under the profile root.
- **Content guard** — the semantic-cosine check (a _general_ model, all-MiniLM) that meaning held; independent of voice ([ADR 0004](docs/adr/0004-no-rewrite-engine-timbro-judges.md)).
- **Rubric** — a pluggable set of deterministic prose checks (`--rubric <name>`; `schimel` ships today) that feeds `check`.
- **Check** — the corpus-free prose-quality command / tool (`timbro check`, `check_voice` MCP tool).
- **Finding** — one detected prose problem from a rubric run (passive voice, nominalization, buried subject, …), returned recall-first.
- **Move** (`FeatureMove`) — one named item in a direction: current z, target, delta, confidence.

## Consumer rules

See `docs/agents/domain.md`: read the relevant `docs/adr/` before working in an area, use these glossary terms in issue titles / tests / proposals, and surface any output that contradicts an ADR rather than silently overriding it.
