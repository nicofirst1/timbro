# Literature — full notes

**Instructions:** companion to `literature.md`. Only papers that need more than the summary in
`literature.md` get a section here (full method walkthroughs, extra figures/tables we want to
cite precisely, verbatim numbers). One `## <paper id>` section per paper, id must match the
`literature.md` table. Every section here must be linked from the corresponding paper's summary
in `literature.md` via `→ full notes: literature_full.md#<id>`.

## zhou2026

**Section 4 (Externalized Expertise: Skills) — detailed structure:**
- 4.1 What is externalized: operational procedures (decomposition/steps/dependencies/stopping
  conditions), decision heuristics (branching policies, trade-offs, fallbacks), normative
  constraints (safety boundaries, compliance, governance).
- 4.2 From execution primitives to capability packages: Stage 1 atomic execution (tool-calling),
  Stage 2 large-scale primitive selection (retrieval/ranking over tool collections), Stage 3
  skill as packaged expertise (reusable procedural organization + composition graph).
- 4.3 How skills are externalized: specification (SKILL.md/manifests: capability scope,
  preconditions, constraints, examples); discovery (registry/semantic retrieval, structured
  metadata, task decomposition, environment conditions); progressive disclosure (existence
  exposed first, detail on demand, matched to task complexity); execution binding (translation
  layer from spec to concrete tool/protocol operations; boundary conditions: portability,
  staleness, unsafe composition, context-dependent degradation); composition (parallel
  execution, conditional routing, recursive invocation).
- 4.4 Acquisition pathways: authored (human-designed, e.g. SKILL.md/AGENTS.md), distilled
  (extracted from episodic trajectories), discovered (autonomous exploration/self-verification),
  composed (combination of existing units, validated before packaging).

**References cited relevant to us:** Ling et al. (arXiv:2602.08004) is cited as the skills.sh
descriptive study. No prior work cited that measures linguistic features of skill documentation.

**Key distinction:** this paper treats skills as architectural objects (what to externalize, how
to package/discover/bind/compose). We treat skill files as linguistic documents with measurable
stylistic/syntactic features correlated with adoption and execution. Orthogonal axes.

## liang2026-skillnet

**Corpus & scale:** 200K+ curated skills; multi-source pipeline (execution trajectories, GitHub
repos, structured documents, natural-language prompts); pre-filtering + multi-stage quality
curation.

**Platforms compared (their Table 2):** SkillNet (full-lifecycle infra), ClawHub (npm-like
version management), SkillsMP (large open-source catalog), SkillHub (premium marketplace, LLM
rating), Skills.sh (community leaderboard, CLI-first).

**Evaluation dimensions (not linguistic):** Safety (hazardous ops, prompt-injection robustness),
Completeness (prerequisites/dependencies explicit), Executability (sandbox-verified), Maintainability
(modularity/composability), Cost-awareness (latency/compute). Quality grading: 3-level
(Good/OK/Poor); QWK ~1.0 human/LLM inter-rater agreement, MAE <0.03 on 200 sampled skills.

**Experimental results:** ALFWorld, WebShop, ScienceWorld; DeepSeek V3.2, Gemini 2.5 Pro, o4 Mini
backbones; baselines ReAct/Expel/Few-Shot. E.g. DeepSeek: 46.18 seen / 17.84 unseen reward with
SkillNet vs. 31.55 / 24.06 with Expel. +40% average reward, -30% interaction steps.

**Skill relation types:** similar_to, belong_to, compose_with, depend_on — used for skill-graph
composition/dependency resolution/workflow synthesis.

**Related-work positioning (theirs):** distinguishes from Ling et al. (arXiv:2602.08004,
structure/redundancy/taxonomy/risk, no linguistic features, no execution) and from Cho et al.
(arXiv:2601.10809, prompted style personas on chat replies, no measured features, no execution).
SkillNet itself avoids linguistic analysis entirely — focuses on functional quality and task
performance.

**Limitations acknowledged (theirs):** incomplete domain coverage; self-constructed skill quality
not fully guaranteed (safety eval can catch some poisoned skills but not all); no fully
instantiated end-to-end pipeline for all agent backbones yet.

## li2026-agentskillos

**Paper:** "Organizing, Orchestrating, and Benchmarking Agent Skills at Ecosystem Scale," Hao Li, Chunjiang Mu, Jianhao Chen, Siyue Ren, Zhiyao Cui, Yiqun Zhang, Lei Bai, Shuyue Hu (Shanghai Artificial Intelligence Laboratory), arXiv:2603.02176, GitHub: `ynulihao/AgentSkillOS`.

**Manage Skills (capability tree):** offline-constructed tree `T` over the skill ecosystem `S`. Root node fixed to 5 manually-specified categories (content creation, data processing, software development, automation, domain-specific) for stability; below that, breadth-first LLM-driven "group discovery" (generate category groups per node) + "skill assignment" (assign each skill in the node to a group) — split into two steps specifically to reduce missed skills vs. doing both at once. Special-case handling: categories with only 1 skill get merged into the nearest target category; categories at/above capacity threshold `C` get converted to leaves without further splitting; skills unassigned due to LLM hallucination get reassigned (falling back to the largest category if still unassigned after retry). Tree updates incrementally as new skills arrive (insert down existing path, then bottom-up refresh of node names/descriptions). A **usage-frequency queue** (ranked by marketplace install count) selects which skills actually get placed in the tree once `|S|` exceeds a threshold `K` — the rest go into a "dormant index" searchable by embedding similarity and promotable back in by the user.

**Solve Tasks (DAG orchestration):** two-stage per task — (i) task-driven retrieval: LLM traverses the capability tree layer-by-layer to shortlist candidate skills (plus vector search for skills outside the tree), then dedupes/ranks down to a compact top-M shortlist; (ii) DAG-based orchestration: LLM decomposes the task into subtasks, assigns each a skill from the shortlist, and organizes them into one of three DAG strategies — quality-first (adds refinement stages), efficiency-first (maximizes parallelism), simplicity-first (minimal DAG, every node necessary). Execution walks the DAG layer by layer (same-layer nodes run in parallel, cross-layer nodes are sequential); each node's execution prompt restates the task, names the skill, lists upstream artifacts with usage hints, and states expected outputs. A "recipe pool" caches full task→DAG plans keyed by task-description similarity so structurally similar future tasks can skip retrieval+orchestration entirely.

