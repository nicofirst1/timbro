# WS1 ledger — corpus assembly

Canonical results ledger for WS1 (experiment-discipline §4). Numbers are cited from
`manifests/*.manifest.json` / `REPORT.md`, never retyped. Newest on top.

## STATUS

- [x] `build_skill_diffs.py` — anchor corpus (cross-sectional + version-chain tables). Done
      2026-07-08 (see RESULTS). Cross-sectional rebuilt via `--cross-only` after the CRLF
      frontmatter fix; chains built via `--chains-only`.
- [x] `build_gos.py` — graph-of-skills 2000. Done.
- [✗] `build_clawhub.py` — **DROPPED as a data source 2026-07-08** (see RESULTS). Not built.
      ClawHub kept as a narrative hook only (ClawHavoc purge).
- [x] `build_slop.py` — labeled low-quality stubs. Done.
- [~] `dedup.py` — exact + MinHash near-dup collapse (D1). **Written + unit-tested** (TDD,
      ponytail-reviewed) 2026-07-08. Emits a compact `dedup_map.parquet` (skill_id →
      near_dup_cluster_id / cluster_size / is_canonical), not a text copy. MinHash 0.9 Jaccard
      enforced by an explicit `jaccard() >= 0.9` post-filter on LSH candidates (LSH banding
      alone only approximates). **Full 672k-row run PENDING** — will surface the live D1 >60%
      fork-explosion STOP check.
- [~] `merge.py` — corpus.parquet + REPORT.md + `rq2_holdout_candidates.parquet`. **Written +
      unit-tested** (TDD, ponytail-reviewed) 2026-07-08. Loose install-join key
      (`[a-z0-9]`-normalized owner/repo/name). corpus.parquet is exactly the 15 `CORPUS_COLUMNS`
      (skill_diffs sibling cols stay in `src_skill_diffs.parquet`). **Run PENDING** — needs
      `dedup_map.parquet` first.
- [x] `parse_weekly_installs` — re-parse the cached skills.sh HTML for the sparkline
      weekly-install series. **Written + unit-tested** (ponytail-reviewed) 2026-07-08.
      Pre-freeze inspection DONE: the "9–16-value" series was a thousands-separator artifact —
      the sparkline is always an 8-week window; frozen separator `,\s+` yields 8 values on
      19,906/19,906 (see RESULTS). Adds `weekly_installs` + `installs_wk_mean` (mean of the
      series; primary RQ2 outcome per ADR-0007; renamed from `installs_wk_recent` after the
      naming flag was resolved 2026-07-08 — estimator unchanged, tests pass post-rename) →
      `skillssh_weekly.parquet` (owner/repo/skill key, WS3-side join artifact). **Run done
      2026-07-08** (see RESULTS) — 19,906 rows, live counts reproduce the pre-freeze inspection.
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
