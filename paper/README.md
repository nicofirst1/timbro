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
classification from these features (prompt-datasets study; arXiv:2510.09316).

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

**Amendment 2026-07-07:** `paper/literature.md` is now the authoritative verified-source
registry (~76+ papers, each independently verified before status "fully read"); the whitelist
below remains the core positioning set.

PromptPrism (arXiv:2505.12592, Findings of EACL 2026) · prompt-datasets study
(arXiv:2510.09316) · Ling et al. (arXiv:2602.08004) · Cho et al. (arXiv:2601.10809) ·
ClawGym (arXiv:2604.26904; note: 13.5K tasks are *training* data, eval bench = 200 instances) ·
SWE-World (arXiv:2602.03419) · Harbor (github.com/laude-institute/harbor, Terminal-Bench team) ·
olmo-eval (Ai2, June 2026) · Graph of Skills (arXiv:2604.05333) ·
"Prompting in the Wild" (arXiv:2412.17298, MSR 2025) · PromptSet.

**Promoted to whitelist 2026-07-07** (from `literature.md`, fully read/verified):
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
  pipeline (see §8 amendment).

**✓ RESOLVED — NO OVERLAP (verified 2026-07-07, fetch-and-quote against arXiv):**
`skillstructure2026` (arXiv:2604.24026, "From Skill Text to Skill Structure: The
Scheduling-Structural-Logical Representation for Agent Skills") — formerly flagged as the
largest unresolved novelty risk — converts skill text into a structured SSL representation via
an LLM normalizer and evaluates representation quality (Skill Discovery MRR@50 0.649→0.729;
Risk Assessment macro F1 0.409→0.509). No linguistic feature measurement, no adoption metrics.
Bonus: its abstract line — skills are "text-heavy artifacts... whose machine-usable evidence
remains embedded largely in natural-language descriptions" — is usable as motivation for our
linguistic lens.

**Known-fabricated (never cite):** "Prompts in the Wild" (ACL, 57.5K-prompt ontology study) —
does not exist; it was hallucinated in the original deep-research report.

## 3. Corpus facts (empirically probed 2026-07-04)

| Source | What it is | Unique full-text skills | Outcome proxies | License |
|---|---|---|---|---|
| HF `shl0ms/skill-diffs` | Full SKILL.md snapshots per commit, 5,891 GitHub repos, 4 platforms | **~630K–665K** (use `bundled` config or latest `after_content` per `skill_id`) | repo `stars`, dates, `intent_class`, `quality_score`; **no installs** | per-record `license_spdx` — filter per row |
| HF `davidliuk/graph-of-skills-data` | Paper-curated benchmark libraries (`skills_2000.tar.gz` is the superset). **Provenance confirmed artifact (verified 2026-07-07, MIT):** the HF dataset card reciprocally cites arXiv:2604.05333 (Dawei Liu et al.), the paper's GitHub repo links the dataset; skill-library configs 200–2000 | 2,000 (substantive, ~6KB avg) | none | MIT |
| ClawHub live registry | Sanctioned API: `GET https://clawhub.ai/v1/feeds/skills` (all 549, one request, robots.txt-allowed) + per skill `GET /api/v1/skills/{slug}/file?path=SKILL.md`; rate limit 3000 reads/min; authenticated `/api/v1/skills/export` ZIP exists. **Reconciliation note 2026-07-07:** hu2026-clawhub's 26,502 is a March 2026 crawl (up to 2026-03-18); live ClawHub as of July 2026 is ~549 — plausibly explained by a post-ClawHavoc purge (>30% of hu's crawl flagged suspicious/malicious; the SoK paper documents ClawHavoc, ~1,200 malicious skills). Plausible-not-confirmed — reconcile explicitly in the manuscript | **549** (small!) | catalog sortable by `downloads` — skill-level adoption signal | must cache, honor 429, link back to canonical pages |
| HF `amoghacloud/clawskills-intelligence-corpus` | 5,147 near-identical templated stubs ("SISR" boilerplate, ~400B each) | ~5.1K **low-quality stubs** | none | MIT |
| skills.sh marketplace (probed 2026-07-04) | Ling et al.'s source. Public sitemaps enumerate **~20,000** skill URLs (`owner/repo/skill`). Detail pages (robots-allowed) embed JSON-LD with **total installs**, stars, first-seen date, security-audit verdicts + only a 466-char SKILL.md preview. Full text NOT available (API is Vercel-OIDC-gated and robots-disallowed — do not use it) | 0 full texts directly — **join installs onto skill-diffs texts via the owner/repo/skill path** | **skill-level total installs** (not per-platform; per-platform counts exist nowhere) | robots.txt allows pages/sitemaps; `/terms` unread — read it before the crawl |

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
- *(Added 2026-07-07)* Additional corpus-landscape datapoint for the narrative:
  liu2026-skillscanwild analyzed **31,132 skills across skills.rest + skillsmp.com** (Dec 2025
  crawl) — two further marketplaces not currently among our corpus sources.

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

