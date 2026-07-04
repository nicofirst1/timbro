# Paper plan — Linguistic topology of agent skill files

**Status:** master plan, verified 2026-07-04. Written to be executable by less capable models.
**Branch policy:** all paper work lives on the `paper` branch under `paper/`. Only Timbro
functionality (WS2) merges to `main`, via normal issue/PR flow.

---

## 0. Locked decisions — do not relitigate

1. **Scope:** corpus study + small pilot execution experiment. NOT a full sandbox A/B pipeline.
2. **Feature extraction is open-source only.** No LIWC license, no Coh-Metrix. Frame features
   as "LIWC-style / Coh-Metrix-style" indices.
3. **Corpus:** built from existing HF datasets + sanctioned ClawHub harvest + (optional) fresh
   GitHub top-up. Corpus construction is a paper contribution.
4. **Venue:** ACL Rolling Review **October 2026 cycle** → NAACL/ACL 2027 (primary).
   NeurIPS 2026 agents workshop as early outing (CFPs ~Aug–Sep 2026). COLM 2027 backup.
5. **Timbro:** existing profiles + rubrics usages stay untouched. New work = vertical slices
   (skill-document parsing, feature extraction). Golden rule: **never reimplement what a
   maintained library provides.**
6. **Everything at analysis time is deterministic** (spaCy/regex/counting). No LLM-as-judge in
   feature extraction. LLMs appear only as the *subject* of the pilot experiment (WS4).

## 1. Research questions

- **RQ1 (topology):** Do deterministic linguistic features of agent skill files — imperative
  density, syntactic depth, cohesion, hedging/certainty, readability, POS+dep-relation
  distributions — cluster into distinct "instruction dialects" across ecosystems
  (Claude Code, OpenClaw, OpenCode, Hermes)?
- **RQ2 (adoption):** Do these features predict adoption proxies (installs/downloads, stars,
  update survival), controlling for length, topic, and ecosystem?
- **RQ3 (execution, pilot):** Does restyling a skill's prose into a different linguistic
  profile — content held constant — change agent task-success rate?

**Explicitly avoided (saturated):** predicting static generation quality or domain
classification from these features (PromptPrism; arXiv:2510.09316).

## 2. Novelty position (verified 2026-07-04)

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

### Citation whitelist (verified real — use only these until extended)

PromptPrism (arXiv:2505.12592, Findings of EACL 2026) · prompt-datasets study
(arXiv:2510.09316) · Ling et al. (arXiv:2602.08004) · Cho et al. (arXiv:2601.10809) ·
ClawGym (arXiv:2604.26904; note: 13.5K tasks are *training* data, eval bench = 200 instances) ·
SWE-World (arXiv:2602.03419) · Harbor (github.com/laude-institute/harbor, Terminal-Bench team) ·
olmo-eval (Ai2, June 2026) · Graph of Skills (arXiv:2604.05333) ·
"Prompting in the Wild" (arXiv:2412.17298, MSR 2025) · PromptSet.

**Known-fabricated (never cite):** "Prompts in the Wild" (ACL, 57.5K-prompt ontology study) —
does not exist; it was hallucinated in the original deep-research report.

## 3. Corpus facts (empirically probed 2026-07-04)

| Source | What it is | Unique full-text skills | Outcome proxies | License |
|---|---|---|---|---|
| HF `shl0ms/skill-diffs` | Full SKILL.md snapshots per commit, 5,891 GitHub repos, 4 platforms | **~630K–665K** (use `bundled` config or latest `after_content` per `skill_id`) | repo `stars`, dates, `intent_class`, `quality_score`; **no installs** | per-record `license_spdx` — filter per row |
| HF `davidliuk/graph-of-skills-data` | Paper-curated benchmark libraries (`skills_2000.tar.gz` is the superset) | 2,000 (substantive, ~6KB avg) | none | MIT |
| ClawHub live registry | Sanctioned API: `GET https://clawhub.ai/v1/feeds/skills` (all 549, one request, robots.txt-allowed) + per skill `GET /api/v1/skills/{slug}/file?path=SKILL.md`; rate limit 3000 reads/min; authenticated `/api/v1/skills/export` ZIP exists | **549** (small!) | catalog sortable by `downloads` — skill-level adoption signal | must cache, honor 429, link back to canonical pages |
| HF `amoghacloud/clawskills-intelligence-corpus` | 5,147 near-identical templated stubs ("SISR" boilerplate, ~400B each) | ~5.1K **low-quality stubs** | none | MIT |
| skills.sh marketplace (unprobed) | Ling et al.'s source: 40,285 listings with per-platform install counts | unknown — needs probe | **skill-level installs** | unknown — needs probe |

