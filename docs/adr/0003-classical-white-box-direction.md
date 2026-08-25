# 3. Classical white-box POS for the revision direction (hybrid architecture)

- **Status:** Accepted (as-built 2026-06-13)

## Context

The direction answers _"which way do I revise?"_ A neural embedding gives a strong _scalar_ ([ADR 0001](0001-neural-style-embedding-for-the-scalar.md)) but its dimensions are opaque — you cannot hand a writer "move along latent axis 47." Timbro's non-negotiable principle is **white-box**: every output number maps to a named, documented feature. Classical POS features are interpretable by construction.

## Decision

The revision direction stays **classical / white-box**: **POS-unigram rates**, z-scored against the corpus and **confidence-weighted by each feature's regression R²** (reliable features outrank noisy ones). This makes the overall architecture **hybrid** — a _neural scalar_ with a _classical direction_.

## Consequences

- Every recommended move is a **named habit** ("more conjunctions, fewer abstract nouns, less code-block punctuation"), satisfying the white-box requirement.
- **Two representations coexist:** StyleDistance for "how far," POS for "which way." They answer different questions and are not required to agree.
- Direction quality is bounded by how well POS-unigram residuals capture the felt difference; low-R² features are down-weighted rather than dropped.

## Summary (ASD-STE100 Simplified Technical English)

The direction tells the writer how to change the draft. The neural embedding is not readable. Its dimensions do not have clear names. Timbro must stay white-box. Each output number must map to a named feature. For this reason, the direction uses POS-unigram rates. Timbro compares each rate to the corpus with a z-score. Timbro gives more weight to reliable features with the R² value. The architecture is hybrid. The scalar is neural. The direction is classical.