7. `build_skillssh.py` (probe done 2026-07-04 — recipe fixed): read `/terms` FIRST and stop if
   it forbids crawling. Then fetch `/sitemap.xml` → the two `sitemap-skills-*.xml` shards
   (~20,000 URLs), crawl each detail page at ≤2 req/s with an identifying User-Agent + contact
   email (~3h), parse the JSON-LD block (`userInteractionCount` = installs) + stars +
   first-seen + audit verdicts. **Never call `skills.sh/api/*`** (OIDC-gated and
   robots-disallowed). Output `paper/data/skillssh_meta.parquet` keyed on `owner/repo/skill`;
   join installs onto skill-diffs full texts by that key (normalize case; report join rate).
   This join is the primary RQ2 outcome. Cache raw HTML locally so the crawl never reruns.

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

**Update 2026-07-07 — WS2 tooling implemented.** GitHub issues #17 (`timbro analyze`
library-backed feature vectors) and #18 (custom extractors: imperatives, cohesion overlap,
`dict_*`/`coh_*` lexicon densities) were closed as completed 2026-07-06. Verified on `main`:
`src/timbro/analyze.py` and `src/timbro/lexicons/` (boosters, conditional connectives, hedges,
negations) exist (merge b54ba3a). Note: not yet present on the `paper` branch checkout — the
branch predates the merge; WS3 runs against `main`'s Timbro.

## 8. WS3 pre-registered analysis rules (BINDING — decided while capable-model access existed)

Every reported number follows the **`experiment-discipline` skill**: produced by a committed
script with a logged run manifest (git commit, data hash, seed). Seeds are always 42.

**Confirmatory feature family (5 + covariate):** `dict_imperative_ratio`, `dict_hedge_per_1k`,
`read_flesch_kincaid_grade`, `syn_mean_tree_depth`, `coh_lemma_overlap_adj`; `log(desc_tokens)`
is always a covariate, never a hypothesis. Everything else is exploratory and must be labeled
exploratory in the paper.
**Confirmatory outcomes:** ClawHub `downloads`; skills.sh installs (if the probe succeeds);
GitHub stars **only** on single-skill repos.

Decision rules — follow literally, log any trigger in `paper/analysis/DEVIATIONS.md`:
- **D1 dedup:** if near-dup removal cuts skill-diffs by >60% (fork explosion), the unit of
  analysis becomes the near-dup cluster: one canonical doc + `cluster_size` as covariate.
  Never treat near-duplicates as independent observations.
- **D2 scale:** descriptives on the full canonical corpus; regressions/clustering on a
  platform-stratified 50K sample if the corpus exceeds 100K docs.
- **D3 clustering:** HDBSCAN (`min_cluster_size=200`) on PCA components covering 90% variance.
  If noise >50% or <3 clusters → k-means, k ∈ {4..12} by silhouette. If best silhouette <0.10 →
  declare "no discrete dialects" and report the top-5 PCA axes as continuous dimensions instead.
  That outcome is a finding, not a failure — do not keep re-clustering until something appears.
