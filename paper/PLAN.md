# Paper plan — Linguistic topology of agent skill files

**Status:** the executable path (renamed from README.md 2026-07-08; README.md is now a short
pointer index). Split 2026-07-08: locked decisions, novelty position,
citation whitelist, corpus facts, and the **BINDING pre-registered analysis rules**
(rules D1–D9) now live as ADRs in **`docs/adr/`** (they win on any conflict). Written to be
executable by less capable models.
**Branch policy:** all paper work lives on the `paper` branch under `paper/`. Only Timbro
functionality (WS2) merges to `main`, via normal issue/PR flow.

---

## 1. Research questions

- **RQ1 (topology):** Do deterministic linguistic features of agent skill files — imperative
  density, syntactic depth, cohesion, hedging/certainty, readability, POS+dep-relation
  distributions — cluster into distinct "instruction dialects" across ecosystems
  (Claude Code, OpenClaw, OpenCode, Hermes)?
- **RQ2 (adoption):** Do these features predict adoption proxies (installs/downloads, stars,
  update survival), controlling for length, topic, and ecosystem? *(Amended 2026-07-08:
  primary outcome = trailing weekly install rate; age covariate mandatory — ADR-0007.)*
- **RQ3 (execution, pilot):** Does restyling a skill's prose into a different linguistic
  profile — content held constant — change agent task-success rate?
- **RQ4 (temporal evolution — added 2026-07-07, pre-registered in ADR-0005):** How do individual
  SKILL.md files evolve linguistically across revisions, and does linguistic evolution relate
  to adoption? Positioning: the self-evolving-skills literature (SkillForge, SkillClaw, SAGE,
  etc.) improves skills by outcome but never characterizes WHAT changes in the text; we measure
  exactly that.

- **RQ5 (human baseline — added 2026-07-08, secondary):** How does instruction written *for
  agents* (SKILL.md) differ linguistically from instruction written *for humans* (README /
  CONTRIBUTING)? Audience is perfectly collinear with era (human docs pre-date LLMs; skills
  post-date them), so the design is a three-cell difference-in-differences:
  (1) human/pre-2023 — README\*/CONTRIBUTING\* from The Stack v1 (`bigcode/the-stack`,
  collected Nov 2021–Jun 2022, pre-ChatGPT by construction, HF streaming — no full download);
  (2) human/post-2023 — current GitHub READMEs (LLM-contaminated, and that's fine: it makes
  the C3−C2 contrast a conservative lower bound); (3) agent/post-2023 — the existing skills
  corpus. **Design, cells, hypotheses, and kill criteria are FROZEN in
  [ADR-0008](docs/adr/0008-rq5-preregistration.md) (D10)** — bracketing estimand
  `[C3−C2, C3−C1]`, not classical DiD. Kill criteria: ~2 days of extraction fight → drop RQ5
  to a limitations paragraph. Secondary RQ: must not starve RQ1–RQ4.

*(Added 2026-07-07 — domain heterogeneity, RQ1 framing)*: register variation may be
domain-driven (skills differ by domain — healthcare vs. software dev etc.; hu2026-clawhub
already shows topic-level clusters). Our claim is *linguistic* dialects, so we must show they
are not merely topic clusters — and if they ARE domain-aligned, that is itself a register
finding (Biber: registers are situationally defined), to be reported as such, not hidden.
See rule D8 in ADR-0004.

**Explicitly avoided (saturated):** predicting static generation quality or domain
classification from these features (prompt-datasets study; arXiv:2510.09316).

## 4. Workstreams

Dependency order: WS1 → WS3 needs WS2 → WS4 needs WS3 → WS5 needs all. WS6 is calendar-driven.

### WS1 — Corpus assembly (July) — `agent:mechanical`

Code in `paper/code/ws1/`, data in `paper/data/` (gitignored / DVC-tracked). Results ledger:
`paper/code/ws1/LEDGER.md`. **Status: builds 1–4 + 7 done 2026-07-08 (ClawHub dropped);
dedup.py + merge.py written, runs pending; step 8 not yet written (see LEDGER STATUS).**

