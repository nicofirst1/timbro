# WS1 ledger — corpus assembly

Canonical results ledger for WS1 (experiment-discipline §4). Numbers are cited from
`manifests/*.manifest.json` / `REPORT.md`, never retyped. Newest on top.

**WS1 fully CLOSED 2026-07-09** — all STATUS items below are `[x]`.

## STATUS

- [x] `build_skill_diffs.py` — anchor corpus (cross-sectional + version-chain tables). Done
      2026-07-08 (see RESULTS). Cross-sectional rebuilt via `--cross-only` after the CRLF
      frontmatter fix; chains built via `--chains-only`.
- [x] `build_gos.py` — graph-of-skills 2000. Done.
- [✗] `build_clawhub.py` — **DROPPED as a data source 2026-07-08** (see RESULTS). Not built.
      ClawHub kept as a narrative hook only (ClawHavoc purge).
- [x] `build_slop.py` — labeled low-quality stubs. Done.
- [x] `dedup.py` — exact + MinHash near-dup collapse (D1). **Written + unit-tested** (TDD,
      ponytail-reviewed) 2026-07-08. Emits a compact `dedup_map.parquet` (skill_id →
      near_dup_cluster_id / cluster_size / is_canonical), not a text copy. MinHash 0.9 Jaccard
      enforced by an explicit `jaccard() >= 0.9` post-filter on LSH candidates (LSH banding
      alone only approximates). **Full 672k-row run done 2026-07-08 (see RESULTS) — D1
      fork-explosion STOP FIRED (skill_diffs near-dup removal 0.6658 > 60%); consult
      resolved 2026-07-08 → ADR-0010 (cluster unit; RQ2 join dedupes to entry-level
      representative, NOT canonical-only).**
- [x] `merge.py` — corpus.parquet + REPORT.md + `rq2_holdout_candidates.parquet`. **Written +
      unit-tested** (TDD, ponytail-reviewed) 2026-07-08; install join reworked to ADR-0010
      entry-level representative (sonnet-implemented, opus-reviewed). Loose install-join key
      (`[a-z0-9]`-normalized owner/repo/name). corpus.parquet is exactly the 15 `CORPUS_COLUMNS`
      (skill_diffs sibling cols stay in `src_skill_diffs.parquet`). **Full run done
      2026-07-08 (see RESULTS)** — 672,022 rows, 9,686 install-labeled entries, holdout 1,704.
- [x] `parse_weekly_installs` — re-parse the cached skills.sh HTML for the sparkline
      weekly-install series. **Written + unit-tested** (ponytail-reviewed) 2026-07-08.
      Pre-freeze inspection DONE: the "9–16-value" series was a thousands-separator artifact —
      the sparkline is always an 8-week window; frozen separator `,\s+` yields 8 values on
      19,906/19,906 (see RESULTS). Adds `weekly_installs` + `installs_wk_mean` (mean of the
      series; primary RQ2 outcome per ADR-0007; renamed from `installs_wk_recent` after the
      naming flag was resolved 2026-07-08 — estimator unchanged, tests pass post-rename) →
      `skillssh_weekly.parquet` (owner/repo/skill key, WS3-side join artifact). **Run done
      2026-07-08** (see RESULTS) — 19,906 rows, live counts reproduce the pre-freeze inspection.
- [x] `build_machine_cell.py` — machine-authored register cell (ADR-0009, exploratory,
      WS1 step 10). **Written + unit-tested + run 2026-07-08** (sonnet-implemented,
      opus-reviewed APPROVE; see RESULTS). 587 rows → `src_machine_cell.parquet`
      (standalone cell, NOT folded into corpus.parquet).
- [x] `build_human_baseline.py` — RQ5 human cells (ADR-0008, WS1 step 9). **Written +
      unit-tested + run 2026-07-08** (sonnet-implemented; see RESULTS). Post-2023 GitHub
      cell DONE: 5,161 rows ≥ the 5k floor. HF gate later cleared; the first full the-stack
      stream RAN 2026-07-09 (floors passed pre=14,866/post=5,271) but was LOST to a
      write-time ArrowTypeError (list-typed license) — type-safe write + post-stream
      reservoir checkpoint added (commit 25740e9), **rerun COMPLETE 2026-07-09** (see
      RESULTS): 20,137 rows, both ADR-0008 floors passed. **Both cells done — WS1 step 9
      CLOSED.** Unblocks the C3−C1 descriptive bracket (ADR-0008).
