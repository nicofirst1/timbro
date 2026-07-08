# ADR-0001 — Scope, venue, and determinism locks

- **Status:** accepted (locked 2026-07-04 — do not relitigate)
- **Context:** master-plan decisions taken while capable-model access existed, to keep less
  capable executing agents from re-opening settled questions. Formerly §0 of the master plan.

## Decision

1. **Scope:** corpus study + small pilot execution experiment. NOT a full sandbox A/B pipeline.
2. **Feature extraction is open-source only.** No LIWC license, no Coh-Metrix. Frame features
   as "LIWC-style / Coh-Metrix-style" indices.
3. **Corpus:** built from existing HF datasets + sanctioned ClawHub harvest + (optional) fresh
   GitHub top-up. Corpus construction is a paper contribution. *(2026-07-08: ClawHub dropped
   as a data source, GitHub top-up rejected as redundant — [ADR-0006](0006-drop-clawhub.md).)*
4. **Venue:** ACL Rolling Review **October 2026 cycle** → NAACL/ACL 2027 (primary).
   NeurIPS 2026 agents workshop as early outing (CFPs ~Aug–Sep 2026). COLM 2027 backup.
5. **Timbro:** existing profiles + rubrics usages stay untouched. New work = vertical slices
   (skill-document parsing, feature extraction). Golden rule: **never reimplement what a
   maintained library provides.**
6. **Everything at analysis time is deterministic** (spaCy/regex/counting). No LLM-as-judge in
   feature extraction. LLMs appear only as the *subject* of the pilot experiment (WS4).

## Consequences

- Executing agents follow PLAN.md workstreams within these bounds; a spec/reality conflict
  triggers rule D7 ([ADR-0004](0004-ws3-preregistration.md)): stop and ask, never substitute.
- Venue calendar drives WS6 (PLAN.md).