Corpus conclusions baked into the plan:
- **skill-diffs anchors the corpus** (2–3 orders of magnitude larger than everything else).
- The earlier "~13,700 ClawHub skills" claim is stale/wrong: live ClawHub = 549. Larger numbers
  referred to skills.sh or a pre-purge registry. Do not repeat the 13.7K figure.
- The slop-stub corpus is **kept as a labeled low-quality class** — a validation set for whether
  our features separate templated slop from organic documentation (on-brand for Timbro).
- Skill-level installs exist only on skills.sh (40K) and ClawHub (549). GitHub stars are
  repo-level (many skills per repo → attenuated signal; model with repo random effects or
  restrict to single-skill repos for the star analysis).
- **Redistribute derived feature vectors, never raw skill texts.** skill-diffs is mixed-license
  (per-record SPDX); ClawHub reuse terms require caching + linkback + no mirroring.

## 4. Workstreams

Dependency order: WS1 → WS3 needs WS2 → WS4 needs WS3 → WS5 needs all. WS6 is calendar-driven.

### WS1 — Corpus assembly (July) — `agent:mechanical`

Code in `paper/corpus/`, data in `paper/data/` (**gitignored** — add `paper/data/` to
`.gitignore` in the first commit that creates it).

1. `build_skill_diffs.py`: stream `shl0ms/skill-diffs` with `datasets` (streaming mode, do not
   load 8GB in RAM). Emit one row per unique `skill_id`: latest SKILL.md text, `repo`,
   `platform`, `stars`, `license_spdx`, first/last commit dates, `n_revisions`.
2. `build_gos.py`: download `skills_2000.tar.gz` only (29MB), extract SKILL.md files.
3. `build_clawhub.py`: fetch feed (1 request), then per-skill file fetches for all 549 with the
   documented recipe; sleep to stay far under 3000/min; record `downloads` metadata. The
   2026-07-04 feed snapshot is already saved (see scratchpad note in §7); re-fetch fresh anyway.
4. `build_slop.py`: clone `amoghacloud/clawskills-intelligence-corpus` (few MB), tag every doc
   `source=slop_stub`.
5. `dedup.py`: exact dedup by normalized-text SHA256; near-dup with MinHash
   (**use `datasketch`**, do not hand-roll), threshold 0.9 Jaccard on 5-gram shingles; keep one
   canonical doc per cluster, record `near_dup_cluster_id` and cluster size.
6. Merge to `paper/data/corpus.parquet` with schema:
   `skill_id, source, platform, text, frontmatter_json, repo, stars, downloads, installs,
   created_at, updated_at, license_spdx, n_revisions, near_dup_cluster_id, is_canonical`.
   (nullable where a source lacks the field).

**Acceptance:** a `paper/corpus/REPORT.md` with per-source counts, dedup stats
(exact + near-dup removal rates), platform breakdown, license breakdown. No data files in git.

**Open sub-task (needs one probe agent):** skills.sh — can full SKILL.md text + install counts
be harvested, and under what terms? If yes, add `build_skillssh.py`; this is the best
adoption-outcome source for RQ2. If terms are unclear, ask the user before scraping.

### WS2 — Timbro vertical slices (July–Aug) — file as GitHub issues on `main`, one per branch/PR