**Benchmark:** 30 human-expert-authored tasks across 5 categories (data computation, document creation, motion video, visual design, web interaction), each requiring a complete end-user-facing artifact (not just code/QA). Evaluated via **LLM-judge pairwise comparison in both orderings** (to cancel position bias) aggregated into a global win matrix, then a **Bradley–Terry model** fit by maximum likelihood to produce continuous per-system ranking scores — explicitly chosen over absolute LLM scoring for fine-grained differentiation and less bias.

**Key experimental result:** tested at 3 ecosystem scales (200/1K/200K skills). AgentSkillOS beats vanilla Claude Code skill invocation and a skill-free baseline at every scale. Ablation: giving vanilla Claude Code the *identical oracle skill set* AgentSkillOS uses still underperforms AgentSkillOS with DAG orchestration — i.e., the orchestration structure itself (not skill availability) is the main driver of the gain. Tree-based retrieval closely approximates oracle skill selection even at 200K scale.

**Relevance to Timbro:** zero linguistic-feature content — this is a retrieval/orchestration systems paper. Two reusable pieces for RQ3: the **Bradley–Terry-over-pairwise-judgments** scoring protocol (cleaner than raw LLM-judge scores if we want continuous, bias-corrected quality rankings for restyled-vs-original comparisons), and the explicit **position-bias mitigation** (judge both orderings) as a checklist item for any LLM-judged component of our pilot. Also worth citing alongside Ling et al. and SkillNet as one more "ecosystem-scale infrastructure" paper with zero linguistic-feature overlap, reinforcing the novelty gap.

## hu2026-clawhub

**Dataset & methodology:** 26,502 skills crawled from ClawHub (as of ~Jan 2026). Normalized into
5 fields: identity (slug/ID/owner), metadata (display name, summary, tags, timestamps), content
(docstrings, manifests, comments), risk (scan signals, labels), effectiveness (heuristic quality
score). Three-stage crawl: enumerate public skills → parallel per-skill metadata collection →
risk aggregation (VirusTotal-style scan + LLM-as-judge). Language split: 17,499 English, 3,882
Chinese (post quality-filter).

**Functional clustering:** TF-IDF + k-means (10 clusters/language) with truncated SVD;
silhouette-validated. English: infrastructure-modular (Developer Tools 36.3%, Search/Retrieval
9.1%, Productivity 9.1% — top 3 = 54.5%); tight, overlapping clusters from reusable module
coupling. Chinese: scenario-driven (media production, video generation, social ops, finance);
broader, more scenario-separated clusters. Quote: "English skills are more aligned with
capability modulization, whereas Chinese skills are more aligned with scenario-specific
packaging."

**Download/adoption signal:** log-normal-ish, modal range 30–60 downloads, <10% exceed 1,000 —
useful reference distribution for our own RQ2 outcome modeling.

**Risk detection:** 12 classifiers on submission-time signals (descriptions, docs, code, tags,
primary doc). Best: Logistic Regression, 40,910 features, 72.62% acc / 72.68% precision / 72.48%
recall / F1 78.95 / AUROC 78.95%. Ablation: removing `primary_doc` costs 0.22pp (most
informative feature); removing summary/full doc *increases* accuracy slightly (summary text adds
noise). Label mismatch: 6,530/6,666 scan-suspicious skills, only 1,840 LLM-confirmed; 10,381 null
labels (~39% unlabeled).

**Cross-ecosystem note:** paper cites Ling et al. as the comparable ecosystem study but notes
Ling focuses on structure/redundancy/taxonomy/risk without linguistic features — same gap we're
targeting, independently confirmed by a second group.

**Data limitations (theirs):** non-text/oversized files skipped during crawl; VT/LLM risk labels
are asymmetrically conservative in opposite directions; fine-grained risk categories severely
undersampled.

## ai2026

**Paper metadata:** Ai et al., ~6 pages, LLNL/Notre Dame; arXiv ID 2606.05525 implies June 2026.

**Skills evaluated:** ParaView (volume/isosurface extraction), VMD (molecular dynamics viz), TTK
(topological analysis of scalar fields), object identification (geometric/property reasoning).

**Benchmark (SciVisAgentBench):** 100 authored task steps (20/domain suite across 5 suites),
mixing deterministic code-generation tasks and visual-outcome tasks (rendered output vs.
ground-truth).

**Eval metrics:** pass@1, pass@[1,2,3], completion rate; LLM-judged binary correctness on code;
image-based PSNR/SSIM/LPIPS (mean±std over 3 repeated trials); token cost (input/output/cached)
as an efficiency proxy.

**Key results:** skills improve mean task scores across all 5 suites (gains range ~3%–60%
depending on suite/harness). Claude Code + skills costs more tokens than Codex + skills on
identical tasks (verbosity/harness interaction). Token usage correlates with caching strategy and
skill explicitness — more detailed skills raise input tokens but sometimes lower output tokens
(net efficiency gain). Gains are NOT uniform: molecular visualization benefits most, topology
least — and the paper explicitly notes gains shrink when the base model already handles a
well-documented tool well (foundation-model memorization reduces marginal skill value).

**Relevance to Timbro:** validates the general hypothesis that instruction content/style should
predict task success, but their intervention is functional (what procedural knowledge to
encode), not linguistic (how to phrase it) — complementary axis, not a competing claim on RQ1.
Their benchmark design (multi-metric, repeated-trial, deterministic + judged scoring) is directly
transplantable to the RQ3 pilot's task suite.

## gao2026

**Methodological details:**
- SWEBOK knowledge-area stratification (18 KAs); Software Construction is 6.2pp higher in
  centralized (skills.sh) vs. personal-use (GitHub) skills; similar drift in Architecture (+3.2
  vs. +1.9) and Security (+3.8 vs. +2.3).
- Linkage recovery: Longest Common Subsequence (LCS) on SKILL.md body, threshold ≥0.99
  (near-verbatim reuse), Cohen's κ = 0.82 inter-rater agreement on reuse classification.
- Content coding: 69 initial codes → 17 subthemes → 6 themes (scoping, execution lifecycle,
  output quality, agent conduct, domain grounding, user coordination); stratified sample of 15
  skills/KA (285 total); κ = 0.79 after disagreement resolution.
