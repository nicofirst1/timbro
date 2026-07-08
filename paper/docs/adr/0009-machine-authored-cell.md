# ADR-0009 — Machine-authored register cell (exploratory, never confirmatory)

- **Status:** accepted (frozen 2026-07-08, before any collection or analysis). **Exploratory
  only** — outside every confirmatory family, outside the abstract's claims.
- **Context:** the skill-diffs corpus cannot attribute authorship — post-2023 edits are
  human/LLM-mixed with no reliable signal. A dataset hunt (2026-07-08, haiku sub-agent, all
  repos verified by fetch) confirmed the self-evolution literature (the 13-paper cluster in
  `literature.md`: `liu2026-skillforge`, `ma2026-skillclaw`, `wang2025-sage`,
  `zhang2026-skillflow`, …) ships frameworks, not skill-text data — with two exceptions below.
  They give us a provably **machine-authored** skill register cell, answering "what does
  machine-generated skill prose look like vs. the organic corpus" nearly for free.

## Decision

### Data (frozen)

- **Primary:** HF `zhang-ziao/SkillFlow-exp-skills` — ~598 final machine-generated SKILL.md
  files, evolved by **11 different LLMs** over the SkillFlow benchmark (arXiv:2604.17308 =
  `zhang2026-skillflow` in the registry). Clean per-model authorship provenance; no
  intermediate trajectories (explicitly excluded by the dataset).
- **Domain labels:** map each skill to its SkillFlow task family via the companion
  HF `zhang-ziao/SkillFlow-Task` (166 tasks, 20 workflow families, 5 domains) — this cell
  arrives pre-labeled for D8; no TF-IDF assignment needed here.
- **Qualitative vignette:** `Qwen-Applications/Trace2Skill` (GitHub, Apache-2.0) —
  `released_skills/`: 4 optimizer-evolved xlsx-skill variants + the human-written Anthropic
  baseline they evolved from. True optimizer trajectory, N too small for statistics —
  case-study box only (feature deltas baseline→evolved, reported descriptively).
- Same pipeline as every other cell: D1 dedup, English filter, `timbro analyze`, no
  cell-specific preprocessing.
- **License caveat:** SkillFlow datasets are licensed "other"/unspecified. Guardrail 2
  already covers us (redistribute feature vectors only, never raw text); noted here so no
  future step ships their text.
- **Name-collision warning (live trap, hit twice on 2026-07-08):** HF
  `beita6969/SkillFlow-Dataset` is an **unrelated** GFlowNet project sharing the name —
  do not use. "SkillForge" is similarly overloaded (our verified citation is
  `liu2026-skillforge`, arXiv:2604.08618; the GitHub `tripleyak/SkillForge` is an unrelated
  router). Every artifact in this line of work gets pinned by arXiv ID + exact repo/dataset
  ID, never by name.

### Analysis (exploratory, D-rule style but never confirmatory)

- Descriptive comparison of the machine-authored cell vs. the organic canonical corpus on
  the full feature set; per-model (11 LLMs) register variation reported descriptively.
- Optional probe mirroring D5: machine-vs-organic classifier AUC, with the same drop-one
  ablation guard if AUC > 0.99.
- No hypothesis tests, no BH family, no promotion to headline claims. Findings feed the
  RQ4 discussion (organic edits vs. machine authorship) and the future-work section
  (within-loop trajectories = re-running SkillFlow's open harness; the follow-up-paper
  direction already pointed at by ADR-0005 addendum 2).

### Timebox / kill

~Half a day of collection + one analyze run. If either dataset fights back (access, parsing,
license surprise) beyond that, drop the cell, log it in the WS1 LEDGER, keep Trace2Skill as
a citation-only mention.

## Consequences

- WS1 gains step 10 (`build_machine_cell.py`); WS3 gains step 8. Both cite this ADR.
- RQ5's human-baseline cells (ADR-0008) plus this cell give the paper a three-register
  layout — human-directed, organic-agent-directed, machine-authored — all exploratory
  beyond ADR-0008's confirmatory C3-vs-C2 contrast.