1. `build_skill_diffs.py`: stream `shl0ms/skill-diffs` with `datasets` (streaming mode, do not
   load 8GB in RAM). Emit one row per unique `skill_id`: latest SKILL.md text, `repo`,
   `platform`, `stars`, `license_spdx`, first/last commit dates, `n_revisions`.
   *(Amended 2026-07-07 for RQ4, see ADR-0005)*: emit **BOTH** tables — (a) the deduped
   latest-snapshot table above (RQ1–RQ3 cross-sectional corpus), and (b) a **version-chain
   table** (all per-commit snapshots keyed within a single repo, pre-dedup) for RQ4.
   *(Schema frozen 2026-07-07, see ADR-0005 addendum)*: concrete artifacts — (a) cross-sectional
   table = latest content state per canonical `skill_id`, deduped per D1; (b) version-chain
   table = the ADR-0005 chain definition (group by `skill_id`, order by `commit_date`, link
   `before_sha == prev.after_sha`; roots from `skills_initial.parquet`, pairs from
   `diffs_clean.parquet`). **Direct parquet download, not datasets-server row APIs** (they fail
   on the large configs — see ADR-0005 access gotcha).
   *(Added 2026-07-07, motivated by issue #21's folk-advice feature family)*: `build_skill_diffs.py`
   also emits per-skill sibling-file columns derived from `bundled.parquet` (sibling files at
   HEAD): `n_sibling_files`, `has_scripts_dir`, `has_references_dir`, `has_assets_dir`,
   `has_readme_in_folder`. These operationalize the multi-file practitioner tips (progressive
   disclosure, one-folder-per-skill, auxiliary docs) that `timbro analyze` cannot see since it
   only ever receives a single document's text.
2. `build_gos.py`: download `skills_2000.tar.gz` only (29MB), extract SKILL.md files.
3. ~~`build_clawhub.py`~~ **DROPPED 2026-07-08** (LEDGER + ADR-0006) —
   ClawHub is narrative hook only.
4. `build_slop.py`: clone `amoghacloud/clawskills-intelligence-corpus` (few MB), tag every doc
   `source=slop_stub`.
5. `dedup.py`: exact dedup by normalized-text SHA256; near-dup with MinHash
   (**use `datasketch`**, do not hand-roll), threshold 0.9 Jaccard on 5-gram shingles; keep one
   canonical doc per cluster, record `near_dup_cluster_id` and cluster size. **D1's >60%
   fork-explosion clause is live** — the dataset-shipped fork linkage already flagged 67%
   non-canonical (LEDGER 2026-07-08); check it when dedup runs.
6. `merge.py`: merge to `paper/data/corpus.parquet` with schema:
   `skill_id, source, platform, text, frontmatter_json, repo, stars, downloads, installs,
   created_at, updated_at, license_spdx, n_revisions, near_dup_cluster_id, is_canonical`
   (nullable where a source lacks the field). Joins skills.sh installs on the loose
   `[a-z0-9]` key (LEDGER 2026-07-08); emits `rq2_holdout_candidates.parquet`.
7. `build_skillssh.py` — **done 2026-07-08**: 19,906 rows in `skillssh_meta.parquet`, 98.5%
   with installs; `/terms` cleared, robots honored, on-disk HTML cache makes it resumable.
   Recipe details in LEDGER.
8. `parse_weekly_installs` *(added 2026-07-08 — ADR-0007)*: re-parse the existing skills.sh
   HTML cache (**no re-crawl**) — every detail page embeds the trailing weekly-install series
   in the sparkline `aria-label` ("Weekly installs: …"; verified 19,906/19,906 pages; always
   exactly 8 weekly values — the earlier "9–16 values" reading was a thousands-separator
   parsing artifact, see LEDGER 2026-07-08; 580 all-zero). Frozen parse rule: split on
   `,\s+`, strip intra-value commas. Emit `skillssh_weekly.parquet` (owner/repo/skill-keyed)
   with `weekly_installs` (8-int list) and `installs_wk_mean` (mean of the series; name
   resolved 2026-07-08, ADR-0007). `installs_wk_mean` is the **primary RQ2 outcome**.

9. `build_human_baseline.py` *(added 2026-07-08 — RQ5, secondary)*: two cells.
   (a) human/pre-2023: stream `bigcode/the-stack` (HF `streaming=True`, never download the
   6TB), keep files whose path basename matches `README*` / `CONTRIBUTING*` with `.md`
   extension; carry repo, license, `first_timestamp`/`last_timestamp` metadata. Sample to a
   size comparable to the skills corpus (~20k docs), record the sampling seed.
   (b) human/post-2023: READMEs from currently-active GitHub repos (GH API or a recent HF
   scrape), same filename filter, `created/updated ≥ 2023`; drop repos containing a SKILL.md
   (ADR-0008 exclusion). Contamination expected and acceptable. Both cells →
   `paper/data/human_baseline.parquet` tagged `audience=human, era={pre,post}`; same dedup
   treatment as step 5, English-only filter applied to all cells identically.
   **Data rules frozen in ADR-0008; timebox ~2 days, then RQ5 kill criteria applies.**

**Acceptance:** a WS1 `REPORT.md` with per-source counts, dedup stats (exact + near-dup
removal rates), platform breakdown, license breakdown, install-join rates (both denominators
per LEDGER 2026-07-08). No data files in git (DVC pointers only).

### WS2 — Timbro vertical slices (July–Aug) — GitHub issues on `main`, one per branch/PR

**Status 2026-07-07: DONE for the core** — #17 (`timbro analyze` library-backed feature
vectors) + #18 (custom extractors) closed 2026-07-06, merged to `main` (b54ba3a):
`src/timbro/analyze.py`, `src/timbro/lexicons/`. Exploratory extensions filed as #21
(folk-advice features) and #22 (plain-language features), both `agent:mechanical`,
milestone M5 — optional for the workshop paper, wanted for the full paper.