- **D4 platform confound:** if cluster↔platform Cramér's V >0.6, re-cluster within each
  platform and report both views.
- **D5 slop check:** organic-vs-stub logistic AUC. If AUC >0.99, run drop-one-feature ablation
  and report the ablated AUC alongside (template-leakage guard).
- **D6 adoption:** Benjamini–Hochberg at q=0.10 over the 5 confirmatory features only. If
  nothing survives → report the null with minimum detectable effect. No promoting exploratory
  hits to headline claims.
- **D7 spec/reality conflict** (schema changed, counts wildly off, endpoint gone): stop, log
  the discrepancy, ask the user. Do not silently substitute.

### §8 amendment (2026-07-07 — pre-registration amendment; analysis has not run. D1–D7 and the confirmatory family above are unchanged)

- **Construct-validity citations per confirmatory feature** (from
  `paper/lit_review_psycholinguistics.md`): `dict_imperative_ratio` ← Vander Linden &
  Di Eugenio 1996 (COLING-96, imperatives in instructional text); `dict_hedge_per_1k` ←
  Hyland 1998/2005; `read_flesch_kincaid_grade` ← Kincaid et al. 1975 (Bailin & Grafstein 2001
  critique motivates pairing with `syn_*`/`coh_*`); `syn_mean_tree_depth` ← Gibson 1998
  (Dependency Locality Theory) + Lu 2010; `coh_lemma_overlap_adj` ← Grosz/Joshi/Weinstein 1995
  (Centering) + Barzilay & Lapata 2008 (entity grid).
- **New exploratory covariate (explicitly NOT confirmatory):** description-field
  completeness/quality — the practitioner review (`paper/lit_review_practitioner.md` §6) argues
  the `description` frontmatter field is its own activation mechanic, distinct from body-prose
  linguistic features. Exploratory only; labeled exploratory in the paper.
- **WS3 method framing:** Biber's Multidimensional Analysis (Biber 1988; Biber & Egbert 2018 at
  web scale, with how-to/instructional pages as a register category) is the direct
  methodological precedent for the standardize→PCA→cluster→name-by-deviant-features pipeline —
  "established method, new corpus."

## 9. WS4 pilot — full spec (mechanical once WS3 clusters exist)

**Compute:** open-weights coder model served with vLLM on the Fraunhofer **NM-BAIOS k8s
cluster** (use the `nm-baios-gpu` skill; Job template on wiki page
[[nm-baios-gpu-batch-jobs]]). The eval harness runs on the local machine (on VPN) against the
served endpoint — GPU time, not API dollars. User approves the GPU-time plan before any runs.

**Design (frozen before first run; amended 2026-07-07 — the spec was not yet frozen, so these
are legitimate pre-registration amendments, motivated by the lit-review synthesis in
`paper/literature.md` / `paper/lit_review_practitioner.md`):**
- **Tasks:** 24 from the ClawGym eval bench (stratified by gating type) if the OpenClaw harness
  is workable; fallback: Terminal-Bench 2.0 via Harbor, skill matched to task by keyword. Task
  list committed to `paper/pilot/tasks.json` before any execution.
- **Conditions (amended 2026-07-07):** 5 per task — **condition 0: no-skill control** (task run
  with no skill loaded; motivation: liu2026-skillsvote — **abstract-level support only**: the
  verified abstract says "indiscriminate updates can pollute future context," but the full text
  was unreachable (ar5iv 404, Semantic Scholar rate-limited) so the "actively hurts" effect
  size is unverified as of 2026-07-07; the control arm is also motivated by li2026-skillsbench's
  length findings and standard design practice), the original skill, + 3 restylings targeting
  the 3 largest WS3 clusters (generate all 3 even if the original already sits in one; that
  measures restyle noise).
