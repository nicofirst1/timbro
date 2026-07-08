"""Pure-logic tests for merge.py's pool/dedup-apply/installs-join/holdout/report seams.

No parquet/disk I/O anywhere in this file — tiny synthetic in-memory fixtures with
hand-computed expected values, so this suite runs in well under a second and does not
require paper/data/ to exist. Seams under test (all pure, importable):

  _join_key(s) -> str
  _frontmatter_name(fm) -> str | None
  project_row(row: dict, columns: list[str]) -> dict
  apply_dedup_map(pooled: list[dict], dedup_map: list[dict]) -> tuple[list[dict], int]
  join_installs(corpus_rows: list[dict], skillssh_rows: list[dict]) -> dict (stats + mutates installs)
  build_holdout(corpus_rows: list[dict], skillssh_rows: list[dict]) -> tuple[list[dict], dict]
  render_report(stats: dict) -> str
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from _schema import CORPUS_COLUMNS  # noqa: E402
from merge import (  # noqa: E402
    _frontmatter_name,
    _join_key,
    apply_dedup_map,
    build_holdout,
    join_installs,
    project_row,
    render_report,
)

# ---- _join_key ---------------------------------------------------------------


def test_join_key_collapses_case_hyphen_underscore_space():
    assert _join_key("anomaly-detection") == "anomalydetection"
    assert _join_key("Anomaly Detection") == "anomalydetection"
    assert _join_key("anomaly_detection") == "anomalydetection"


def test_join_key_none_and_empty_become_empty_string():
    assert _join_key(None) == ""
    assert _join_key("") == ""


# ---- _frontmatter_name --------------------------------------------------------


def test_frontmatter_name_parses_simple_name_line():
    fm = "name: foo-bar\ndescription: x"
    assert _frontmatter_name(fm) == "foo-bar"


def test_frontmatter_name_handles_quoted_name():
    fm = 'name: "Anomaly Detection"\ndescription: y'
    assert _frontmatter_name(fm) == "Anomaly Detection"

    fm2 = "name: 'Anomaly Detection'\n"
    assert _frontmatter_name(fm2) == "Anomaly Detection"


def test_frontmatter_name_returns_none_when_no_name_line():
    fm = "description: x\nlicense: MIT"
    assert _frontmatter_name(fm) is None
    assert _frontmatter_name(None) is None
    assert _frontmatter_name("") is None


# ---- project_row (pool/project) ------------------------------------------------


def test_skill_diffs_shaped_row_projects_to_exactly_corpus_columns():
    row = {
        "skill_id": "sd:abc123",
        "source": "skill_diffs",
        "platform": "claude",
        "text": "some text",
        "frontmatter_json": "name: foo\n",
        "repo": "owner/reponame",
        "stars": "10",
        "downloads": None,
        "installs": None,
        "created_at": "2026-01-01",
        "updated_at": "2026-02-01",
        "license_spdx": "MIT",
        "n_revisions": "3",
        "near_dup_cluster_id": None,
        "is_canonical": None,
        # 5 sibling cols that must be dropped
        "n_sibling_files": "2",
        "has_scripts_dir": "true",
        "has_references_dir": "false",
        "has_assets_dir": "false",
        "has_readme_in_folder": "true",
    }
    out = project_row(row, CORPUS_COLUMNS)
    assert set(out.keys()) == set(CORPUS_COLUMNS)
    assert "n_sibling_files" not in out
    assert "has_scripts_dir" not in out
    assert out["skill_id"] == "sd:abc123"
    assert out["repo"] == "owner/reponame"


def test_project_row_missing_keys_become_null():
    row = {"skill_id": "gos:1", "source": "graph_of_skills", "text": "t"}
    out = project_row(row, CORPUS_COLUMNS)
    assert set(out.keys()) == set(CORPUS_COLUMNS)
    assert out["repo"] is None
    assert out["stars"] is None


# ---- apply_dedup_map -----------------------------------------------------------


def test_apply_dedup_map_overwrites_source_nulls():
    pooled = [
        {"skill_id": "sd:1", "near_dup_cluster_id": None, "is_canonical": None},
        {"skill_id": "sd:2", "near_dup_cluster_id": None, "is_canonical": None},
    ]
    dedup_map = [
        {"skill_id": "sd:1", "near_dup_cluster_id": "ndc:000000", "cluster_size": "2", "is_canonical": "true"},
        {"skill_id": "sd:2", "near_dup_cluster_id": "ndc:000000", "cluster_size": "2", "is_canonical": "false"},
    ]
    out, n_missing = apply_dedup_map(pooled, dedup_map)
    by_id = {r["skill_id"]: r for r in out}
    assert by_id["sd:1"]["near_dup_cluster_id"] == "ndc:000000"
    assert by_id["sd:1"]["is_canonical"] == "true"
    assert by_id["sd:2"]["is_canonical"] == "false"
    assert n_missing == 0


def test_apply_dedup_map_detects_missing_skill_id():
    pooled = [
        {"skill_id": "sd:1", "near_dup_cluster_id": None, "is_canonical": None},
        {"skill_id": "sd:absent", "near_dup_cluster_id": None, "is_canonical": None},
    ]
    dedup_map = [
        {"skill_id": "sd:1", "near_dup_cluster_id": "ndc:000000", "cluster_size": "1", "is_canonical": "true"},
    ]
    out, n_missing = apply_dedup_map(pooled, dedup_map)
    assert n_missing == 1
    # not dropped, not silently nulled-and-forgotten — row still present
    by_id = {r["skill_id"]: r for r in out}
    assert "sd:absent" in by_id
    assert len(out) == 2


# ---- join_installs --------------------------------------------------------------


def test_installs_join_loose_match_populates_installs():
    corpus_rows = [
        {
            "skill_id": "sd:1",
            "source": "skill_diffs",
            "repo": "Owner/Repo",
            "frontmatter_json": "name: Anomaly Detection\n",
            "installs": None,
        }
    ]
    skillssh_rows = [
        {"owner": "owner", "repo": "repo", "skill": "anomaly-detection", "installs": 42, "url": "https://x"}
    ]
    stats = join_installs(corpus_rows, skillssh_rows)
    assert corpus_rows[0]["installs"] == "42"
    assert stats["n_skill_diffs"] == 1
    assert stats["n_installs_matched"] == 1


def test_installs_join_null_repo_rows_never_match():
    corpus_rows = [
        {"skill_id": "gos:1", "source": "graph_of_skills", "repo": None, "frontmatter_json": None, "installs": None},
        {"skill_id": "slop:1", "source": "slop_stub", "repo": None, "frontmatter_json": None, "installs": None},
    ]
    skillssh_rows = [
        {"owner": "owner", "repo": "repo", "skill": "anomaly-detection", "installs": 42, "url": "https://x"}
    ]
    stats = join_installs(corpus_rows, skillssh_rows)
    assert corpus_rows[0]["installs"] is None
    assert corpus_rows[1]["installs"] is None
    assert stats["n_skill_diffs"] == 0
    assert stats["n_installs_matched"] == 0


def test_installs_join_non_matching_skill_diffs_row_stays_null():
    corpus_rows = [
        {
            "skill_id": "sd:1",
            "source": "skill_diffs",
            "repo": "owner/repo",
            "frontmatter_json": "name: totally-different\n",
            "installs": None,
        }
    ]
    skillssh_rows = [
        {"owner": "owner", "repo": "repo", "skill": "anomaly-detection", "installs": 42, "url": "https://x"}
    ]
    stats = join_installs(corpus_rows, skillssh_rows)
    assert corpus_rows[0]["installs"] is None
    assert stats["n_skill_diffs"] == 1
    assert stats["n_installs_matched"] == 0


def test_installs_join_duplicate_skillssh_keys_keep_max():
    corpus_rows = [
        {
            "skill_id": "sd:1",
            "source": "skill_diffs",
            "repo": "owner/repo",
            "frontmatter_json": "name: anomaly-detection\n",
            "installs": None,
        }
    ]
    # installs passed as STRINGS + adversarial values: numeric max is "100", but a
    # lexical max of {"9","100","7"} would wrongly pick "9" -> guards the int() cast.
    skillssh_rows = [
        {"owner": "owner", "repo": "repo", "skill": "anomaly-detection", "installs": "9", "url": "https://a"},
        {"owner": "owner", "repo": "repo", "skill": "anomaly-detection", "installs": "100", "url": "https://b"},
        {"owner": "owner", "repo": "repo", "skill": "Anomaly_Detection", "installs": "7", "url": "https://c"},
    ]
    stats = join_installs(corpus_rows, skillssh_rows)
    assert corpus_rows[0]["installs"] == "100"
    assert stats["n_installs_matched"] == 1


# ---- build_holdout --------------------------------------------------------------


def test_holdout_includes_skillssh_row_in_overlapping_repo_with_no_corpus_match():
    corpus_rows = [
        {
            "skill_id": "sd:1",
            "source": "skill_diffs",
            "repo": "owner/repo",
            "frontmatter_json": "name: matched-skill\n",
        }
    ]
    skillssh_rows = [
        {"owner": "owner", "repo": "repo", "skill": "matched-skill", "installs": 10, "url": "https://a"},
        {"owner": "owner", "repo": "repo", "skill": "brand-new-skill", "installs": 20, "url": "https://b"},
    ]
    holdout, stats = build_holdout(corpus_rows, skillssh_rows)
    assert len(holdout) == 1
    assert holdout[0]["skill"] == "brand-new-skill"
    assert set(holdout[0].keys()) == {"owner", "repo", "skill", "installs", "url"}


def test_holdout_excludes_skillssh_row_whose_repo_not_in_corpus():
    corpus_rows = [
        {
            "skill_id": "sd:1",
            "source": "skill_diffs",
            "repo": "owner/repo",
            "frontmatter_json": "name: matched-skill\n",
        }
    ]
    skillssh_rows = [
        {"owner": "other-owner", "repo": "other-repo", "skill": "some-skill", "installs": 5, "url": "https://z"},
    ]
    holdout, stats = build_holdout(corpus_rows, skillssh_rows)
    assert holdout == []
    assert stats["repo_overlap"] == 0


def test_holdout_sorted_and_stats_present():
    corpus_rows = [
        {"skill_id": "sd:1", "source": "skill_diffs", "repo": "o/r", "frontmatter_json": "name: m\n"},
    ]
    skillssh_rows = [
        {"owner": "o", "repo": "r", "skill": "zzz", "installs": 1, "url": "https://z"},
        {"owner": "o", "repo": "r", "skill": "aaa", "installs": 2, "url": "https://a"},
    ]
    holdout, stats = build_holdout(corpus_rows, skillssh_rows)
    assert [h["skill"] for h in holdout] == ["aaa", "zzz"]
    assert stats["repo_overlap"] == 1
    assert stats["ceiling"] == 2


# ---- render_report ---------------------------------------------------------------


def test_render_report_contains_handed_numbers_and_does_not_recompute():
    stats = {
        "per_source_counts": {"skill_diffs": 664875, "graph_of_skills": 2000, "slop_stub": 5147},
        "per_source_canonical_counts": {"skill_diffs": 500000, "graph_of_skills": 1900, "slop_stub": 5000},
        "dedup": {
            "exact_removal_rate": 0.123456,
            "near_dup_removal_rate": 0.654321,
            "d1_fork_explosion": False,
            "n_exact_classes": 111,
            "n_near_dup_clusters": 222,
        },
        "platform_counts": {"claude": 100, None: 50},
        "license_counts": {"MIT": 200, None: 30},
        "install_join": {
            "n_installs_matched": 9874,
            "n_skill_diffs": 9874,
            "install_join_rate_present": 0.999,  # sentinel, must appear verbatim
            "install_join_rate_ceiling": 0.853,  # sentinel
            "repo_overlap": 816,
            "holdout_n": 1701,
        },
        "dedup_map_missing_n": 0,
    }
    report = render_report(stats)
    assert "664875" in report or "664,875" in report
    assert "2000" in report or "2,000" in report
    assert "5147" in report or "5,147" in report
    assert "0.999" in report
    assert "0.853" in report
    assert "816" in report
    assert "1701" in report or "1,701" in report
    assert "False" in report or "false" in report.lower()
    # sentinel rates handed in must appear verbatim -> proves no recomputation
    assert "0.123456" in report
    assert "0.654321" in report