Follow repo conventions (CLAUDE.md): implementer specs are decisions; run
`uv run pytest` + `uv run ruff check src/` before done; don't touch `_PENALTY`/`_WEIGHTS`/verdicts.

**Issue A — `timbro analyze` feature-extraction command** (`agent:mechanical` once spec'd):
- New CLI subcommand: `timbro analyze <paths...> --format jsonl|csv` → one feature vector per
  document. Reuses the existing spaCy pipeline and the #16 markup preprocessing (frontmatter/
  markdown/HTML stripping) to isolate prose; structural features computed on the *raw* markdown.
- Feature groups (deterministic, CPU-only):
  - `desc_*`: tokens, sentences, chars, mean sentence length — via **textdescriptives**.
  - `read_*`: readability suite — via textdescriptives.
  - `syn_*`: dependency distance, parse-tree depth, clausal-embedding depth (count of
    clausal dep labels `ccomp/xcomp/advcl/acl/relcl` per sentence) — textdescriptives + spaCy.
  - `posdep_*`: the 62-d POS-tag + dep-label relative-frequency vector (plain spaCy counting;
    replicates the routing-features literature).
  - `coh_*`: adjacent-sentence noun/argument overlap (custom spaCy counting — no maintained
    open lib exists; keep it a simple lemma-overlap ratio) + textdescriptives embedding
    coherence as the LSA-style proxy.
  - `lex_*`: MTLD/HDD via **lexical-diversity**; wordfreq-based rarity (dep already exists).
  - `dict_*`: imperative-sentence ratio (sentence-initial base-form verb with no explicit
    subject); hedges (Hyland's published hedge list); certainty/boosters (Hyland's boosters);
    negation list; conditional/logical connectives (`if/then/else/when/unless/otherwise`).
    Word lists ship as data files under `src/timbro/lexicons/` with source citations in-file.
  - `struct_*`: heading count/depth, code-block char ratio, list-item ratio, table count,
    prose/markup ratio, frontmatter field set.
- **Dependencies allowed to add:** `textdescriptives` (Apache-2.0), `lexical-diversity` (MIT),
  `datasketch` (MIT, corpus-side only — may live in `paper/` instead of the package).
  **Forbidden:** LFTK (CC BY-NC), empath (dead), textacy (stalled), lingfeat (archived).
- Acceptance: `uv run timbro analyze README.md --format jsonl` emits a valid vector; features
  documented in a table (name, definition, library or lexicon source); tests for the custom
  extractors (imperative detection, overlap, lexicon counts) with hand-checked fixtures.

