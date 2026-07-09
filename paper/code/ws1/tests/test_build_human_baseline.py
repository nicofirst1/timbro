"""Pure-logic tests for build_human_baseline.py (WS1 step 9, RQ5, ADR-0008).

Seams under test (no network, no HF/gh calls):
  - is_readme_or_contributing_basename: filename filter
  - assign_era: pre/post-2023 classification
  - is_english_heuristic: ASCII+stopword English filter (langdetect substitute)
  - repo_has_skill_md: SKILL.md-repo exclusion (ADR-0008)
  - make_doc_id: deterministic id construction
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from build_human_baseline import (  # noqa: E402
    ERA_POST,
    ERA_PRE,
    GhCache,
    assign_era,
    is_english_heuristic,
    is_readme_or_contributing_basename,
    make_doc_id,
    repo_has_skill_md,
)


# ---- is_readme_or_contributing_basename ------------------------------------------

def test_readme_md_matches():
    assert is_readme_or_contributing_basename("README.md") is True


def test_readme_lowercase_matches_case_insensitively():
    assert is_readme_or_contributing_basename("readme.md") is True


def test_contributing_md_matches():
    assert is_readme_or_contributing_basename("CONTRIBUTING.md") is True


def test_contributing_lowercase_matches():
    assert is_readme_or_contributing_basename("contributing.md") is True


def test_readme_with_suffix_matches_prefix_rule():
    # basename must START WITH README/CONTRIBUTING (e.g. README.zh.md conventions)
    assert is_readme_or_contributing_basename("README.zh-CN.md") is True


def test_readme_rst_does_not_match_wrong_extension():
    assert is_readme_or_contributing_basename("README.rst") is False


def test_readme_no_extension_does_not_match():
    assert is_readme_or_contributing_basename("README") is False


def test_readme_txt_does_not_match():
    assert is_readme_or_contributing_basename("README.txt") is False


def test_unrelated_md_file_does_not_match():
    assert is_readme_or_contributing_basename("CHANGELOG.md") is False


def test_skill_md_does_not_match():
    assert is_readme_or_contributing_basename("SKILL.md") is False


def test_none_and_empty_basename_do_not_match():
    assert is_readme_or_contributing_basename(None) is False
    assert is_readme_or_contributing_basename("") is False


# ---- assign_era ------------------------------------------------------------------

def test_date_before_2023_is_pre():
    assert assign_era("2022-06-15T00:00:00Z") == ERA_PRE


def test_date_exactly_cutoff_is_post():
    assert assign_era("2023-01-01T00:00:00Z") == ERA_POST


def test_date_after_2023_is_post():
    assert assign_era("2024-03-01T00:00:00Z") == ERA_POST


def test_date_only_no_time_component():
    assert assign_era("2021-11-01") == ERA_PRE


def test_missing_date_defaults_to_post_conservatively():
    assert assign_era(None) == ERA_POST


def test_short_unparseable_date_defaults_to_post():
    assert assign_era("2023") == ERA_POST


def test_custom_cutoff_respected():
    assert assign_era("2022-06-01T00:00:00Z", cutoff="2022-01-01") == ERA_POST
    assert assign_era("2021-06-01T00:00:00Z", cutoff="2022-01-01") == ERA_PRE


# ---- is_english_heuristic ---------------------------------------------------------

_ENGLISH_README = """# My Project

This is a simple tool for developers. You can install it with pip and use it
in your workflow. The documentation explains how to configure it for your needs.
"""

_CHINESE_README = "这是一个用于开发者的工具，您可以安装它并在您的工作流中使用它。"

_SPANISH_README = """# Mi Proyecto

Esta es una herramienta simple para desarrolladores. Puedes instalarla con pip
y usarla en tu flujo de trabajo. La documentacion explica como configurarla.
"""


def test_english_prose_passes():
    assert is_english_heuristic(_ENGLISH_README) is True


def test_chinese_text_fails_ascii_ratio():
    assert is_english_heuristic(_CHINESE_README) is False


def test_spanish_text_fails_stopword_check():
    # Mostly-ASCII (accented chars aside) but lacks English stopwords.
    assert is_english_heuristic(_SPANISH_README) is False


def test_empty_and_none_text_are_not_english():
    assert is_english_heuristic(None) is False
    assert is_english_heuristic("") is False
    assert is_english_heuristic("   \n\t  ") is False


def test_single_stopword_is_not_enough():
    # Only "the" present once -> below _STOPWORD_MIN_HITS threshold of 2 distinct hits.
    assert is_english_heuristic("the") is False


def test_short_code_snippet_without_stopwords_fails():
    assert is_english_heuristic("x = 1\ny = 2\nz = x + y") is False


# ---- repo_has_skill_md -------------------------------------------------------------

def test_repo_with_root_skill_md_is_excluded():
    assert repo_has_skill_md(["README.md", "SKILL.md", "src/main.py"]) is True


def test_repo_with_nested_skill_md_is_excluded():
    assert repo_has_skill_md(["README.md", "skills/foo/SKILL.md"]) is True


def test_repo_without_skill_md_is_not_excluded():
    assert repo_has_skill_md(["README.md", "CONTRIBUTING.md", "src/main.py"]) is False


def test_empty_tree_is_not_excluded():
    assert repo_has_skill_md([]) is False


def test_similarly_named_file_does_not_false_positive():
    # "SKILLS.md" or "SKILL.markdown" must NOT trigger the exclusion (exact basename only).
    assert repo_has_skill_md(["SKILLS.md", "SKILL.markdown", "MYSKILL.md"]) is False


# ---- make_doc_id -------------------------------------------------------------------

def test_doc_id_is_deterministic():
    a = make_doc_id("github", "owner/repo", "README.md")
    b = make_doc_id("github", "owner/repo", "README.md")
    assert a == b


def test_doc_id_differs_by_path():
    a = make_doc_id("github", "owner/repo", "README.md")
    b = make_doc_id("github", "owner/repo", "CONTRIBUTING.md")
    assert a != b


def test_doc_id_carries_source_detail_prefix():
    doc_id = make_doc_id("stack", "owner/repo", "README.md")
    assert doc_id.startswith("stack:")


# ---- GhCache exclusion marker (disk-only, tmp_path — no network) -------------------

def test_cache_excluded_marker_roundtrip(tmp_path):
    cache = GhCache(tmp_path)
    cache.write_excluded("owner/skill-repo")
    # Reads back as "no docs" for the collection loop...
    assert cache.read("owner/skill-repo") == []
    # ...but the exclusion REASON is recoverable for the manifest count.
    assert cache.is_excluded("owner/skill-repo") is True


def test_cache_plain_rows_are_not_excluded(tmp_path):
    cache = GhCache(tmp_path)
    cache.write("owner/normal-repo", [{"path": "README.md", "text": "hi"}])
    assert cache.read("owner/normal-repo") == [{"path": "README.md", "text": "hi"}]
    assert cache.is_excluded("owner/normal-repo") is False


def test_cache_legacy_empty_list_reads_as_no_match_not_excluded(tmp_path):
    # Pre-marker cache format: excluded repos stored a bare [] — reads back as
    # "no match", NOT as an exclusion (documented undercount on legacy caches).
    cache = GhCache(tmp_path)
    cache.write("owner/legacy-repo", [])
    assert cache.read("owner/legacy-repo") == []
    assert cache.is_excluded("owner/legacy-repo") is False


def test_cache_miss_is_none_and_not_excluded(tmp_path):
    cache = GhCache(tmp_path)
    assert cache.read("owner/never-seen") is None
    assert cache.is_excluded("owner/never-seen") is False