Feature groups, dependency allowlist, and acceptance criteria live in the closed issues;
repo conventions in CLAUDE.md apply (implementer specs are decisions; `uv run pytest` +
`uv run ruff check src/` before done; never touch `_PENALTY`/`_WEIGHTS`/verdicts).
**Non-goals:** no new rubric, no changes to scoring/verdicts, no LLM calls, no network at
analyze time.

### WS3 — Corpus analysis (Aug) — `paper/code/ws3/`

1. Run `timbro analyze` over `corpus.parquet` canonical docs → `paper/data/features.parquet`.
   (WS3 runs against `main`'s Timbro — the `paper` branch predates the #17/#18 merge.)
2. Descriptives: feature distributions per source/platform; organic vs. slop-stub separability
   (simple logistic regression / AUC — validates the feature set and gives a Timbro story).
3. Clustering (RQ1): standardize features; PCA then HDBSCAN (fallback k-means, k by silhouette);
   name clusters by their most-deviant features; map clusters onto the heuristic table from the
   original research report (imperative-dense vs. conditional-rich vs. narrative, etc.).
   Confound gates: platform (D4), domain (D8), era (D9).
4. Adoption models (RQ2): Spearman screens, then regressions of the confirmatory outcomes
   (per ADR-0007: primary `log1p(installs_wk_mean)`; robustness `log1p(total installs)`;
   stars on single-skill repos) on features with **log-length + log-age covariates**, platform
   and domain fixed effects, repo random effects. Benjamini–Hochberg per D6. Report effect
   sizes with CIs, not just p-values.
5. RQ4 temporal evolution: ONLY under ADR-0005's frozen rules (chains ≥3 versions; 14,388 eligible
   per LEDGER). Includes the ADR-0005 addendum 2 embedding-delta exploratory.
6. Holdout: characterize `rq2_holdout_candidates.parquet` topic/dialect novelty BEFORE scoring
   it; report degradation as a drift signal (LEDGER open problem, 2026-07-08).
7. RQ5 human baseline *(added 2026-07-08, secondary — only if WS1 step 9 survived its
   timebox)*: run `timbro analyze` over `human_baseline.parquet`; analysis ONLY under
   ADR-0008's frozen rules (D10): confirmatory contrast = C3 vs C2, two-sided, 5-feature
   family, log-length covariate, BH q=0.10 within family; `C3−C1` and `C2−C1` descriptive
   (bracket + era shift). ≥5k docs per human cell after dedup or downgrade to descriptive.
   Genre caveat (README ≠ procedure even for humans) named in the paper per ADR-0008.

**Acceptance:** scripted, re-runnable (`uv run python paper/code/ws3/run_all.py`), figures to
`paper/figures/`, a findings memo `paper/code/ws3/FINDINGS.md`, deviations in
`paper/code/ws3/DEVIATIONS.md`.

### WS4 — Pilot execution experiment (Sep) — `agent:judgment`, frozen spec in §9 below

Do not run without user budget approval; implement from §9, not from memory.

### WS5 — Manuscript (Sep–Oct) — `paper/manuscript/`

Outline: Intro → Related work (whitelist in ADR-0002; position vs. Ling and Cho
explicitly) → Corpus & tool (Timbro release, `uvx` trial path — coordinate with repo issue #9
so reviewers can run it) → Topology & adoption findings → Pilot → Limitations (proxies ≠
quality; pilot scale; English-only; install-count noise per Ling; weekly-install definition
opacity per ADR-0007). Run the `schimel-pass` and `nico-voice` skills on drafts. ARR
needs: anonymized repo, derived-features-only data release, license statement per ADR-0003.

### WS6 — Venue calendar

- **~Jul 11, 2026:** NeurIPS 2026 workshop list drops — pick an agents workshop, note its CFP
  (Aug–Sep). Workshop paper = WS1+WS2+WS3 only.