**Issue B — skill-document structural profile** (small): expose the `struct_*` group +
frontmatter parsing as a reusable slice (mostly extends #16). May fold into Issue A if the diff
stays small.

**Non-goals:** no new rubric, no changes to scoring/verdicts, no LLM calls, no network at
analyze time.

### WS3 — Corpus analysis (Aug) — `paper/analysis/`

1. Run `timbro analyze` over `corpus.parquet` canonical docs → `paper/data/features.parquet`.
2. Descriptives: feature distributions per source/platform; organic vs. slop-stub separability
   (simple logistic regression / AUC — validates the feature set and gives a Timbro story).
3. Clustering (RQ1): standardize features; PCA then HDBSCAN (fallback k-means, k by silhouette);
   name clusters by their most-deviant features; map clusters onto the heuristic table from the
   original research report (imperative-dense vs. conditional-rich vs. narrative, etc.).
4. Adoption models (RQ2): Spearman screens, then regressions of log(1+installs|downloads|stars)
   on features with **log-length covariate**, platform fixed effects, repo random effects (or
   single-skill-repo subset for stars). Benjamini–Hochberg across the feature family.
   Report effect sizes with CIs, not just p-values.
5. Bonus (cheap, data already there): stylistic drift over time using skill-diffs revision
   history — are skills converging toward one dialect?

**Acceptance:** scripted, re-runnable (`uv run python paper/analysis/run_all.py`), figures to
`paper/figures/`, a findings memo `paper/analysis/FINDINGS.md`.

### WS4 — Pilot execution experiment (Sep) — `agent:judgment`, spec finalized after WS3

Design skeleton (do not run without user budget approval):
- ~20–30 tasks from Harbor/Terminal-Bench (or ClawGym's 200-instance eval bench) where a skill
  file is loaded.
- For each task's skill: 3–4 **content-preserving restylings**, one per WS3 cluster profile.
  Timbro verifies each variant actually lands in the target linguistic profile (dogfooding).
- Fixed model, 3 seeds, deterministic verifier from the framework. ≈ 240–360 runs.
- Analysis: paired success rates (McNemar / mixed-effects logistic), report minimum detectable
  effect; a null result is publishable as "topology matters for adoption but not execution at
  this scale" — do not spin it.

### WS5 — Manuscript (Sep–Oct) — `paper/manuscript/`

Outline: Intro → Related work (whitelist above; position vs. Ling and Cho explicitly) →
Corpus & tool (Timbro release, `uvx` trial path — coordinate with repo issue #9 so reviewers
can run it) → Topology & adoption findings → Pilot → Limitations (proxies ≠ quality; pilot
scale; English-only; install-count noise per Ling). Run the `schimel-pass` and `nico-voice`
skills on drafts. ARR needs: anonymized repo, derived-features-only data release, license
statement per §3.

### WS6 — Venue calendar

- **~Jul 11, 2026:** NeurIPS 2026 workshop list drops — pick an agents workshop, note its CFP
  (Aug–Sep). Workshop paper = WS1+WS2+WS3 only.
- **ARR Oct 2026** (exact deadline TBA, assume mid-Oct): full paper. Buffer: WS5 draft done
  by Oct 1.
- Backup: COLM 2027 (~late Mar) if WS4 becomes the centerpiece.

## 5. Guardrails for executing agents

1. **Citations:** only from the whitelist in §2 or newly *verified* sources (fetch and confirm
   the paper exists and says what you claim). Never cite from memory.
2. **Data hygiene:** nothing under `paper/data/` gets committed. Redistribute feature vectors,
   never raw skill text.
3. **Politeness:** honor documented rate limits and 429/Retry-After on any harvest; ClawHub
   reuse terms in §3. No mass scraping of an unprobed source without user sign-off.
4. **Statistics:** length is always a covariate; multiple-comparison correction always; effect
   sizes with CIs.
5. **Determinism:** Timbro-side extraction never calls an LLM or the network.
6. **Money:** any step that spends (API runs, licenses) needs explicit user approval first.
7. **When a spec here conflicts with reality** (dataset schema changed, endpoint gone, count
   differs wildly): stop, write down the discrepancy, ask the user. Do not silently substitute.

## 6. Risks

- **Novelty race:** Ling et al.'s group could add a linguistic layer. Mitigation: workshop
  paper as flag-plant; move WS1–WS3 fast.
- **Adoption-signal weakness:** stars are repo-level; skills.sh unprobed. If skills.sh falls
  through, RQ2 leans on ClawHub downloads (n=549) + repo-level models — still publishable,
  smaller claims.
- **Restyling validity (WS4):** "content-preserving" is the load-bearing assumption; Timbro
  profile checks + a manual audit of a sample are the control.
- **ARR Oct date unconfirmed** — re-check aclrollingreview.org/dates in August.

## 7. State snapshot (2026-07-04)

- Branch `paper` created. This file is the master plan.
- ClawHub 549-entry feed snapshot + sample SKILL.md fetch saved in session scratchpad
  (`clawhub_research/feed_skills.json`) — transient; WS1 step 3 re-fetches fresh.
- Subagent verification reports (citations, datasets, ClawHub) summarized into §2–§3; the
  underlying facts were empirically checked, not assumed.
- Next actions: (1) probe skills.sh (WS1 open sub-task); (2) file WS2 Issue A on GitHub;
  (3) watch NeurIPS workshop list Jul 11.