- [x] `build_skillssh.py` — installs join. **Gate cleared + crawl done 2026-07-08** (see
      RESULTS). `skills.sh/robots.txt` allows the sitemaps/detail pages (only `/api/*`
      disallowed), `/terms` permits "reasonable use, including caching results on your own
      infrastructure" (read + user sign-off recorded). 19,906 rows, resumable via the on-disk
      HTML cache.

## PRE-REG — WS1 corpus assembly (2026-07-07)

- **Goal:** assemble a deduplicated cross-sectional skill corpus + a version-chain table,
  with per-source provenance, for RQ1–RQ4. This is corpus construction, not a hypothesis
  test; the "results" are counts, dedup/near-dup rates, join rates, license/platform breakdowns.
- **Data + expected upstream counts** (frozen ADR-0005, asserted at run time via `_schema.*_EXPECTED`):
  - `shl0ms/skill-diffs`: diffs 986,515 · diffs_clean 130,631 · skills_initial 664,872 ·
    repos 5,891 · bundled 630,119.
  - `davidliuk/graph-of-skills-data` (skills_2000): 2,000 skills.
  - `amoghacloud/clawskills-intelligence-corpus`: 5,147 stubs (labeled low-quality class).
  - ~~ClawHub live feed: ~549~~ **DROPPED 2026-07-08** (see RESULTS) — narrative hook only.
- **Method:** direct parquet download for skill-diffs (NOT datasets-server row APIs — ADR-0005
  access gotcha); exact dedup by normalized-text SHA256, near-dup via `datasketch` MinHash,
  0.9 Jaccard on 5-gram shingles, seed 42 (D1). Canonical doc per near-dup cluster.
- **Confirms if:** each source's row count matches its `_EXPECTED` (skill-diffs / GOS / slop);
  corpus.parquet has exactly `CORPUS_COLUMNS`; REPORT.md reconciles per-source → merged counts.
- **Would NOT confirm / STOP if:** any asserted upstream count is off (D7 conflict — dataset
  changed under us); near-dup removal exceeds 60% on skill-diffs (D1 fork-explosion → unit of
  analysis becomes the cluster, log it, do not treat near-dups as independent).

## RESULTS

All counts cited from `manifests/*.manifest.json` (never retyped). Newest on top.

### 2026-07-09 16:36 — the-stack rerun COMPLETE: human_baseline.parquet 20,137 rows, WS1 step 9 CLOSED

Rerun of `build_human_baseline.py --github-sample 6000` after the type-safe-write fix
(commit 25740e9) completed clean. Numbers from `human_baseline.parquet.manifest.json`
(sha256 `b2875fd6…`, seed 42, pyarrow 24.0.0, datasets 5.0.0, huggingface_hub 1.19.0, git
`4f9f10d6-dirty`):

- `human_baseline.parquet`: **20,137** rows — **era=pre 14,866** / **era=post 5,271**, both
  **≥ the ADR-0008 5,000/cell floor** (`floor_status_per_era`: pre `true`, post `true`).
  Stack cell: 40,751,875 scanned / 12,612,580 matched / 20,000 sampled; GH cell 6,000 docs
  from 2,251 matched repos (3,210 scanned, 410 no-match/fetch-fail, 549 SKILL.md-repo
  excluded). Pooled 26,000 → English filter (ascii-ratio + stopword heuristic) dropped
  5,863 → 20,137 kept.
- **Incident, resolved:** the first full stream (2026-07-09 13:03 entry below) passed both
  floors but was lost at write time to an `ArrowTypeError` (the-stack's `license_spdx` is
  `list<string>`, not a plain string) — 4h of streaming discarded because the reservoir
  lived only in memory. Fix: type-safe `coerce_cell` write path + a post-stream reservoir
  checkpoint (`stack_reservoir_checkpoint.pkl`, temp state, not DVC-tracked), commit
  25740e9. This rerun streamed the-stack from scratch (checkpoint only helps a *post*-stream
  retry) and wrote clean on the first attempt.
- **Consequence (ADR-0008): both RQ5 cells now exist — the C3−C1 / C2−C1 descriptive
  bracket is UNBLOCKED**, alongside the already-unaffected C3 vs C2 confirmatory contrast.
  **WS1 step 9 is DONE; WS1 is fully closed.**