- **ARR Oct 2026** (exact deadline TBA, assume mid-Oct): full paper. Buffer: WS5 draft done
  by Oct 1.
- Backup: COLM 2027 (~late Mar) if WS4 becomes the centerpiece.
- **Sep 1, 2026:** skills.sh re-crawl #2 (cached recipe, ~3h, ≤2 req/s) — second 8-week
  window → 16-week weekly-install series for the ADR-0005 lagged exploratory (pinned 2026-07-08,
  ADR-0007). Skipping it = log why in the WS1 LEDGER.

## 5. Guardrails for executing agents

1. **Citations:** only from the whitelist in ADR-0002 or newly *verified* sources
   (fetch and confirm the paper exists and says what you claim). Never cite from memory.
2. **Data hygiene:** nothing under `paper/data/` gets committed (DVC pointers only).
   Redistribute feature vectors, never raw skill text.
3. **Politeness:** honor documented rate limits and 429/Retry-After on any harvest. No mass
   scraping of an unprobed source without user sign-off.
4. **Statistics:** length AND age are always covariates; multiple-comparison correction
   always; effect sizes with CIs.
5. **Determinism:** Timbro-side extraction never calls an LLM or the network.
6. **Money:** any step that spends (API runs, GPU time, licenses) needs explicit user approval
   first.
7. **When a spec here conflicts with reality** (dataset schema changed, endpoint gone, count
   differs wildly): stop, write down the discrepancy, ask the user. Do not silently substitute.

## 6. Risks

- **Novelty race:** Ling et al.'s group could add a linguistic layer. Mitigation: workshop
  paper as flag-plant; move WS1–WS3 fast.
- **Adoption-signal weakness:** install-labeled skills ≤ ~1.74% of the corpus and skills.sh
  is curated → selection bias; report coverage as RQ2's denominator, run the labeled-vs-
  unlabeled selection check, cross-check with repo stars (LEDGER 2026-07-08).
- **Restyling validity (WS4):** "content-preserving" is the load-bearing assumption; Timbro
  profile checks + a manual audit of a sample are the control.
- **ARR Oct date unconfirmed** — re-check aclrollingreview.org/dates in August.

## 7. State snapshot

- 2026-07-04: branch `paper` created; master plan written; citations/datasets/ClawHub
  verified by subagent sweeps (details now in ADR-0002/ADR-0003).