- **Restyling protocol:** fixed per-cluster prompt templates in `paper/pilot/prompts/`; any
  strong LLM may generate. Acceptance gates, all mandatory, max 3 attempts then drop the task
  and log it: (a) code blocks, commands, file paths, and frontmatter **byte-identical** to the
  original; (b) `timbro analyze` places the variant within 1.0 z of the target-cluster centroid
  on the 5 confirmatory features; (c) human audit of a 20% random sample of accepted variants;
  (d) *(added 2026-07-07)* the restyle acceptance report includes the **token-length delta of
  each variant vs. the original**, carried as a covariate in the analysis (motivation:
  li2026-skillsbench, numbers verified verbatim 2026-07-07 — "compact and standard-length
  Skills (+19.0 and +21.5 pp) outperform detailed (+14.5 pp) and comprehensive documentation
  (+0.7 pp)"; the cliff is specifically at *comprehensive*; length alone is known to swing
  execution outcomes).
- **Runs (amended 2026-07-07):** 5 conditions × 24 tasks × 3 seeds = **360**, temperature 0.2.
  Per-run manifest: skill hash, prompt hash, model+quantization, seed, harness commit
  (experiment-discipline). *(Added 2026-07-07)* every run also logs **whether the skill was
  actually invoked/triggered**; success-conditional-on-invocation is a secondary outcome
  (motivation: contested ~56% non-invocation anecdote in the practitioner review — a restyled
  skill that never fires can't show a style effect).
- **Stats:** mixed-effects logistic `success ~ condition + (1|task)`; pairwise McNemar
  original-vs-each-variant; always report the MDE for this n. A null is publishable — report it
  straight.
- **Abort criteria:** restyle acceptance fails on >30% of tasks → stop and redesign the
  protocol; the verifier disagrees with itself on identical (condition, seed) reruns → fix the
  harness before generating any results.
- **RQ3 motivation (added 2026-07-07):** convergent, independently-mined evidence that
  more/redundant instruction context can hurt, not help, execution — Lost in the Middle
  (arXiv:2307.03172, TACL 2023, mid-context degradation), WebArena (removing the "Unachievable"
  hint *improved* GPT-4 success +2.71pp), SWE-bench (performance drops as context length grows),
  Agent Workflow Memory (NL+HTML combined *degrades* vs. NL alone), and SWE-agent
  (jimenez2024-sweagent: 2× success from interface/instruction wording alone, no model change).

### 9.1 NM-BAIOS constraints (from wiki, 2026-07-04)

- k8s 1.32 (not Slurm), namespace `nicolo`, context `nicolo@kubernetes`, **VPN required** (API
  is a private VIP). Plain batch `Job`, `restartPolicy: Never`, `backoffLimit: 0`.
- GPUs: full **H100 ~94GB** (`nvidia.com/gpu`) — contended, expect queueing; ~12× **A100 MIG
  2g.10gb slices** — usually free. A 32B model needs the H100; MIG slices fit only ≤7B at
  4-bit. Primary: 32B on H100. Fallback if H100 queue blocks: 14B-class AWQ on H100 off-hours,
  or a ~7B 4-bit on MIG (note the model change in the paper).
- **Hard cap `activeDeadlineSeconds: 21600` (6h) on every Job** — the vLLM server cannot run
  persistently. Chunk the 360 runs (288 pre-amendment; see §9 amendment 2026-07-07) into ≤6h
  batches; put `HF_HOME` on the home PVC
  (`home-nicolo`, RWX NFS) so each relaunch skips the model download (documented
  "whole evening lost" gotcha otherwise).
- **Endpoint exposure is undocumented ground**: no Service/Ingress pattern in the wiki. Try
  `kubectl port-forward` from the laptop first; if RBAC forbids it, run the harness driver
  inside the cluster (job-local batch shape) and pull results back with `kubectl cp`/stager-pod
  pattern. Resolve this BEFORE freezing the pilot design; it may force batch-shaped evaluation.
- Prebuilt pinned image in the GitLab registry (needs standing `read_registry` deploy token) —
  no `pip install` at container start. `PYTHONUNBUFFERED=1`. Pre-warm HF cache with one
  downloader before fan-out. Etiquette: leave "free − 1" MIG slices for others. Force-delete
  stuck pods (they hold the GPU). Jobs are immutable — delete-then-reapply.
