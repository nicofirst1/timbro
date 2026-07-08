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
- [ ] `dedup.py` — exact + MinHash near-dup collapse (D1). Not yet written.
- [ ] `merge.py` — corpus.parquet + REPORT.md. Not yet written.
- [x] `build_skillssh.py` — installs join. **Gate cleared + crawl done 2026-07-08** (see
      RESULTS). `skills.sh/robots.txt` allows the sitemaps/detail pages (only `/api/*`
      disallowed), `/terms` permits "reasonable use, including caching results on your own
      infrastructure" (read + user sign-off recorded). 19,906 rows, resumable via the on-disk
      HTML cache.

## PRE-REG — WS1 corpus assembly (2026-07-07)

- **Goal:** assemble a deduplicated cross-sectional skill corpus + a version-chain table,
  with per-source provenance, for RQ1–RQ4. This is corpus construction, not a hypothesis
  test; the "results" are counts, dedup/near-dup rates, join rates, license/platform breakdowns.
- **Data + expected upstream counts** (frozen §8b, asserted at run time via `_schema.*_EXPECTED`):
  - `shl0ms/skill-diffs`: diffs 986,515 · diffs_clean 130,631 · skills_initial 664,872 ·
    repos 5,891 · bundled 630,119.
  - `davidliuk/graph-of-skills-data` (skills_2000): 2,000 skills.
  - `amoghacloud/clawskills-intelligence-corpus`: 5,147 stubs (labeled low-quality class).
  - ~~ClawHub live feed: ~549~~ **DROPPED 2026-07-08** (see RESULTS) — narrative hook only.
- **Method:** direct parquet download for skill-diffs (NOT datasets-server row APIs — §8b
  access gotcha); exact dedup by normalized-text SHA256, near-dup via `datasketch` MinHash,
  0.9 Jaccard on 5-gram shingles, seed 42 (D1). Canonical doc per near-dup cluster.
- **Confirms if:** each source's row count matches its `_EXPECTED` (skill-diffs / GOS / slop);
  corpus.parquet has exactly `CORPUS_COLUMNS`; REPORT.md reconciles per-source → merged counts.
- **Would NOT confirm / STOP if:** any asserted upstream count is off (D7 conflict — dataset
  changed under us); near-dup removal exceeds 60% on skill-diffs (D1 fork-explosion → unit of
  analysis becomes the cluster, log it, do not treat near-dups as independent).

## RESULTS

All counts cited from `manifests/*.manifest.json` (never retyped). Newest on top.

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
  §8b <1,000 "descriptive-only" floor, so RQ4 stands as a real analysis.
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