- **Artifact:** `paper/data/human_baseline.parquet` (DVC-tracked; this rerun's `.dvc`
  pointer replaces yesterday's stale post-only-cell pointer — expected, since the parquet
  is a full overwrite each run).
- **Repro:** `uv run python paper/code/ws1/build_human_baseline.py --github-sample 6000`,
  git commit `4f9f10d6` (dirty at run time), seed 42, packages `datasets==5.0.0`
  `huggingface_hub==1.19.0` `pyarrow==24.0.0` (all from the manifest).

### 2026-07-09 13:03 — the-stack full stream LOST to a write-time bug; type-safe write + checkpoint added, rerun launched

Ran `build_human_baseline.py --github-sample 6000` with HF access now granted (the earlier
gate cleared). The ~3h45m the-stack stream + English filter **completed and passed both
ADR-0008 5k floors** — but the run crashed at write time and the in-memory reservoir was
**not persisted** (no manifest; counts below are read from the crash log, not a manifest):
`/private/tmp/claude-12875/-Users-nbrandizzi-repos-personal-timbro/b87feaa0-208d-4df8-ab94-251c77aab12b/scratchpad/stack_full_run.log`.

- **Stream completed:** scanned 40,751,875 / matched 12,612,580 / sampled 20,000 (cell a);
  GH cell 6,000 docs from 2,251 repos. Pooled 26,000 → English filter kept 20,137.
  **Post-filter floors PASSED: era=pre n=14,866 [OK], era=post n=5,271 [OK]** (both ≥ the
  ADR-0008 5,000/cell floor).
