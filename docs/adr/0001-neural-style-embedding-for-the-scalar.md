# 1. Neural style embedding for the scalar, not fitted classical stylometry

- **Status:** Accepted (as-built 2026-06-13)
- **Supersedes:** the initial build plan's classical-first primary discriminator (now retired)

## Context

The scalar answers _"how far is this draft from the target voice?"_ The corpus is tiny — n ≈ 15 posts. The plan opened classical-first, citing the Valla benchmark (Tyo et al. 2023): classical n-gram/frequency stylometry beats neural style embeddings when per-author samples are few (76.5% vs 66.7% macro-accuracy). So the primary discriminator was to be _fitted_ classical features (LFTK / BiberPlus / Gram2Vec / writeprints → feature-selected → Mahalanobis).

Phase 1 falsified that at our n. Every fitted classical combination underperformed its own best single member — added dimensions accrue noise faster than signal at n ≈ 15. POS-unigrams, the best single backbone, topped out at **0.76 leave-one-out AUC** against same-domain contrast and could not clear the **0.80** gate. A _pre-trained_ StyleDistance embedding scored by kNN reached **0.86**.

## Decision

The scalar is a **pre-trained StyleDistance embedding**, not fitted classical features.

## Consequences

- **The lesson:** Valla's "classical wins at small n" holds for representations you _fit_ on the corpus. A _pre-trained_ style embedding doesn't pay the small-n tax — it arrives trained on massive authorship data and needs only a few points to locate a region.
- The classical backbones and the fitted-feature Mahalanobis path were dropped **from the scalar**. Classical POS survives in the _direction_ — see [ADR 0003](0003-classical-white-box-direction.md).
- These are **leave-one-out AUC** figures — validation discriminability against a hard same-domain contrast, _not_ the product's distance score (the 0–100 scale in the README is a separate output).
- Reframed target: **0.86 is the hard bar** (you vs other expert AI/ML writers); against generic writers discriminability is ~0.93, and that is the actual product use case.

## Source

Deep research record: `claude_memory/wiki/research/voice-style-metric-space.md`.

## Summary (ASD-STE100 Simplified Technical English)

The corpus is small. It has approximately 15 posts. The plan selected classical features first. At this size, classical features did not separate the voice well. The best classical score was 0.76 AUC. The gate is 0.80. The classical features did not pass the gate. The pre-trained StyleDistance embedding scored 0.86 AUC. It passed the gate. For this reason, the scalar uses the StyleDistance embedding. A pre-trained embedding does not need many posts. These scores show the test accuracy. They are not the product distance value.