- Evolution tracking: per-skill commit history; customization frame (adoption→final diff) vs.
  evolution frame (initial→final body change); 621 linked pairs; edits skew additive (2.7:1
  additions:removals).
- Dataset retention: 5,876 repos (76,921 skills) after quality filters; keyword filtering removes
  collections/tutorials/forks; Tukey-fence (340-line max churn) suppresses outliers.

**Differentiation from Timbro:** categorical (SWEBOK KAs, edit-type taxonomy) vs. our linguistic/
syntactic features (imperative density, syntactic depth, cohesion, readability, POS/dep
distributions — all deterministic, not LLM-judged). They report no adoption metrics and no
execution outcomes; we target both directly.

**Positioning note for our related work:** cite alongside Ling et al. and Cho et al. under
"agent-skills ecosystem studies," emphasizing that prior work characterizes skill content via
structural categories and maintenance behavior, while we measure deterministic linguistic
features of instruction prose. Their SWEBOK stratification is a candidate subgroup-analysis axis;
their LCS linkage method is directly reusable for our reuse-tracing in RQ2.

## yang2026

**Key distinction:** measures execution outcomes from a federated-learning architecture, not from
linguistic analysis. Skill patches are structured semantic operations (ADD/EDIT/DELETE over
existing skills, capability-matrix + two-level memory guiding evolution), not prose rewrites.

**Methodological overlap with RQ3:** does measure task success under system-architecture
variation (homogeneous/heterogeneous backbones: Qwen, GLM-5, Kimi CLI) — same *kind* of
measurement RQ3 needs, but the independent variable is architecture, not linguistic restyling.

**Numbers:** +44.4% success-rate improvement, -37.5% cost vs. self-evolution baselines on
SkillFlow (20 task families, from Zhang et al. 2026d — a benchmark shared with our context).
Privacy audit: Sensitive Entity Leakage Rate (SELR) framework, 0.09% leakage after personalized
update absorption; ~3.5MB total patch payloads vs. gigabytes under parametric federated learning.

**Related-work silo note:** cites a dense cluster of 2026 skill-evolution papers (Ma et al.,
Zheng et al. 2026b, Xia et al., Shi et al., Liu et al. 2026, Wang et al. 2025, Ouyang et al., Yao
et al.) but does NOT cite Ling et al., and is not cited by Ling et al. — confirms this is a
parallel silo (architectural/federated) to the linguistic-topology silo we're building.

## zhang2026

**Skill definition:** tuple (name, description, body) — same schema shape as our instruction
documents; SkillComposer focuses on refining the body via three learnable ops.

**Create/merge/improve mechanics:** multi-view similarity (Eq. 1) merges across embedding
dimensions, threshold δ=0.8 for merge candidates. Delta-pass-rate rejection sampling filters
training examples where pass@k improves by ≥ τ (0.4 for create/merge/improve).

**Benchmarks:** τ²-Bench (Retail/Airline/Telecom, 3-turn interactions), LiveCodeBench v6
(Easy/Medium/Hard), AppWorld (OOD generalization). +4.5/+3.4 over baselines.

**Cross-model generalization:** skills composed by Qwen3.5-4B generalize to a 27B model (+4.5 on
τ²-Bench) — skill quality appears largely model-agnostic in their setup.

**Gap we should note explicitly:** they do NOT test cross-*ecosystem* generalization (Claude
Code / OpenClaw / OpenCode / Hermes) — exactly the axis our RQ1 targets. Their merge step uses
embedding similarity, not linguistic features — worth floating in our discussion whether
high-quality merged skills also share linguistic properties (untested by them, open question for
us).

**Corpus overlap risk:** their offline library uses OpenCodeReasoning (500 samples) — possible
overlap territory with our HF skill-diffs corpus in the OpenCoder domain; worth a dedup check if
we ever pull from OpenCodeReasoning-adjacent sources.

## li-skillhone

**Architecture:** role-separated — optimization side (Proposer, Explorer, Developer, Reviewer,
Decider) works on the skill repository; evaluation side (Executor, Analyzer, Reporter, Auditor)
works on a *separate* skill-evaluation repository (practice probes, validators, traces, redacted
reports). Prevents evaluation-side leakage into optimization.

**Decision record:** each step recorded as `h_t = (q_t, r_t, e_t, o_t)` — diagnosis, candidate
revision, redacted evaluation evidence, outcome — a persistent audit trail so later agents don't
re-derive old decisions.

**Numbers:** GAIA 64.6%, WebWalkerQA-EN 66.4%; +14.2/+13.4 over Skill-Creator baseline, +20.5/
+28.3 over Hermes-SE. Deployment study across 7 recurring tool-mediated scenarios: +18.8pt
average accuracy. Transfers to Claude Sonnet 4.6 without further optimization: 72.4% GAIA
(evidence gains are skill-procedure improvements, not model-overfitting).

**Skill sourcing:** ClawHub/SkillHub community pools (web-pilot, web-content-fetcher,
scholar-search, query-dbpedia, multi-search-engine, literature-review, deep-research-pro,
ddgs-search, etc.) — potential corpus overlap with our own ClawHub-sourced data.

**Direct design lesson for RQ3:** the optimization/evaluation role separation is exactly the
discipline our pilot needs — Timbro's dogfooding verification (does the restyled variant land in
the target cluster?) should be architecturally separated from whatever produces the restyled
variants, mirroring their leakage-prevention design.

## liu2026-skillsvote

**Paper:** "SkillsVote: Lifecycle Governance of Agent Skills from Collection, Recommendation to Evolution," Hongyi Liu, Haoyan Yang, Tao Jiang, Bo Tang, Feiyu Xiong, Yuyu Luo, Zhiyu Li (MemTensor (Shanghai) Technology / Harbin Institute of Technology / Soochow University / HKUST-GZ), arXiv:2605.18401, June 2026. Site: skills.vote, GitHub: `MemTensor/skills-vote`.

**Corpus:** profiles a **million-scale open-source Agent Skills corpus** for format, dependency, quality, and verifiability — collection/profiling details in their Appendix D.1 (not extracted here; worth a follow-up read if we need corpus-construction specifics at that scale).

**Pre-task recommendation (agentic library search, not static semantic matching):** given a task and a skill library, a separate recommendation stage searches the local library, selectively reads candidate SKILL.md files, and selects a small covering set of skills plus a short usage guide — rather than exposing the full library or a fixed top-k chunk list. Motivated by the same progressive-disclosure idea as Claude Skills, but adds an explicit exposure-control layer *conditioned on the task* before the solver agent ever starts.

