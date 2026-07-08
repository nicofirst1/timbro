# ADR-0006 — Drop ClawHub as a data source; no direct GitHub scrape

- **Status:** accepted (2026-07-08). Supersedes the ClawHub row of
  [ADR-0003](0003-corpus-sources.md).
- **Context:** the 2026-07-04 probe assumed ClawHub's sanctioned feed would contribute 549
  full-text skills plus a `downloads` adoption signal. The WS1 build-time probe (LEDGER
  2026-07-08, repo-level overlap check on committed corpus parquets) found otherwise.

## Decision

- **ClawHub is dropped as a data source.** The only robots-allowed bulk feed
  (`/v1/feeds/skills`) is a *verified-publisher allowlist*: 660 entries, **no downloads/install
  field at all**, content not inline. Its 329 `public-github` entries resolve to just 2 vendor
  monorepos (`nvidia/skills`, `aws/agent-toolkit-for-aws`) — both already indexed by skills.sh,
  one also in skill-diffs. The other 331 are only reachable via `/api/*` (robots-disallowed).
  Net contribution: ~2 redundant vendor repos, zero adoption signal. Kept only as the
  ClawHavoc narrative hook in the manuscript. (The full ~52k ClawHub registry has no
  sanctioned bulk access; adoption numbers cited in the wild are third-party scrapes.)
- **No direct GitHub SKILL.md scrape.** skill-diffs already IS the GitHub crawl (664,875
  skills, full history); GitHub Code Search can't enumerate more (1,000-result cap, rate
  limits) and would be near-fully redundant. An optional `build_github_stats.py` (repo-level
  `forks` + license backfill) is parked — polish, not a blocker.

## Consequences

- ClawHub `downloads` leaves the confirmatory RQ2 outcome list
  ([ADR-0007](0007-temporal-confounds-d9.md) records the replacement outcome set).
- RQ2 adoption signal rests on skills.sh installs (+ weekly series) and repo-level stars;
  the ≤1.74% install-coverage selection-bias caveat and its mitigations are logged in the
  WS1 LEDGER (2026-07-08) and PLAN.md §6 risks.
- D8's "use marketplace category metadata where present (ClawHub categories)" fallback is
  moot for ClawHub-sourced rows; domain labels come from the TF-IDF k-means path.
