# ADR-0010 — D1 consequence: cluster unit of analysis + RQ2 install-join representative

- **Status:** accepted (2026-07-08). Implements the pre-registered D1 STOP consequence
  (WS1 LEDGER pre-reg 2026-07-07); does not amend the pre-reg — the branch was registered,
  this records the implementation.
- **Context:** the D1 fork-explosion STOP fired on the full 672k dedup run
  (`skill_diffs_near_dup_removal_rate` 0.6658 > 0.60; `dedup_map.parquet.manifest.json`).
  Pre-reg consequence: unit of analysis becomes the near-dup cluster; near-dups are NOT
  independent samples. The user-consult inspection (2026-07-08, ad-hoc probe —
  decision-support; back with a committed probe before any figure enters the manuscript)
  showed the instinctive implementation (collapse everything to `is_canonical`) is wrong
  for RQ2:
  - Row-level install join matches **12,428** skill_diffs rows but only **9,686** distinct
    loose `(owner, repo, name)` entries — a **1.28×** over-count from same-key duplicate
    rows, not cross-repo forks.
  - Matched near-dup clusters (**9,702**) ≈ distinct entries (**9,686**): near-dup structure
    barely collapses the labeled set.
  - Canonical-only joining recovers just **5,667** distinct entries (−41%): `is_canonical`
    was chosen for text dedup (source rank → most revisions → smallest id) and is
    install-blind — the cluster's canonical rep is usually not the fork living in the
    skills.sh-indexed repo.

## Decision

1. **corpus.parquet keeps every pooled row** plus `near_dup_cluster_id` / `is_canonical`
   (provenance; no row drops in the merged artifact).
2. **RQ1/RQ3 (descriptive/dialect) analyses filter `is_canonical`** — unit = cluster via
   its text-canonical representative.
3. **RQ2 install join dedupes to one representative row per distinct loose
   `(owner, repo, name)` entry** — the install-bearing unit — instead of labeling every
   matching row. Representative within an entry, deterministic: cluster-canonical row if
   present, else max `n_revisions`, else smallest `skill_id`. Recovers the full ~9,686
   labeled entries (matches the LEDGER install-join probe: 9,660 exact / 9,874 loose).
4. **RQ2 models cluster standard errors on `near_dup_cluster_id`.** Entries and clusters
   are ~1:1 in the labeled set but not exactly (entries spanning 2+ clusters exist, and a
   cluster spanning 2+ labeled entries means non-independent labels); clustering SEs
   satisfies the pre-reg "not independent" clause literally.
5. **REPORT.md reports the inflation diagnostics**: matched rows (row-level), distinct
   entries matched, distinct clusters matched, canonical-only matched count — so the 28%
   over-count and the −41% canonical loss stay visible.

## Consequences

- `merge.py` `join_installs` changes from label-all-matching-rows to
  label-representative-row-per-entry (+ unit tests). Run unblocked once reviewed.
- RQ4 is unaffected — its fork exclusion happens upstream in the chain builder
  ([ADR-0005](0005-rq4-preregistration.md)).
- Pre-registered sensitivity check for RQ2: rerun canonical-only (the 5,667-entry set); a
  flip would indicate the cluster/fork structure drives the result.
