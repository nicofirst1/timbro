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