- 2026-07-07: WS2 core done (#17/#18 merged to `main`, b54ba3a). RQ4 pre-registered (ADR-0005),
  chain mechanics frozen same day after the schema probe. D8 added.
- 2026-07-08: WS1 builds done except dedup/merge (LEDGER). ClawHub dropped. skills.sh crawl
  complete (19,906 skills). Install-join key decided (loose `[a-z0-9]`, ~100% on
  corpus-present skills).
- **2026-07-08 (this update):** plan split — binding decisions and pre-registration moved
  verbatim to ADRs in `docs/adr/` (ADR-0001–0005). New ADR-0007
  amendment: weekly-install series discovered in the crawl cache sparkline aria-labels
  (100% coverage) → primary RQ2 outcome becomes `installs_wk_recent` (renamed
  `installs_wk_mean` later that day, ADR-0007); mandatory
  `log1p(skill_age_days)` covariate; **D9** era-confound rule. WS1 gains step 8 (cache
  re-parse, no re-crawl).
- **2026-07-08 (later):** RQ5 added (human-baseline, secondary) after a dataset hunt
  confirmed The Stack v1 gives a pre-ChatGPT human cell by construction; WS1 gains step 9
  (timeboxed ~2 days), WS3 gains step 7. **Frozen same day as ADR-0008 (D10)** — bracketing
  design `[C3−C2, C3−C1]` (the naive DiD algebra collapses to C3−C2; contamination makes it
  a lower bound), two-sided tests on the 5-feature family, ≥5k/cell floor.
- Still open: NeurIPS workshop list ~Jul 11; `kubectl port-forward` test on NM-BAIOS before
  pilot runs; WS1 dedup.py + merge.py + step 8 + step 9 (RQ5).

## 9. WS4 pilot — full spec (mechanical once WS3 clusters exist)

**Compute:** open-weights coder models (*amended 2026-07-08: three same-family sizes — see
the model-scale bullet below*) served with vLLM on the Fraunhofer **NM-BAIOS k8s
cluster** (use the `nm-baios-gpu` skill; Job template on wiki page
[[nm-baios-gpu-batch-jobs]]). The eval harness runs on the local machine (on VPN) against the
served endpoint — GPU time, not API dollars. User approves the GPU-time plan before any runs.

**Design (frozen before first run; amended 2026-07-07 — the spec was not yet frozen, so these
are legitimate pre-registration amendments, motivated by the lit-review synthesis in
`paper/literature/literature.md` / `paper/literature/lit_review_practitioner.md`):**
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
- **Model scale (added 2026-07-08; pre-freeze amendment):** scale becomes a third crossed
  factor with 3 levels — **same-family instruct coder models at ~7B / ~14B / ~32B, same
  quantization across all three** (AWQ 4-bit), so quantization does not confound scale.
  Motivation: the paper's prescriptive value depends on the *size* of the style effect
  relative to what a practitioner can otherwise buy — scale is the natural yardstick — and
  cross-model heterogeneity in prior skill/context results (li2026-skillsbench,
  jimenez2024-sweagent) means a single-model estimate may not transport. Default trio:
  Qwen2.5-Coder-{7B,14B,32B}-Instruct AWQ; a newer same-family trio may be substituted
  **only before the first run**, pinned in `paper/pilot/models.json`. All three served on
  the H100 where possible (7B is cheap there); 7B may fall back to a MIG A100 slice only if
  the H100 queue blocks — hardware recorded per run in the manifest, disclosed if mixed.
  The **harness stays fixed** across all scales (harness variation would be confounded with
  the task set — deliberately out of scope).
- **Runs (amended 2026-07-07; re-amended 2026-07-08):** 3 scales × 5 conditions × 24 tasks
  × 3 seeds = **1,080**, temperature 0.2.
  Per-run manifest: skill hash, prompt hash, model+quantization, seed, harness commit
  (experiment-discipline). *(Added 2026-07-07)* every run also logs **whether the skill was
  actually invoked/triggered**; success-conditional-on-invocation is a secondary outcome
  (motivation: contested ~56% non-invocation anecdote in the practitioner review — a restyled
  skill that never fires can't show a style effect). *(Added 2026-07-08)* invocation rate is
  also reported **per scale** (pre-registered secondary descriptive: smaller models may
  simply not fire the skill, which is a mediator of any scale×style pattern).
- **Stats (amended 2026-07-08):** mixed-effects logistic
  `success ~ condition * scale + (1|task)`, scale as an ordered factor (treatment-coded
  contrasts + a log-parameter trend). Pre-registered estimands, in order: (a) condition
  effect **within each scale** — the original RQ3 question, now per-scale; pairwise McNemar
  original-vs-each-variant stays, per scale; (b) scale main effect, in the same pp units;
  (c) condition × scale interaction — "does style sensitivity change with capability";
  expected underpowered at this n, report its MDE, **exploratory unless it clears the
  test**. Variance decomposition (task / scale / condition / seed) is descriptive only.
  Always report the MDE for this n. A null is publishable — report it straight.
- **Practical-significance goalpost (fixed 2026-07-08, before any run):** style
  recommendations are framed as *actionable* in the paper only if the best-vs-worst
  condition gap is **≥ 5 pp with a 95% CI excluding 0** in the pooled model. Below that,
  the calibrated claim is "style effects are small relative to scale," reported straight —
  with the headline comparison in common units: **pp gained by best restyling vs pp gained
  per scale step**. Either outcome is a publishable, prescriptive result.
- **Pre-run power check (blocking, added 2026-07-08):** before any GPU run, simulate the
  MDE for the pooled condition effect under the frozen n (sweep task ICC 0.2–0.4). If MDE
  > 5 pp, increase seeds (the cheap axis) until MDE ≤ 5 pp, or record in the WS4 ledger why
  not — decided and written **before** runs, not after.
- **Abort criteria:** restyle acceptance fails on >30% of tasks → stop and redesign the
  protocol; the verifier disagrees with itself on identical (condition, seed) reruns → fix the
  harness before generating any results. *(Added 2026-07-08)* a scale that cannot complete
  the harness protocol (< 50% of its no-skill-control runs produce a parseable episode) is
  **dropped to descriptive and logged** — never silently substituted with a different model.
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
  or a ~7B 4-bit on MIG (note the model change in the paper). *(2026-07-08: partly
  superseded — all three scales are now in-design (§9 model-scale bullet); "fallback"
  language applies only to hardware placement, not to which models run.)*
- **Hard cap `activeDeadlineSeconds: 21600` (6h) on every Job** — the vLLM server cannot run
  persistently. Chunk the 1,080 runs (288 pre-amendment 2026-07-07, 360 pre-amendment
  2026-07-08; see the dated §9 amendments) into ≤6h
  batches; only the 32B third runs at full H100 cost — 14B/7B are cheaper per run; put `HF_HOME` on the home PVC
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
