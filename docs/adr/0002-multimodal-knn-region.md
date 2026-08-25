# 2. Multi-modal kNN acceptance region, not a single Gaussian

- **Status:** Accepted (as-built 2026-06-13)
- **Supersedes:** the initial build plan's single-Gaussian region model (now retired)

## Context

Given the scalar embedding ([ADR 0001](0001-neural-style-embedding-for-the-scalar.md)), the _region model_ decides how "distance from the voice" is actually computed. The plan specified a single Gaussian acceptance region: PCA → LedoitWolf covariance shrinkage → Mahalanobis distance (LedoitWolf was called _critical_ at n ≈ 15, since raw covariance is singular).

A single Gaussian assumes one unimodal blob. A real voice corpus is often **multi-register** — e.g. one author's blog posts and papers form two distinct clusters. On such a corpus the single-Gaussian model was falsified: it pulls the mean into the empty space _between_ clusters and mis-scores drafts from both.

## Decision

The acceptance region is a **multi-modal kNN** model over the embedding space, not a single Gaussian (Mahalanobis).

## Consequences

- **Handles multi-register voice:** a draft is scored by proximity to its nearest exemplars, so each register is its own neighbourhood.
- No covariance to regularize — the LedoitWolf / Mahalanobis machinery is gone.
- kNN needs enough exemplars _per register_; very small or single-register corpora still work, with coarser resolution.

## Summary (ASD-STE100 Simplified Technical English)

The plan used one Gaussian region. The region used PCA, LedoitWolf shrinkage, and Mahalanobis distance. One Gaussian region is correct for one group of data. A voice corpus can have more than one group. For example, blog posts and papers make two groups. On two groups, the one Gaussian region failed. It put the center in the empty space between the groups. For this reason, the region model uses kNN. The kNN model scores a draft with its nearest examples. Each group keeps its own area. The kNN model needs enough examples in each group.
