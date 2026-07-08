"""Canonical corpus schema — the single source of truth for column names.

Every builder emits a per-source parquet; dedup.py + merge.py fold them into
paper/data/corpus.parquet with exactly CORPUS_COLUMNS. Fields a source lacks are
left null (see paper/README.md §4 WS1 step 6).
"""

# Final merged corpus.parquet columns (§4 WS1 step 6)
CORPUS_COLUMNS = [
    "skill_id",
    "source",
    "platform",
    "text",
    "frontmatter_json",
    "repo",
    "stars",
    "downloads",
    "installs",
    "created_at",
    "updated_at",
    "license_spdx",
    "n_revisions",
    "near_dup_cluster_id",
    "is_canonical",
]

# `source` tag values — one per builder
SOURCE_SKILL_DIFFS = "skill_diffs"
SOURCE_GOS = "graph_of_skills"
SOURCE_CLAWHUB = "clawhub"
SOURCE_SLOP = "slop_stub"
SOURCE_MACHINE_AUTHORED = "machine_authored"

# Frozen upstream row counts (ADR-0005, verified 2026-07-07).
# Builders assert against these at run time; a mismatch is a D7 spec/reality
# conflict → stop and log, do not silently substitute.
SKILL_DIFFS_EXPECTED = {
    "diffs.parquet": 986_515,
    "diffs_clean.parquet": 130_631,
    "skills_initial.parquet": 664_872,
    "repos.parquet": 5_891,
    "bundled.parquet": 630_119,
}
GOS_EXPECTED_SKILLS = 2_000
SLOP_EXPECTED_STUBS = 5_147
CLAWHUB_EXPECTED_APPROX = 549  # live count may drift; record the actual, don't assert hard

# ADR-0009: HF zhang-ziao/SkillFlow-exp-skills index.json summary says 598 entries, but
# only entries with has_skill_md=True carry actual SKILL.md text (verified 2026-07-08:
# 582 of 598). Assert against the has-text count, not the raw entry count.
SKILLFLOW_EXP_SKILLS_EXPECTED = 582
# Qwen-Applications/Trace2Skill released_skills/: 4 evolved variants (2 self-deepening
# "combined", 2 self-creation-from-scratch) + 1 human-written Anthropic baseline
# (spreadsheet_agent/skills/xlsx/SKILL.md — byte-identical frontmatter to the two
# "combined" deepening variants, confirming it's their evolution source).
TRACE2SKILL_EXPECTED_VARIANTS = 5