**Post-task attribution (subtask-level, the paper's core methodological contribution):** raw trajectories are split into **subtasks** — the smallest semantically complete unit that can support library evolution, defined as having *one standalone objective, one primary evaluation signal, and at most one associated skill context*. Trajectories are only split where one of those three boundaries changes, not at every tool call. For each subtask, attribution records: (1) outcome evidence — objective environment feedback vs. human preference vs. no explicit signal (kept separate so these aren't treated as equally trustworthy); (2) responsibility assignment — success/failure attributed to skill-guided execution, independent exploration, or exploration-after-observing-an-irrelevant-skill; (3) reusable delta — only the portion of skill knowledge that actually shaped execution (missing procedures/preconditions/recovery patterns), explicitly discarding ordinary trial-and-error and task-specific constants.

**Evidence-gated evolution:** admissibility (only successful subtasks with reusable exploration may trigger a library update — failed/uncertain subtasks are kept for diagnosis but can't authorize a change) → aggregation (evidence supporting the same procedure/precondition/correction gets merged into one proposed update, not duplicate edits) → routing (extend an existing skill via smallest justified change / create a new skill / skip if evidence is weak or misaligned). Explicitly designed to be conservative — every library change must be evidence-backed and localized.

**Experiments:** Harbor-based, Terminal-Bench 2.0 (avg@5 accuracy) and SWE-Bench Pro public (avg@1 resolve rate), 3 Codex configs (GPT-5.2 medium, GPT-5.4 mini medium, GPT-5.5 xhigh). Online (SkillsVote evolves an empty library live at test time) beats ReasoningBank and a naive skill-creator baseline in most configs and is more stable across difficulty splits (baselines regress at GPT-5.5 while SkillsVote still gains). Offline transfer: a library evolved from historical Terminal-Bench Pro trajectories gives the strongest Terminal-Bench 2.0 transfer (+1.4 to +7.8pp depending on backbone) — beating a frozen library of 10K curated open-source skills in most configs, meaning trajectory-derived skills generalize better than curated ones here. **Recommendation-vs-no-recommendation ablation (Fig. 5) is the most quotable number for us:** directly exposing the online library without recommendation yields mean task-level contribution of +3.3 gain / -6.7 loss (net negative); adding recommendation balances this to +6.0/-6.0 — i.e., unfiltered skill exposure actively hurts on Terminal-Bench Hard tasks, recommendation is what fixes it.

**Relevance to Timbro:** no linguistic features, no instruction-dialect framing. Two reusable ideas for RQ3: (1) the **subtask-attribution unit** (one objective/one signal/one skill) is a cleaner way to isolate what to credit than scoring whole-task success when comparing a restyled skill variant against the original; (2) the **recommendation ablation result is direct evidence that irrelevant/weak skill exposure can make things worse, not just fail to help** — a concrete argument for including a no-skill control condition in the RQ3 pilot design (§9 of the plan currently has 4 conditions: original + 3 restylings; consider whether a 5th no-skill baseline is worth the extra runs). Cites Ling et al. directly as reference [29] for ecosystem framing.

## preprints202605-1276

**Paper:** "A Survey of Agent Skills: Toward Procedural Infrastructure for LLM Agents," Cehao Yang, Xiaojun Wu, Honghao Liu, Xueyuan Lin, Chengjin Xu, Xuhui Jiang, Yuanliang Sun, Wenjie Zhang, Zhichao Shi, Yijie Xu, Jia Li, Hui Xiong, Jian Guo. preprints.org/manuscript/202605.1276.

**Six-layer taxonomy:** ontology (conceptual status, knowledge compression) → representation (natural-language guidance, code snippets, decision graphs, filesystem packages, structured records) → lifecycle (acquisition from trajectories/external sources; storage via flat/hierarchical/tree/graph-structured libraries; retrieval and composition; usage/execution; maintenance/refinement/deprecation; internalization) → runtime integration (terminal/tool interfaces, multi-agent systems, agent harnesses) → governance (security, risk, trust) → applications (robotics, games, web, GUI/OS agents, software engineering).

**Formalization:** skill S = (C, P, R, E) — approximately condition/procedure/resource/effect, per the confirmed-reading pass (exact term definitions not re-extracted here — check the PDF directly before citing the formalism verbatim).

**Table 2 (skill refinement mechanisms):** surveys 11 recent frameworks — SkillTracer, MCE, Skill-Pro, MemSkill, EvoSkill, Memento-Skills, D2Skill, CoEvSkills, SkillClaw, SkillForge (plus one more not captured in the read-through).

**Acquisition regimes:** success-driven, contrastive, exploration-driven. **Storage paradigms:** flat vs. hierarchical vs. tree vs. graph-structured.

**Relevance to Timbro:** strongest RQ1 conceptual scaffolding among the previously-unread batch — explicitly treats representation as a first-class dimension across ecosystems (Claude Code, Codex, OpenClaw, Hermes, etc.), close in spirit to our "instruction dialect" framing, but stops at taxonomy — no measured linguistic features, no clustering, no execution data.

## preprints202604-1817

**Paper:** "A Survey of Agent Skills for Foundation-Model Agents: Concepts, Representations, Lifecycles, Evaluation, and Applications," Jinhao Shen, Huahui Yi, Wentao Hu, Yiyang Jiang, Wengyu Zhang, Xiao-Yong Wei, Qing Li. preprints.org/manuscript/202604.1817. Posted 2026-05-15, not peer-reviewed. Public curated paper list: github.com/JinhaoShen/awesome-agent-skill-papers.

**Formalization:** skill σ = (Cσ, Πσ, Tσ, Iσ) — applicability conditions, internal procedure, termination criterion, callable interface.

**Five-dimension structure:** representation (textual/programmatic/hybrid — §3.2, directly aligned with our instruction-dialect thesis), functional scope/level of abstraction, acquisition source, retrieval visibility, lifecycle (discovery → practice/distillation → storage → composition → evaluation → update).

**Figure 1:** maps the skill ecosystem as Acquisition → Deployment/Evolution → Orchestration → Security, with a "Concepts Comparison" layer distinguishing skills from tools/prompts/policies/memory/harness.

**Related work cited:** lists Ling et al.'s "Agent Skills: A Data-Driven Analysis of Claude Skills" directly as a concrete ecosystem example — confirms this survey's authors are aware of our closest novelty competitor.

**Relevance to Timbro:** grounds the representation-dimension argument for RQ1 but is purely organizing/taxonomic — no linguistic feature extraction, no statistical clustering, no execution-outcome measurement.

## openreview-fNXXsp9iub

**Paper:** "They Are Not Static: A Survey of Dynamic Agent Skills," Yubo Li (Carnegie Mellon University). openreview.net/pdf?id=fNXXsp9iub. 94-paper corpus frozen 2026-04-24.

**7-tuple lifecycle model:** evidence acquisition, proposal, verification, admission, storage, retrieval, maintenance, governance.

**Eight architectural families; master coding sheet:** 82 representative systems coded on operator vocabulary, infrastructure topology, pipeline architecture, verification form. Ten core operators recur across all 82 systems: ADD, REFINE, MERGE, SPLIT, PRUNE, DISTILL, ABSTRACT, COMPOSE, REWRITE, RERANK.

**Evidence-graded patterns** (grade reflects strength of causal support — A = multiple ablations or one clean ablation + corroboration, B = one controlled study or strong benchmark, C = convergent behavior without a clean causal ablation, D = architectural only):
- R1: admission gates drop skill-verification failures 71%→41%.
- R2: verifier quality decisively affects RL adoption.
- R3: flat retrieval scales sublinearly / drops at moderate scale under realistic distractor loads.
- R4: maintenance is load-bearing — ablations show 4.5× utilization gains as skill count grows from 28→126 units.
- R5: write-time abstraction beats read-time abstraction.

**Eight safety surfaces:** prompt injection, supply-chain poisoning, credential leakage, ownership/theft, attribution — each with per-stage quantitative anchors (ASR, DDIPE, credential-leakage metrics) and a proposed 5-item reporting checklist for dynamic-skill papers.

**Two-timescale modes:** fast loop (inline edit, shared-artifact, or SKILL.md+case) vs. slow loop (adapter tuning, policy weight updates, RL steps, teacher signal).

**Relevance to Timbro:** architectural/structural only — no linguistic feature extraction, no execution-outcome measurement tied to prose. But its evidence-grading scheme (A/B/C/D) is a reusable rigor template for how we grade our own RQ3 causal claims, and the "SKILL.md+case" fast-loop mode is a direct precedent for the file format we study.

## cho2026

**Paper:** "A Concise Agent is Less Expert: Revealing Side Effects of Using Style Features on Conversational Agents," Young-Min Cho, Yuan Yuan, Sharath Chandra Guntuku, Lyle Ungar. arXiv:2601.10809, Jan 2026, cs.CL.

**Why this paper matters more than any other in the tracker:** it is the README's second explicitly named novelty competitor ("Cho et al."), and getting the differentiation exactly right is load-bearing for the whole paper's positioning, not just a background citation.

**Setup:** surveys 127 ACL Anthology papers to enumerate 12 commonly-used conversational-agent style features (e.g. friendly, helpful, concise, formal, empathetic — the paper's own taxonomy of what NLP researchers already treat as controllable "style knobs" for dialogue agents). Constructs controlled synthetic dialogues in two settings — task-oriented and open-domain — where an LLM is prompted with an instruction to *adopt* one style feature at a time (e.g. "respond concisely"). A separate LLM acts as judge, doing **pairwise comparison** between the steered response and a baseline/other-styled response, rating perceived levels of all 12 style features (not just the one that was targeted). Introduces the **CASSE** dataset (the synthetic dialogues + pairwise judgments) as a released artifact. Also tests activation-steering (representation-level intervention rather than prompt-level instruction) as an alternative mechanism and as a potential mitigation for unwanted entanglement.

**Headline finding:** style features are "deeply entangled rather than orthogonal" — prompting for one feature measurably shifts the perceived level of others, in directions researchers don't intend. The flagship example: instructing an agent to be concise significantly *reduces* its perceived expertise, even though nothing about the agent's actual knowledge or correctness changed — only its phrasing was steered. This is presented as a warning for anyone treating style dimensions as independently adjustable in agent design.

**What is NOT measured:** no linguistic feature is extracted or computed directly from text (no POS distributions, no readability score, no hedge-word count) — "style" here is entirely the *label the researchers assigned via the steering prompt*, and the outcome variable is entirely the *label an LLM judge assigns via subjective pairwise comparison*. There is no real task execution anywhere in the pipeline — no agent actually completes a task and succeeds or fails; "expertise" and other traits are perceived qualities judged from the surface of a chat reply, not verified capabilities. The object of study is conversational chat replies (task-oriented and open-domain dialogue), not instruction/skill documents that an agent reads to guide its own behavior.

**Precise three-way differentiation to use in the manuscript (do not blur these into one blanket "different topic" statement):**
1. *Measured vs. prompted/steered.* Cho's style variable is an instruction given to the model being studied and confirmed post-hoc by an LLM judge; our style variables (`dict_imperative_ratio`, `dict_hedge_per_1k`, `read_flesch_kincaid_grade`, `syn_mean_tree_depth`, `coh_lemma_overlap_adj`, plus the full `posdep_*`/`lex_*`/`struct_*` groups) are computed deterministically from existing, unmodified text via spaCy/regex/counting — nothing is prompted into existence.
2. *Execution vs. perception.* Cho's dependent variable is subjective LLM-judged perceived quality of a chat turn; ours are adoption proxies (RQ2: installs/downloads/stars) and real agent task-success rate under a deterministic verifier (RQ3).
3. *Instruction documents vs. conversational replies.* Cho studies what an agent *says* in a conversation; we study what an agent *reads* (a SKILL.md/instruction file) before acting.

**Direct methodological debt we owe this paper regardless of the competitive framing:** Cho's core empirical result — that steering one linguistic/stylistic dimension moves perception of a *different, unrelated* dimension — is exactly the mechanism that would produce a spurious effect in our own RQ1–RQ3 if we don't control for length. This is the stated origin of the ADR-0002 rule "raw length must be a covariate everywhere." If an unmeasured, correlated stylistic trait can flip perceived expertise in Cho's setup, an unmeasured length confound could just as easily flip an apparent adoption or execution effect in ours — cite Cho directly wherever that covariate choice is justified in the manuscript, not just in the related-work section.

## jeoung2026-promptprism

**Paper:** "PromptPrism: A Linguistically-Inspired Taxonomy for Prompts," Sullam Jeoung, Yueyan Chen, Yi Zhang, Shuai Wang, Haibo Ding, Lin Lee Cheong. arXiv:2505.12592. Published as Findings of ACL: EACL 2026 (ACL Anthology entry 2026.findings-eacl.61, pp. 1168–1192 per the anthology listing; page range not independently re-confirmed from the arXiv abstract itself).

**Three-level taxonomy:** functional structure (the role each prompt component plays — e.g. instruction, context, constraint, example), semantic component (meaning/content relationships between those components), syntactic pattern (structural/grammatical arrangement of the prompt text). This is explicitly a *taxonomy* for classifying and organizing prompts along these three axes, not a feature-extraction toolkit that outputs numeric vectors, and not a released linguistic-feature dataset.

**Three demonstrated applications:** (1) automated prompt refinement — using the taxonomy to guide systematic rewriting; (2) dataset profiling — extracting structural/semantic/syntactic characteristics across a collection of prompts to characterize a dataset's composition; (3) sensitivity analysis — testing how semantic reordering or delimiter changes affect downstream LLM performance.

**GAP RESOLVED (full text read via arXiv HTML rendering, https://arxiv.org/html/2505.12592, cross-checked against the ACL Anthology entry 2026.findings-eacl.61).** The earlier "access blocked" note is superseded. The overlap question is now answered as a **confirmed non-overlap**. Details below.

**What the "syntactic pattern" level actually covers (the crux of the gap):** it is *structural/formatting* markup, not linguistic parse structure. Its categories are:
- *Component indexing* — `(Role, Index)` position identifiers — and *component span analysis* — `(start_pos, end_pos)` boundary markers.
- *Directive markers*: **prefix patterns** (hash comments `#`, double-slash comments `//`, blockquotes `>`, numbered lists `1.`/`2.`, bullet points `-`/`*`/`+`); **suffix patterns** (colon endings `:`, sentence terminators `.!?`, semicolons).
- *Delimiters*: double newline, single newline, tab, whitespace.
- *Special tokens*: model-specific markers (e.g. Llama's `<|begin_of_text|>`).

It computes **no** POS distributions, **no** dependency distances, **no** parse-tree depth, and **no** clausal-embedding counts. This means **zero overlap** with our `syn_*` (dependency distance, parse-tree depth, clausal-embedding depth of `ccomp/xcomp/advcl/acl/relcl`) and **zero overlap** with our `posdep_*` (62-d POS-tag + dependency-label relative-frequency vector — that construct belongs to `zhang2025-promptdatasets`/arXiv:2510.09316, a different paper, not this one).

**Dataset-profiling metrics (checked precisely against our groups):** the profiling application aggregates, per prompt/dataset — *structural*: turn type (single/multi-turn), prompt pattern (role-sequence analysis), unique structural roles; *semantic*: component frequency analysis, plus **mean taxonomic tree width and mean tree depth**; *syntactic*: component indices, spans, delimiters, directive markers; *metadata*: task type, language specification, token length, modality. Critical clarification on the one metric whose *name* looks like ours: the "tree width / tree depth" is the width/depth of **PromptPrism's own component-taxonomy tree** (how prompt components nest under the Instruction / Context / Output-Constraint / etc. hierarchy), **not** a spaCy dependency parse-tree depth of the sentences. It is a name collision, not a feature match. None of the profiling metrics match our `lex_*` (MTLD/HDD, wordfreq rarity) — the paper computes no type-token ratio, MTLD, HDD, or word-frequency/vocabulary-richness measure anywhere.

**Imperatives / hedges / boosters (the precise checkable question):** absent. The paper does **not** perform imperative-sentence detection, does **not** measure hedging or certainty/booster language, and does **not** use anything resembling Hyland's hedge/booster lists. None of our `dict_*` group (imperative ratio, hedges, boosters, negation, conditional/logical connectives) is present.

**Outcome experiments:** there is **no** outcome-prediction experiment in the adoption or real-task-execution sense. The three applications and their metrics are: (1) *taxonomy-guided prompt refinement* — evaluated with ROUGE-L (an LLM-response-quality proxy), reporting an average 29% improvement on text-generation tasks over a Chain-of-Thought baseline in the two-shot setting; (2) *dataset profiling* — evaluated only with human-annotation validation metrics (format correctness 0.99, tag correctness 1.0, coverage 0.98 on apigen-80k); (3) *prompt sensitivity analysis* — tests how *semantic-component reordering* (first/middle/last positions for Instruction, Question, Few-shot) and *delimiter modifications* shift LLM performance, with significance via ANOVA (p<0.05). All three are LLM-response-quality proxies; none is an adoption proxy (installs/downloads/stars) and none is a real agent-execution/task-success outcome. (Note: PromptPrism reports **no** F1/Macro-F1/AUC classification numbers — the F1=0.90 / Macro-F1=0.975 / AUC=0.792 figures in our tracker belong to `zhang2025-promptdatasets`, not to this paper; the two must not be conflated.)

**Scope:** generic LLM prompts. There is no agent-skill-file, SKILL.md, or cross-ecosystem (Claude Code / OpenClaw / OpenCode) analysis. The only cross-platform element is Table 5, which compares *role-definition conventions* across LLM service providers (OpenAI, Anthropic, Mistral, Llama) — a provider-syntax comparison, not a linguistic-feature or agent-skill comparison.

**Verdict: (iii) confirmed NO overlap.** PromptPrism is a qualitative/structural taxonomy of prompt *components*, whose "syntactic pattern" axis is formatting/markup structure, not the spaCy-derived numeric linguistic features our study extracts. It is still the closest named work to formally treating "syntactic pattern" as a prompt dimension, so it earns a specific citation in related work — but the differentiation is clean and one sentence: *they taxonomize structural/formatting syntax qualitatively; we extract numeric psycholinguistic and dependency-parse features and link them to adoption and execution outcomes.* It is a taxonomic/classification precedent for RQ1's "instruction dialect" framing, **not** a feature-overlap risk requiring a defensive differentiation paragraph.

## zhang2025-promptdatasets

**Paper:** "Large Language Model Prompt Datasets: An In-depth Analysis and Insights," Yuanming Zhang, Yan Lin, Arijit Khan, Huaiyu Wan. arXiv:2510.09316. Submitted Oct 2025, revised May 2026.

**Why this paper matters:** it is the direct methodological ancestor of our own `posdep_*` feature group (README WS2 Issue A), and it is also the paper the README explicitly names as the "saturated question" RQ1–RQ3 are designed to avoid repeating. Both facts need to appear clearly in the manuscript — one as a positive citation (feature provenance), one as a negative/avoidance citation (why we don't repeat their exact experiment).

**Corpus:** compiles 129 heterogeneous LLM prompt datasets — over 1.22TB, more than 673M instances — into a taxonomy, then runs multi-level linguistic analysis (lexical, syntactic, semantic) across 7 representative corpora selected from that compilation. This is a general-LLM-prompt corpus, not an agent-skill-file corpus — no SKILL.md, no agent-skill marketplace data anywhere in it.

**The 62-d feature vector (CONFIRMED VERBATIM by independent opus re-fetch of the abstract):** a 62-dimensional vector of POS-tag and dependency-label relative frequencies, extracted via standard NLP parsing (not LLM-based). Shown to function as a "uniquely efficient routing primitive": using this vector to route prompts (e.g., to different model sizes/specializations) recovers more than 93% of the accuracy achievable with GPU-based embedding methods, at 1.9× lower latency (3.0ms vs. 5.7ms) and with no GPU or vocabulary/tokenizer dependency required. This is the exact feature design our `posdep_*` group replicates — cite this paper directly at that point in the methods section as the source/precedent, per the README's own framing ("replicates ... the routing-features literature").

**Three static prediction tasks (the outcomes we are NOT repeating):** (1) prompt filtering, F1=0.90; (2) domain/task classification, Macro-F1=0.975; (3) prompt-quality prediction, AUC=0.792. All three are *static* properties of a single prompt in isolation — none is an adoption proxy (installs/downloads/stars) and none is a real execution/task-success outcome measured by running an agent. This is precisely the gap the README's "Explicitly avoided (saturated)" line refers to: "predicting static generation quality or domain classification from these features (PromptPrism; arXiv:2510.09316)" — note the README's own citation there is to the *feature literature* broadly and specifically names this arXiv ID, confirming this is the anchor paper for that avoidance decision.

**Key linguistic finding worth quoting in our own discussion section:** syntactic/routing features (the 62-d vector) correlate *negatively* with response quality, while lexical diversity is the strongest quality predictor despite having minimal value for routing. The paper's own architectural recommendation is a two-stage pipeline — cheap syntactic/routing features for fast triage, lexical-diversity-based scoring for quality — which is a useful frame if we ever want to justify why our own feature groups (`posdep_*` for routing/structure, `lex_*` for MTLD/HDD diversity) serve different roles rather than being redundant with each other.

**Differentiation to state explicitly in the manuscript:** (1) corpus — general LLM prompts across 129 heterogeneous datasets vs. our agent-skill instruction files across multiple ecosystems (Claude Code, OpenClaw, OpenCode, Hermes); (2) outcome — static filtering/classification/quality-AUC on a single prompt in isolation vs. our adoption proxies (RQ2) and real execution success under restyling (RQ3); (3) framing — they ask "can these features predict properties of *this* prompt," we ask "do these features cluster into dialects across ecosystems (RQ1) and do those dialects predict adoption/execution (RQ2/RQ3)." Their paper answers a *different, already-solved* question about the same feature family; ours asks new questions the feature family has never been pointed at.

## bai2026-clawgym

**Paper:** "ClawGym: A Scalable Framework for Building Effective Claw Agents." 14 authors: Fei Bai, Huatong Song, Shuang Sun, Daixuan Cheng, Yike Yang, Chuan Hao, Renyuan Li, Feng Chang, Yuan Wei, Ran Tao, Bryan Dai, Jian Yang, Wayne Xin Zhao, Ji-Rong Wen. arXiv:2604.26904, Apr 2026.

**Three components:** ClawGym-SynData (13.5K *training* tasks, via two pipelines: persona-driven task synthesis, and a **skill-grounded pipeline** that composes tasks directly from entries in OpenClaw's skill registry — real SKILL.md documentation is converted into structured task annotations: summary, core content, usage constraints, input-output characteristics — and these structured annotations remain part of the task definition, available to and manipulable by the agent during execution, not just used to generate the task and then discarded); ClawGym-Bench (200-instance curated evaluation set, built via automated filtering plus human-LLM review for quality); ClawGym-Agents (SFT + lightweight RL training recipes for personal/desktop agents on the OpenClaw runtime).

**Confirms our README's figure:** the "13.5K tasks are training data, eval bench = 200 instances" note in the citation whitelist (ADR-0002) is accurate per this reading — training and evaluation sets are clearly separated and differently sized, and should not be conflated when citing "ClawGym's corpus size" in the manuscript.

**What's missing (the useful gap for us):** no experiment anywhere in the paper tests how rewriting, restyling, or otherwise varying the prose of a skill-file/instruction document affects task success — there is no documentation-style ablation of any kind. The skill-grounded pipeline treats SKILL.md content as a source of task-defining facts to be extracted and structured, not as a linguistic artifact whose phrasing might independently matter.

**Relevance to Timbro:** a strong candidate task source for the WS4/RQ3 pilot specifically because tasks already embed real skill-file prose as part of the task definition — this is exactly the kind of substrate a content-preserving restyling experiment needs (a task where the skill's prose is load-bearing for how the agent behaves, not just decorative documentation sitting outside the task loop). The absence of any prose-style ablation in ClawGym itself is evidence, not just an assumption, that this remains open/novel territory for our RQ3 pilot to claim.

## merrill2026-terminalbench

**Paper:** "Terminal-Bench: Benchmarking Agents on Hard, Realistic Tasks in Command Line Interfaces." Authors include Merrill, Shaw, Nicholas Carlini (confirmed a genuine co-author, not a hallucinated credibility add — this was independently checked given Carlini's prominence makes him a plausible target for a fabricated-authorship error), et al. arXiv:2601.11868, Jan 2026.

**Benchmark composition:** 89 hard, realistic command-line tasks spanning 16 categories — software engineering, security, scientific computing, data science, games, debugging, and more — at easy/medium/hard difficulty, all human-validated for solvability, realism, and specification clarity (i.e., a human confirmed each task is actually completable as specified and that the task description isn't ambiguous or broken). Frontier models/agents score below 65% even at their best; weaker models score around 15%. Scale of evaluation: 6 agents × 16 models × ≥5 runs each = 32,155 total trials — a useful reference point for how much repeated-trial noise-averaging a rigorous agent-execution study needs.

**Harbor, the execution harness (github.com/laude-institute/harbor, maintained by the Laude Institute + Stanford):** runs Terminal-Bench 2.0 specifically, and is a general-purpose orchestration layer for agent evaluation across multiple environments/cloud providers (Daytona, Modal, LangSmith, and others) to support large-scale parallel testing. This is infrastructure we could plausibly run our own WS4 pilot on top of, not just cite.

**Harbor task directory structure (the detail that matters most for our WS4 design):** each task is a directory containing:
- `instruction.md` — a plain markdown task description (the prose an agent reads to understand what to do)
- `task.toml` — configuration/metadata
- `environment/` — Docker setup defining the sandboxed execution environment
- `solution/` — an optional reference solution
- `tests/` — verification scripts that determine pass/fail

**The direct methodological precedent for our "content-preserving restyling" design:** Harbor's own documentation confirms that `instruction.md` prose can be freely restructured — headings reorganized, sections reordered, formatting changed — without altering the functional task requirements. The invariant Harbor's own tooling enforces is exactly the invariant our WS4 pilot needs: requirements (what the agent must accomplish, verified by `tests/`) stay fixed and identical, while presentation (how the requirements are phrased in `instruction.md`) is deliberately variable. This maps almost one-to-one onto README §9's acceptance gate (a): "code blocks, commands, file paths, and frontmatter byte-identical to the original" while prose is restyled. Practically, this means our WS4 restyling protocol can potentially reuse Harbor's task format directly — restyle `instruction.md` per WS3 cluster profile, leave `task.toml`/`environment/`/`tests/` untouched — rather than inventing a new task-directory convention from scratch.

**Relevance to us:** cite Terminal-Bench/Harbor as (a) a primary candidate task source for the WS4 pilot (alongside ClawGym's 200-instance eval bench as a fallback/alternative, per README §9), and (b) the closest existing infrastructure-level validation that "restyle the instructions, freeze the requirements" is a coherent, already-practiced experimental design — not a technique we're inventing for the first time, but one we're the first to apply specifically to test linguistic-style effects on execution.

## liu2026-graphofskills

**Paper:** "Graph-of-Skills: Dependency-Aware Structural Retrieval for Massive Agent Skills." Dawei Liu, Zongxia Li, Hongyang Du, Xiyang Wu, Shihang Gui, Yongbei Kuang, Lichao Sun. arXiv:2604.05333, Apr 2026 (title/authors/numbers all independently re-confirmed verbatim via a second opus fetch).

**Problem addressed:** context saturation when an agent has access to a very large skill library — naive top-K similarity retrieval over a big skill pool tends to surface skills whose prerequisites (other skills they depend on) aren't satisfied, wasting context and leading the agent down incomplete or broken execution paths.

**Method:** builds an **offline DAG of skills** where directed edges encode dependency relationships ("skill A requires skill B" — e.g., a high-level automation skill depending on a lower-level file-manipulation skill). At query time, retrieval is **dependency-aware**: a hybrid semantic-lexical retrieval step identifies candidate skills relevant to the query, then **personalized PageRank** over the DAG (seeded from those candidates) surfaces a bounded, coherent bundle that respects the dependency structure — surfacing prerequisite skills alongside the skills that need them, rather than just the top-K most semantically similar skills in isolation.

**Evaluation:** "SkillsBench," GPT-5.2 Codex backbone. Reports 25.55% peak reward increase and 56.72% token reduction versus naive top-K retrieval, tested across skill libraries ranging from 200 to 2,000 skills (showing the benefit holds and likely grows as library size scales).

**Nature of the contribution:** purely structural/graph-topological. There is no linguistic or stylistic analysis of skill text anywhere in this paper — it measures and exploits *dependency relationships between skills*, not *properties of the prose within a skill*. Zero overlap with RQ1 (topology of linguistic features), RQ2 (adoption prediction from linguistic features), or RQ3 (execution outcomes under content-preserving restyling).

**IMPORTANT UNRESOLVED PROVENANCE CAVEAT — read this before citing our own corpus table:** our corpus build (ADR-0003) lists the HuggingFace dataset `davidliuk/graph-of-skills-data` (2,000 skills, MIT license, described as "paper-curated benchmark libraries, `skills_2000.tar.gz` is the superset") as a corpus source, and attributes it to *this* paper. The basis for that attribution is: (1) the HF username "davidliuk" plausibly matches author "Dawei Liu" (a common romanization/username-construction pattern — first-initial + surname), and (2) the dataset's skill count (2,000) matches the paper's stated evaluation scale ("skill libraries of 200 to 2,000 items"). **Neither of these is independently confirmed.** The arXiv abstract itself does not mention a HuggingFace release, does not name a dataset called `graph-of-skills-data`, and does not confirm that "SkillsBench" (the paper's evaluation benchmark) is the same artifact as the 2,000-skill HF dataset we're relying on. This is a plausible-but-unverified link, not a confirmed one.

**Required follow-up before treating this as settled:** visit the paper's GitHub repository (if one is linked from the arXiv page or paper PDF) or the HuggingFace dataset card for `davidliuk/graph-of-skills-data` directly, and look for an explicit cross-reference (a citation to arXiv:2604.05333 on the dataset card, or a link to the HF dataset from the paper's repo) before upgrading the ADR-0003 corpus table's provenance claim from "attributed" to "confirmed." Until that check happens, any mention of this corpus source in the manuscript's corpus-construction section should carry the same hedge this note does — do not silently strengthen the claim in later drafts.

**Relevance to Timbro beyond the provenance caveat:** cite as one more "ecosystem-scale infrastructure paper with zero linguistic-feature overlap" alongside Ling et al., SkillNet, and AgentSkillOS, reinforcing that dependency-graph/retrieval-structure work and our linguistic-topology work are contributions on entirely orthogonal axes of the same skill-ecosystem object.
