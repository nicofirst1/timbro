# ADR-0003 — Corpus sources

- **Status:** accepted (empirically probed 2026-07-04; skills.sh row corrected 2026-07-08).
  ClawHub row superseded by [ADR-0006](0006-drop-clawhub.md).
- **Context:** every candidate source was empirically probed (schemas, counts, licenses,
  crawl permissions) before being baked into the plan. Formerly §3 of the master plan.

## Decision

| Source | What it is | Unique full-text skills | Outcome proxies | License |
|---|---|---|---|---|
| HF `shl0ms/skill-diffs` (**schema verified 2026-07-07 via datasets-server**) | Full SKILL.md snapshots per commit, **5,891 repos across 4 platforms**: `diffs.parquet` 986,515 commit-level rows / 36 cols; `diffs_clean.parquet` 130,631 true before/after pairs; `skills_initial.parquet` 664,872 creation snapshots; `repos.parquet` 5,891; `bundled.parquet` 630,119 sibling files at HEAD | **664,872** initial skill snapshots (986,515 commit-level rows; 130,631 clean pairs) | repo `stars` + `license_spdx` in `repos.parquet` (join on repo); per-edit `intent_class`/`quality_score` labels included; **no installs** | per-record/per-repo `license_spdx` — filter per row |
| HF `davidliuk/graph-of-skills-data` | Paper-curated benchmark libraries (`skills_2000.tar.gz` is the superset). **Provenance confirmed artifact (verified 2026-07-07, MIT):** the HF dataset card reciprocally cites arXiv:2604.05333 (Dawei Liu et al.), the paper's GitHub repo links the dataset; skill-library configs 200–2000 | 2,000 (substantive, ~6KB avg) | none | MIT |
| ~~ClawHub live registry~~ | **DROPPED 2026-07-08 — [ADR-0006](0006-drop-clawhub.md)**; kept as ClawHavoc narrative hook only | ~~549~~ | ~~downloads~~ (feed carries none) | — |
| HF `amoghacloud/clawskills-intelligence-corpus` | 5,147 near-identical templated stubs ("SISR" boilerplate, ~400B each) | ~5.1K **low-quality stubs** | none | MIT |
| skills.sh marketplace (probed 2026-07-04; corrected 2026-07-08) | Ling et al.'s source. Public sitemaps enumerate **~20,000** skill URLs (`owner/repo/skill`; ~53 are stray `/api/*` entries to skip). Detail pages (robots-allowed) embed JSON-LD carrying **total installs** (`userInteractionCount`) — but NOT stars/first-seen/audit-verdict (corrected 2026-07-08: those are not in the structured data; the crawl yields them null). **Full SKILL.md text IS present** — rendered in the Next.js hydration payload (`__next_f`), the same content as skill-diffs (corrected 2026-07-08: the 2026-07-04 "466-char preview / full text unavailable" note was wrong — it missed the JS-hydrated body; verified by heading-overlap against skill-diffs). Never call the API (Vercel-OIDC-gated, robots-disallowed) | 0 used directly — **join installs onto skill-diffs texts via the owner/repo/skill path**; skills.sh's rendered text is a possible fallback for skills absent from skill-diffs | **skill-level total installs** (not per-platform; per-platform counts exist nowhere) + **weekly-install series** in the sparkline aria-label ([ADR-0007](0007-temporal-confounds-d9.md)) | robots.txt allows pages/sitemaps (only `/api/*` disallowed); `/terms` read + cleared 2026-07-08 (permits reasonable cached use) |

Corpus conclusions baked into the plan:

- **skill-diffs anchors the corpus** (2–3 orders of magnitude larger than everything else).
- The earlier "~13,700 ClawHub skills" claim is stale/wrong: live ClawHub = 549. Larger numbers
  referred to skills.sh or a pre-purge registry. Do not repeat the 13.7K figure.
- The slop-stub corpus is **kept as a labeled low-quality class** — a validation set for whether
  our features separate templated slop from organic documentation (on-brand for Timbro).
- Skill-level installs exist only on skills.sh (~20K per our 2026-07-04 sitemap probe; Ling
  et al. report 40,285 listings in their earlier crawl). GitHub stars are
  repo-level (many skills per repo → attenuated signal; model with repo random effects or
  restrict to single-skill repos for the star analysis).
- **Redistribute derived feature vectors, never raw skill texts.** skill-diffs is mixed-license
  (per-record SPDX).
- *(Added 2026-07-07)* Additional corpus-landscape datapoint for the narrative:
  liu2026-skillscanwild analyzed **31,132 skills across skills.rest + skillsmp.com** (Dec 2025
  crawl) — two further marketplaces not currently among our corpus sources.

## Consequences

- WS1 build recipes in PLAN.md; manifest-backed build results in `paper/code/ws1/LEDGER.md`
  (crawl complete 2026-07-08: 19,906 skills.sh rows, 98.5% with installs).
- ClawHub reconciliation note (26,502 in hu2026-clawhub's March crawl vs ~549 live — plausibly
  the post-ClawHavoc purge; plausible-not-confirmed) must be reconciled explicitly in the
  manuscript.