- **Write-time crash (lost the run):** `write_output` did `pa.array(..., type=pa.string())`
  over rows where `license_spdx` is a **list** — the-stack's `max_stars_repo_licenses` is a
  `list<string>` (the GH cell's license is a plain string) → `ArrowTypeError: Expected bytes,
  got a 'list' object`. 4h of stream discarded because the reservoir lived only in memory.
- **Fix (this commit):** (1) type-safe write — `coerce_cell` JSON-encodes list/dict, `str()`s
  everything else (e.g. datetime `last_timestamp`), None passes through; applied at the stack
  row (`license_spdx`, `last_timestamp`) AND belt-and-braces in `write_output` so no schema
  surprise can crash the write again. Coercion audit: only `license_spdx` (list) was the live
  crash; `last_timestamp` guarded defensively; all other cells + the whole GH cell are already
  str/None. (2) Post-stream **reservoir checkpoint** (`stack_reservoir_checkpoint.pkl`, temp
  state — no DVC/manifest): dumped the moment `build_stack_cell` returns, loaded-and-skips the
  stream on restart, so every step after the 4h stream is now retryable for free. (3) Unit
  tests for `coerce_cell` / `write_output` (list license + datetime → valid all-string table)
  and the checkpoint roundtrip; ws1 suite 111 passed. ruff clean.
- **Rerun LAUNCHED** detached (`--github-sample 6000`), streaming from scratch (checkpoint
  only helps a post-stream retry, and the pre-crash reservoir was never persisted); GH cell
  resumes from `human_baseline_gh_cache/`. `human_baseline.parquet` will be overwritten at the
  END of the rerun (expected). Manifest/final counts pending completion.

### 2026-07-09 — footgun: `is_canonical` is a STRING column, not bool

`is_canonical` in `corpus.parquet` is a **string** column with values `"true"`/`"false"`
(`dedup.py` writes strings; `merge.py`'s `string_table` keeps them as strings). Any WS3
filter must compare `== "true"` or explicitly cast to bool at load time — naive truthiness
(e.g. `if row["is_canonical"]`) keeps **all 672,022 rows**, since non-empty strings are
always truthy.

### 2026-07-08 — RQ5 human baseline: post-2023 cell built (5,161 rows); pre-2023 cell blocked on HF gate

Ran `build_human_baseline.py --skip-stack --github-sample 6000` (WS1 step 9, ADR-0008).
Numbers from `human_baseline.parquet.manifest.json` (sha256 `991c680e…`, seed 42):

- `human_baseline.parquet`: **5,161** rows, all `era=post` — **≥ the ADR-0008 5k/cell
  floor** (`floor_status_per_era.post: true`). 6,001 docs fetched from 2,185 matched /
  3,105 scanned repos (min_stars 5, created/updated ≥ 2023-01-01); **840** dropped by the
  English filter. SKILL.md-repo exclusion enforced on the full recursive tree per repo;
  post-hoc invariant check: seeded 100-repo sample of the delivered 1,970 repos → 0 carry
  a SKILL.md. (A stale `n_repos_skill_md_excluded: 0` diagnostic in the first manifest was
  never wired to the check — cosmetic; replaced by marker-based counters in code.)
- **Pre-2023 the-stack cell BLOCKED:** `bigcode/the-stack` is HF-gated, no local token
  (`HfFolder.get_token()` → None). Streaming + seeded reservoir sampling (target 20k)
  implemented and untested-on-live; retry = accept gate + `HF_TOKEN` + rerun (GH cell
  resumes from `human_baseline_gh_cache/`). Manifest records the cell as `blocked`, not
  zero-success. **Consequence (ADR-0008): C3 vs C2 confirmatory contrast UNAFFECTED;
  C3−C1 / C2−C1 descriptive bracket pending the unblock.**
- **Flagged implementation choices (not in ADR-0008, logged per its deviation rule):**
  English filter = ascii-ratio + stopword heuristic (NOT langdetect — no new deps),
  applied identically to both cells; `MAX_DOCS_PER_REPO=5` diversity cap (a smoke-test
  monorepo yielded 172 README/CONTRIBUTING files; root-level/shortest-path preferred);
  GH sample sized 6,000 (API budget ~1.4 s/repo) — top-up = rerun with higher
  `--github-sample`, cache-resumable; D1 dedup treatment deferred downstream to WS3
  step 7 (dedup.py owns fixed `src_*` inputs; ADR-0008 requires dedup before analysis,
  not at build time). DVC-tracked.

### 2026-07-08 — machine-authored cell built (ADR-0009, exploratory): src_machine_cell.parquet

Ran `build_machine_cell.py` (WS1 step 10). Numbers from
`src_machine_cell.parquet.manifest.json` (sha256 `28f022cc…`):

- **587** rows total: `zhang-ziao/SkillFlow-exp-skills` **582** + `Qwen-Applications/
  Trace2Skill` released_skills **5** (4 evolved variants + the human-written Anthropic
  xlsx baseline, byte-identical frontmatter to the two "combined" deepening variants —
  confirming it as their evolution source). 18 columns = `CORPUS_COLUMNS` +
  `generator_model` / `domain` / `task_family`. 11 distinct generator models; 20/20 task
  families mapped to the 5 SkillFlow domains (0 unmapped). 0 empty bodies.
- **Expected-count deviation, resolved loud:** ADR-0009's "~598" counts `index.json`
  entries; only **582** carry `has_skill_md=True` (verified live 2026-07-08). Asserted
  against 582 (`SKILLFLOW_EXP_SKILLS_EXPECTED` in `_schema.py`, reasoning documented
  inline) — the assert targets text-bearing rows, not raw index entries.
- Domain labels: static 20-family → 5-domain table transcribed from `SkillFlow-Task`'s
  README (task.toml has no domain field). Name-collision guard honored (ADR-0009):
  `beita6969/SkillFlow-Dataset` never touched, IDs pinned exact. License: SkillFlow rows
  `license_spdx` null (unspecified upstream); Trace2Skill evolved `Apache-2.0`; baseline
  `Proprietary` (its own frontmatter). Standalone exploratory cell — NOT merged into
  corpus.parquet (ADR-0009: never confirmatory; WS3 step 8 consumes it directly).
  DVC-tracked.

### 2026-07-08 — merge.py full run: corpus.parquet assembled (ADR-0010 entry-level join)

Ran the reworked `merge.py` (ADR-0010; sonnet-implemented, opus-reviewed APPROVE) over the
three pooled sources + `dedup_map.parquet` + `skillssh_meta.parquet`. Numbers from
`corpus.parquet.manifest.json` (sha256 `5b7f02f0…`, pyarrow 24.0.0, git `e73139c`):

- `corpus.parquet`: **672,022** rows (skill_diffs 664,875 + GOS 2,000 + slop 5,147; 0 pooled
  skill_ids missing from dedup_map). **227,407** canonical rows. All 15 `CORPUS_COLUMNS`.
- **Install join (entry-level, ADR-0010):** `n_matched_rows` **12,428** → `n_entries_matched`
  **9,686** labeled rows (1.28× row inflation killed); `n_clusters_matched` **9,702**;
  canonical-only would have recovered **5,667** (the −41% ADR-0010 avoided). Reproduces the
  consult inspection exactly. Ceiling rate **0.8366** (9,686 / 11,578 repo-overlap triples;
  the ~15% gap = temporal-skew skills, see holdout). Labeled share of skill_diffs rows
  0.0146 (the ≤1.74% coverage caveat, now exact; manifest key
  `install_labeled_share_skill_diffs` — renamed from a mislabeled
  `install_join_rate_present` and REPORT/manifest regenerated same day, same output sha).
- `rq2_holdout_candidates.parquet`: **1,704** rows (manifest; ≈ the probe's ~1,701),
  temporally out-of-sample RQ2 candidates. DVC pointers committed for both artifacts.

### 2026-07-08 — D1 consult resolved: RQ2 join representative = entry-level, NOT canonical-only (ADR-0010)

Ad-hoc inspection (decision-support, not a builder manifest — back with a committed probe
before any figure enters the manuscript) of the install join under the fired D1 consequence.
Row-level join matches **12,428** skill_diffs rows = only **9,686** distinct loose
`(owner,repo,name)` entries (**1.28×** row over-count from same-key duplicate rows, not
cross-repo forks); matched near-dup clusters **9,702** ≈ entries, so near-dup structure
barely collapses the labeled set — and it reproduces the earlier install-join probe
(9,660 exact / 9,874 loose). Canonical-only joining recovers just **5,667** entries
(−41%): `is_canonical` is text-dedup-chosen, install-blind.

- **Decision (ADR-0010):** corpus.parquet keeps all rows + cluster columns; RQ1/RQ3 filter
  `is_canonical`; RQ2 install join dedupes to one representative row per distinct entry
  (cluster-canonical if present, else max `n_revisions`, else smallest `skill_id`); RQ2
  models cluster SEs on `near_dup_cluster_id`; REPORT.md carries the inflation diagnostics.
  Sensitivity check: RQ2 rerun canonical-only.
- **merge.py rework + run:** entry-level join implementation pending (sonnet-dispatched,
  opus-reviewed), then the full merge run.

### 2026-07-08 — dedup full 672k run: D1 FORK-EXPLOSION STOP FIRED

Ran `dedup.py` over the pooled text sources (src_skill_diffs + src_gos + src_slop). The
pre-registered D1 STOP (>60% near-dup removal on skill_diffs) **fired** — as anticipated from
the 67% dataset-shipped fork rate already recorded below. Numbers from
`dedup_map.parquet.manifest.json` (sha256 `0c8f7320…`, datasketch 2.0.0, seed 42):

- `dedup_map.parquet`: **672,022** rows (one per pooled skill; skill_id → near_dup_cluster_id
  / cluster_size / is_canonical). Inputs pinned by sha256 in the manifest.
- **Exact dedup:** 672,022 → **256,376** distinct normalized texts (`exact_removal_rate`
  0.6185). Normalization = lowercase + whitespace-collapse (so folds case/spacing variants,
  not strictly byte-identical).
- **Near-dup (MinHash 0.9 Jaccard, 5-gram word shingles, num_perm=128):** 672,022 →
  **227,407** clusters pooled (`near_dup_removal_rate` 0.6616).
- **D1 trigger — `skill_diffs_near_dup_removal_rate` = 0.6658 > 0.60 → `d1_fork_explosion:
  true`.** Per pre-reg: **unit of analysis becomes the near-dup cluster; near-dups are NOT
  independent samples.** Downstream (merge.py, RQ2/RQ4 modeling) must collapse to canonical /
  cluster-robust — **pending user consult before merge.py runs.**

### 2026-07-08 — weekly-installs re-parse: full-cache run (skillssh_weekly.parquet)

Ran `parse_weekly_installs.py` over the on-disk skills.sh crawl cache (no re-crawl). Live
counts reproduce the frozen pre-freeze inspection exactly, confirming the `,\s+` separator
rule holds across the whole cache.

- `skillssh_weekly.parquet`: **19,906** rows (`skillssh_weekly.parquet.manifest.json`, sha256
  `d64d7395…`, `pyarrow` 24.0.0). One row per resolved `/{owner}/{repo}/{skill}` detail page,
  keyed owner/repo/skill; a WS3-side join artifact (like `skillssh_meta.parquet`), **not** a
  `CORPUS_COLUMNS` field. Every series is exactly 8 values (schema-checked; 0 length
  exceptions). **5** pages no-aria/unparseable (the crawl's unresolved detail pages — matches
  the 19,911 scanned − 19,906), **580** all-zero series (→ `installs_wk_mean` 0.0). 0 mean
  mismatches vs `mean(series)`.
- Fields: `weekly_installs` (8-int list), `installs_wk_mean` (its mean, ADR-0007). Manifest
  records `window_weeks=8`; single crawl anchor 2026-07-08 — state the 8-week window
  limitation wherever the outcome is reported. DVC-tracked (`.dvc` pointer committed; bytes
  local-cache only).

### 2026-07-08 — weekly-installs re-parse: the "9–16-value" series is a thousands-separator artifact

Mandatory pre-freeze inspection (ADR-0007: "the 9–16-value series must be inspected once before
the re-parse is frozen"). Re-scanned all 19,911 cached skills.sh `.body` files for the sparkline
`aria-label="Weekly installs: …"`. 19,906 carry it (5 no-aria = the crawl's unresolved detail
pages). **The earlier "8 vs 9–16 values" split was a parsing artifact, not a real signal:**
skills.sh renders values ≥1,000 with a thousands-separator comma (`1,901`), so a naive
`split(",")` overcounts — `586, 437, 220, 145, 205, 177, 235, 1,901` is **8** weekly values
(last = 1901), not 9. Splitting on `", "` (comma + whitespace) and stripping intra-value commas
yields **exactly 8 values on 19,906/19,906 pages — 0 exceptions, 0 non-integer tokens**. The
n=16 spike (314 pages) is simply series where all 8 values are ≥1,000.

- **FROZEN parse rule:** value separator = regex `,\s+`; within each token strip `,` and parse
  int. The sparkline is **always an 8-week window** (single crawl anchor 2026-07-08 — state the
  window limitation wherever the outcome is reported). **580 / 19,906** series are all-zero.
- **Outcome fields** (`parse_weekly_installs` → `skillssh_weekly.parquet`, keyed owner/repo/skill,
  a WS3-side join artifact like `skillssh_meta.parquet`, NOT a `CORPUS_COLUMNS` field):
  `weekly_installs` = the 8-int series; `installs_wk_mean` = its mean (ADR-0007 def; all-zero
  → 0.0). ~~⚠ naming flag~~ **RESOLVED 2026-07-08 (user decision, ADR-0007):** estimator =
  mean of the full 8-week series, column renamed `installs_wk_recent` → `installs_wk_mean`
  (code + tests updated; 10/10 pass).

### 2026-07-08 — RQ2 install-join key: frontmatter-name viability + miss breakdown

Ad-hoc probe (`skillssh_meta.parquet` × `src_skill_diffs.parquet`, both committed corpus
parquets; decision-support, not a builder manifest — if any figure enters the manuscript,
back it with a committed probe first). Repo overlap = **816** owner/repo (reproduces the
overlap finding below). skills.sh keys on `owner/repo/skill` (the repo folder); skill-diffs
dropped `skill_path`, so the only corpus-side skill key is the `frontmatter_json` `name:`
field. Question: does a name-based join recover skill-level installs (the primary RQ2 outcome)?

Of the **11,578** skills.sh triples in the 816 overlapping repos:

| count | share | category |
|------:|------:|----------|
| 9,660 | 83.4% | exact frontmatter-`name` match |
| 1,701 | 14.7% | skill **absent from the skill-diffs snapshot** — skills.sh crawl (2026-07-08) postdates the HF snapshot; no text to join onto, unjoinable by construction |
| 214 | 1.8% | matches only after `[a-z0-9]` normalization (hyphen/underscore/space/case; e.g. ss `anomaly-detection` vs fm `anomaly detection`) |
| 3 | 0.0% | repo's SKILL.md files carry no `name:` frontmatter (`astral-sh/claude-code-plugins`) |

- **The apparent 83% "loss" is mostly the wrong denominator.** The 14.7% are skills we hold
  no text for (temporal skew) → excluded from RQ2 regardless of join quality. Against
  **corpus-present** skills, exact-name recovers **9,660 / 9,874 = 97.8%**; loose `[a-z0-9]`
  normalization recovers **9,874 / 9,874 ≈ 100%** (the 3 no-frontmatter skills aside).
- **Decision — loose join key (D-adjacent, method):** `merge.py` joins installs on
  `_join_key(s) = re.sub(r"[^a-z0-9]", "", s.lower())` applied to `owner`, `repo`, and the
  skill/name on both sides — recovers the +214 for one regex. REPORT.md reports **two** rates:
  vs corpus-present skills (~100%, the RQ2 coverage number) and vs the repo-overlap ceiling
  (9,874 / 11,578 = 85.3%, with the 14.7% temporal-skew gap named). **No `build_skill_diffs`
  re-run** — `skill_path` is not needed; frontmatter `name` suffices.
- **Holdout artifact:** `merge.py` also emits `rq2_holdout_candidates.parquet` — the ~1,701
  skills.sh triples in overlapping repos that carry an `installs` label but match no corpus
  text (a free byproduct of the join). Candidate *temporally out-of-sample* RQ2 test set:
  train on the skill-diffs∩skills.sh join, test on these newer skills (their SKILL.md text
  fetched from GitHub in WS3 — targeted known `owner/repo/skill` paths, NOT the enumeration
  crawl rejected below).
- **OPEN PROBLEM — concept drift, not just a temporal holdout (flagged 2026-07-08, NB):** the
  1,701 are *newer* skills and the field moves fast, so they likely carry **new directions** —
  topics, capabilities, and instruction dialects absent from the training snapshot. So the
  holdout confounds *temporal generalization* with *distribution shift*: a model degrading on
  it may be meeting genuinely novel skill types, not failing features. WS3 must (a) characterize
  the holdout's topic/dialect novelty vs training BEFORE scoring it, and (b) report degradation
  as a drift signal, not fold it into plain test error. The same caveat qualifies any RQ1
  "dialect stability over time" claim.

### 2026-07-08 — source-overlap decisions (drop ClawHub; RQ2 coverage; no GitHub scrape)

Descriptive figures below are from an ad-hoc overlap check on the committed corpus
parquets + the live ClawHub feed (`/v1/feeds/skills`, fetched 2026-07-08); repo-level
(unit = GitHub `owner/repo`), decision-support only — not a builder manifest. If any of
these enter the manuscript, back them with a committed probe first.

- **ClawHub DROPPED as a data source.** The only robots-allowed bulk feed
  (`/v1/feeds/skills`) is a *verified-publisher allowlist*: 660 entries, no `downloads`/
  install field at all, and content not inline. Its 329 `public-github` entries resolve to
  just **2 vendor monorepos** — `nvidia/skills` (231) + `aws/agent-toolkit-for-aws` (98) —
  both already indexed by skills.sh, `nvidia/skills` also in skill-diffs. The other 331
  (`public-clawhub`) are only reachable via `/api/*` (robots-disallowed). So ClawHub adds
  ~2 vendor repos of near-redundant content and **zero adoption signal**. Kept only as the
  ClawHavoc narrative hook. (The full ~52k ClawHub registry has no sanctioned bulk access;
  adoption numbers cited in the wild are third-party scrapes.)
- **RQ2 install-coverage is small — selection-bias caveat (pre-registered robustness item).**
  skills.sh installs (`skillssh_meta.parquet`, 19,906 skills / 2,452 repos) overlap
  skill-diffs on **816 repos = 13.9% of the 5,887 text-corpus repos**. Of skills.sh's 19,906
  skills, 11,578 (58%) sit in a shared repo → **install-labeled text skills ≤ ~11,578 = ≤1.74%
  of the 664,875-skill corpus** (repo-level ceiling; exact skill-level join lands in `merge.py`).
  n≈11.6k is ample statistical power; the risk is **generalizability** — skills.sh is a curated
  directory, so labeled skills skew toward promoted ones. **Actions:** report the join/coverage
  rate as RQ2's denominator; run a selection-bias check (labeled vs unlabeled on length /
  quality / platform); use repo-level `stars` (already present, 90% coverage) as a
  breadth-coverage adoption proxy to cross-check the install-based RQ2 result.
- **No direct GitHub SKILL.md scrape.** skill-diffs already IS the GitHub crawl (664,875
  skills, full history); GitHub Code Search can't enumerate more (1,000-result cap, rate
  limits) and would be near-fully redundant. Stats we'd want are mostly already shipped
  (`stars` 90%, dates 100%, `n_revisions` 100%, `license_spdx` 39%). An optional
  `build_github_stats.py` (5,887 repos → `forks` + license backfill, repo-level/coarse) is
  **parked** — polish, not a blocker, add only if `forks` is wanted as a covariate.

### 2026-07-08 — skill-diffs anchor corpus (both tables)

- **Cross-sectional** `src_skill_diffs.parquet`: **664,875** rows / 664,875 distinct skills
  (`src_skill_diffs.parquet.manifest.json`, git `e34117f`). Upstream D7 asserts all passed:
  skills_initial 664,872 · diffs_clean 130,631 · repos 5,891 · bundled 630,119.
  - Rebuilt via `--cross-only` after the CRLF frontmatter fix (`_text.extract_frontmatter`,
    `[\r\n]+` fences). Frontmatter now parsed on 637,772 rows (95%). Residual unstripped
    (`frontmatter_json` null AND body opens with `---`) = 1,018 rows (0.15%); of those only
    159 are cleanly fixable (121 leading-whitespace, 38 close-at-EOF), rest are genuine
    non-frontmatter `---` rules. 0 valid `---<fm>---` docs fail → not a regex bug; left as-is.
- **Version chains** `skill_diffs_chains.parquet`: **289,145** version-rows across **218,626**
  chains (`skill_diffs_chains.parquet.manifest.json`). 15,306 chains split on a broken link;
  **446,249** fork skills excluded. RQ4-eligible (≥3 versions): **14,388** — well above the
  ADR-0005 <1,000 "descriptive-only" floor, so RQ4 stands as a real analysis.
  - **Fork-explosion note (D1-adjacent):** 446,249 / 664,875 = **67%** of skills are
    non-canonical cross-repo copies (dataset-shipped `skill_cluster_id`, Jaccard≥0.7). This is
    the RQ4 fork-exclusion filter, NOT the pre-registered D1 MinHash near-dup collapse (0.9
    Jaccard, runs in `dedup.py`, not yet run) — but the magnitude flags that D1's >60%
    fork-explosion clause is live and must be checked when dedup runs.

### 2026-07-08 — GOS + slop sources

- `src_gos.parquet`: **2,000** rows (`src_gos.parquet.manifest.json`) — matches
  `GOS_EXPECTED_SKILLS`.
- `src_slop.parquet`: **5,147** rows (`src_slop.parquet.manifest.json`) — matches
  `SLOP_EXPECTED_STUBS`.

### 2026-07-08 — skills.sh installs crawl (complete)

- `skillssh_meta.parquet`: **19,906** rows (`skillssh_meta.parquet.manifest.json`, sha256
  `0e126f43…`), one per `/{owner}/{repo}/{skill}` detail page. **19,610 (98.5%)** carry an
  installs count (`interactionStatistic.userInteractionCount`); min 6 / median 592 / max
  2,392,667. `stars`, `first_seen`, `audit_verdict` are all null — not in the page JSON-LD
  (confirmed pre-crawl). 19,910 detail pages attempted (4 unresolved after retries); ~53
  `/api/*` sitemap entries filtered up front (robots-disallowed). Crawl ran at ≤2 req/s off
  the on-disk HTML cache (fully resumable). Join into `corpus.parquet` happens in `merge.py`.

### 2026-07-08 — skills.sh parser fix (pre-crawl validation)

- Detail-page URLs are `/{owner}/{repo}/{skill}` (no `/skills/` prefix); the original regex
  matched 0 live pages, which would have made the ~20K-page crawl yield an empty table. Fixed
  + unit-tested; verified on real cached pages: **671/671 extract installs**
  (`interactionStatistic.userInteractionCount`; min 214 / median 997 / max 34,613). `stars`,
  `first_seen`, `audit_verdict` are NOT in the JSON-LD → null. Final `skillssh_meta.parquet`
  count pending crawl completion.
