# WS1 ledger — corpus assembly

Canonical results ledger for WS1 (experiment-discipline §4). Numbers are cited from
`manifests/*.manifest.json` / `REPORT.md`, never retyped. Newest on top.

## PENDING

- [ ] `build_skill_diffs.py` — anchor corpus (cross-sectional + version-chain tables)
- [ ] `build_gos.py` — graph-of-skills 2000
- [ ] `build_clawhub.py` — live ClawHub feed (~549)
- [ ] `build_slop.py` — labeled low-quality stubs
- [ ] `dedup.py` — exact + MinHash near-dup collapse (D1)
- [ ] `merge.py` — corpus.parquet + REPORT.md
- [ ] **GATED** `build_skillssh.py` — installs join. **Blocked on:** (a) read `skills.sh/terms`
      and confirm crawling is permitted; (b) explicit user sign-off (≈3h crawl of ~20K pages,
      §5.3/§6 guardrails). Code may be written; the crawl must NOT run until both clear.

## PRE-REG — WS1 corpus assembly (2026-07-07)

- **Goal:** assemble a deduplicated cross-sectional skill corpus + a version-chain table,
  with per-source provenance, for RQ1–RQ4. This is corpus construction, not a hypothesis
  test; the "results" are counts, dedup/near-dup rates, join rates, license/platform breakdowns.
- **Data + expected upstream counts** (frozen §8b, asserted at run time via `_schema.*_EXPECTED`):
  - `shl0ms/skill-diffs`: diffs 986,515 · diffs_clean 130,631 · skills_initial 664,872 ·
    repos 5,891 · bundled 630,119.
  - `davidliuk/graph-of-skills-data` (skills_2000): 2,000 skills.
  - `amoghacloud/clawskills-intelligence-corpus`: 5,147 stubs (labeled low-quality class).
  - ClawHub live feed: ~549 (drift allowed — record actual, no hard assert).
- **Method:** direct parquet download for skill-diffs (NOT datasets-server row APIs — §8b
  access gotcha); exact dedup by normalized-text SHA256, near-dup via `datasketch` MinHash,
  0.9 Jaccard on 5-gram shingles, seed 42 (D1). Canonical doc per near-dup cluster.
- **Confirms if:** each source's row count matches its `_EXPECTED` (skill-diffs / GOS / slop);
  corpus.parquet has exactly `CORPUS_COLUMNS`; REPORT.md reconciles per-source → merged counts.
- **Would NOT confirm / STOP if:** any asserted upstream count is off (D7 conflict — dataset
  changed under us); near-dup removal exceeds 60% on skill-diffs (D1 fork-explosion → unit of
  analysis becomes the cluster, log it, do not treat near-dups as independent).

## RESULTS

_(none yet — builders pending)_
