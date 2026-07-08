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

# Frozen upstream row counts (paper/README.md §8b, verified 2026-07-07).
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
