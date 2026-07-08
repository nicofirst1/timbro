# WS1 corpus assembly — REPORT

## Per-source row counts

| source | rows | canonical |
|---|---:|---:|
| skill_diffs | 664875 | 0 |
| graph_of_skills | 2000 | 0 |
| slop_stub | 5147 | 0 |

## Dedup (cited from dedup_map.parquet.manifest.json, not recomputed)

- exact_removal_rate: 0.6185005848022833
- near_dup_removal_rate: 0.6616078045064001
- n_exact_classes: 256376
- n_near_dup_clusters: 227407
- d1_fork_explosion: True

## Platform breakdown

- None: 7147
- claude_skill: 420634
- hermes_skill: 54636
- openclaw_skill: 87078
- opencode_skill: 102527

## License breakdown

- MIT: 195560
- None: 403372
- AGPL-3.0: 4334
- Apache-2.0: 31741
- NOASSERTION: 33200
- BSD-3-Clause: 528
- GPL-3.0: 2157
- CC0-1.0: 451
- Unlicense: 166
- CC-BY-SA-4.0: 146
- CC-BY-4.0: 207
- MPL-2.0: 16
- EUPL-1.2: 10
- EPL-2.0: 41
- UPL-1.0: 30
- MIT-0: 7
- GPL-2.0: 9
- BSD-2-Clause: 14
- ISC: 22
- 0BSD: 1
- WTFPL: 4
- LGPL-2.1: 6

## Installs join (RQ2)

- n_skill_diffs: 664875
- n_installs_matched: 9686
- n_matched_rows (row-level, pre-dedup diagnostic): 12428
- n_entries_matched (distinct keys labeled): 9686
- n_clusters_matched (distinct near_dup_cluster_id over matched rows): 9702
- n_canonical_entries_matched (canonical-only would recover): 5667
- install_labeled_share_skill_diffs (labeled entries / all skill_diffs rows): 0.01456815190825343
- install_join_rate_ceiling (vs repo-overlap ceiling): 0.8365866298151667
- repo_overlap: 816
- holdout_n (rq2_holdout_candidates.parquet): 1704

## dedup_map coverage

- pooled skill_ids absent from dedup_map: 0
