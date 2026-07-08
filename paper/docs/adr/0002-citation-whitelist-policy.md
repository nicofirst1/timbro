# ADR-0002 — Novelty position and citation-whitelist policy

- **Status:** accepted (verified 2026-07-04; whitelist extended 2026-07-07)
- **Context:** the paper's novelty claim must survive adversarial review, and early
  deep-research output contained a fabricated citation — so citations are allowlisted and
  every source is verified (fetch-and-confirm) before use. Formerly §2 of the master plan.

## Decision

Cite only from the whitelist below or newly *verified* sources (fetch and confirm the paper
exists and says what you claim — never cite from memory). `paper/literature/literature.md`
is the authoritative verified-source registry (~76+ papers; amendment 2026-07-07); the set
below is the core positioning whitelist.

### Novelty position

Coverage matrix vs. closest prior art:

| Features \ Outcome | Adoption proxies | Execution success |
|---|---|---|
| Token count / taxonomy / risk labels | Ling et al. 2026 (descriptive only; length never correlated with installs) | — |
| Measured psycholinguistic/syntactic features | **unclaimed — ours** | **unclaimed — ours** |
| Controlled restyling of *instruction files* | — | **unclaimed — ours** |

- **Ling et al., arXiv:2602.08004** — 40,285 skills.sh listings, structural/marketplace stats,
  no linguistic features beyond token count, no execution. Cite as corpus/adoption precedent;
  note their caveat that install counts are noisy/promotable.
- **Cho et al., arXiv:2601.10809** ("A Concise Agent is Less Expert") — prompted style personas
  on *chat replies*, LLM-judged perception, no measured features, no execution. Differentiate on
  (i) measured features vs. prompted labels, (ii) execution vs. perception, (iii) instruction
  documents vs. conversational responses.
- **Raw length must be a covariate everywhere** (length effects on perception are claimed by Cho).

### Core whitelist (verified real)

PromptPrism (arXiv:2505.12592, Findings of EACL 2026) · prompt-datasets study
(arXiv:2510.09316) · Ling et al. (arXiv:2602.08004) · Cho et al. (arXiv:2601.10809) ·
ClawGym (arXiv:2604.26904; note: 13.5K tasks are *training* data, eval bench = 200 instances) ·
SWE-World (arXiv:2602.03419) · Harbor (github.com/laude-institute/harbor, Terminal-Bench team) ·
olmo-eval (Ai2, June 2026) · Graph of Skills (arXiv:2604.05333) ·
"Prompting in the Wild" (arXiv:2412.17298, MSR 2025) · PromptSet.

**Promoted 2026-07-07** (from `literature/literature.md`, fully read/verified):

- SkillForge (`liu2026-skillforge`, arXiv:2604.08618) — closest methodological neighbor found:
  measures a named "Style" axis of skill text with a task-outcome link, but it is an LLM-judged
  single tone axis in customer support ≠ our measured deterministic feature vector ×
  adoption/execution. Needs a direct differentiation note in related work.
- ClawHub study (`hu2026-clawhub`, arXiv:2604.13064) — closest RQ1 analog: cross-lingual
  functional clustering of 26,502 skills (crawled up to 2026-03-18), but topic-level only —
  TF-IDF + Truncated SVD + k-means on title+summary; verifier searches for readability/Flesch/
  syntactic/style features all NOT FOUND (verified 2026-07-07) — our differentiation holds.
  Adjacent, not competing: their submission-time risk prediction found "primary documentation
  emerging as the most informative submission-time signal" (best classifier LogReg 72.62% acc /
  78.95 AUROC) — the closest existing text→outcome result, but it predicts security risk, not
  adoption.
- SoK: Agentic Skills (`jiang2026-sokskills`, arXiv:2602.20867) — representation × scope
  taxonomy naming natural-language-only skill prose as a first-class category; RQ1 positioning.
  (Verified 2026-07-07: verbatim abstract obtained; no linguistic measurement — readability/
  linguistic/style/lexical all NOT FOUND. Documents the ClawHavoc campaign, ~1,200 malicious
  skills.)
- SkillsBench (`li2026-skillsbench`, arXiv:2602.12670) — 87-task execution benchmark; "compact
  documentation (+19.0/+21.5pp) outperformed exhaustive prose (+0.7pp)"; RQ3 precedent and
  candidate WS4 harness.
- Biber 1988 (*Variation across Speech and Writing*) + Biber & Egbert 2018 (*Register Variation
  Online*) — Multidimensional Analysis, the methodological precedent for the RQ1 clustering
  pipeline ([ADR-0004](0004-ws3-preregistration.md)).

### Resolved novelty risks

**✓ NO OVERLAP (verified 2026-07-07, fetch-and-quote against arXiv):** `skillstructure2026`
(arXiv:2604.24026, "From Skill Text to Skill Structure") — formerly the largest unresolved
novelty risk — converts skill text into a structured SSL representation via an LLM normalizer
and evaluates representation quality (Skill Discovery MRR@50 0.649→0.729; Risk Assessment
macro F1 0.409→0.509). No linguistic feature measurement, no adoption metrics. Bonus: its
abstract line — skills are "text-heavy artifacts... whose machine-usable evidence remains
embedded largely in natural-language descriptions" — is usable as motivation for our
linguistic lens.

**Known-fabricated (never cite):** "Prompts in the Wild" (ACL, 57.5K-prompt ontology study) —
does not exist; it was hallucinated in the original deep-research report.

## Consequences

- Any new citation requires verification before use; unverified sources block the writing, not
  the other way around.
- Related work must differentiate explicitly vs. Ling, Cho, SkillForge, hu2026-clawhub.
