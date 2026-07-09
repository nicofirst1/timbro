"""Pure-logic tests for build_human_baseline.py (WS1 step 9, RQ5, ADR-0008).

Seams under test (no network, no HF/gh calls):
  - is_readme_or_contributing_basename: filename filter
  - assign_era: pre/post-2023 classification
  - is_english_heuristic: ASCII+stopword English filter (langdetect substitute)
  - repo_has_skill_md: SKILL.md-repo exclusion (ADR-0008)
  - make_doc_id: deterministic id construction
  - coerce_cell / write_output: type-safe all-string parquet write (the-stack
    ships list-typed licenses + datetime timestamps that crashed the write)
"""
import datetime
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import build_human_baseline as bhb  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from build_human_baseline import (  # noqa: E402
    AUDIENCE_HUMAN,
    ERA_POST,
    ERA_PRE,
    OUTPUT_COLUMNS,
    GhCache,
    assign_era,
    coerce_cell,
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


# ---- coerce_cell: type-safe cell -> str|None --------------------------------------

def test_coerce_cell_passes_none_through():
    assert coerce_cell(None) is None


def test_coerce_cell_passes_str_through_unchanged():
    assert coerce_cell("MIT") == "MIT"


def test_coerce_cell_json_encodes_list():
    # the-stack's max_stars_repo_licenses is a list<string> — the field that crashed
    # the write with ArrowTypeError "Expected bytes, got a 'list' object".
    assert coerce_cell(["mit", "apache-2.0"]) == '["mit", "apache-2.0"]'


def test_coerce_cell_json_encodes_dict():
    assert coerce_cell({"spdx_id": "MIT"}) == '{"spdx_id": "MIT"}'


def test_coerce_cell_strs_datetime():
    dt = datetime.datetime(2022, 6, 1, 12, 0, 0)
    assert coerce_cell(dt) == "2022-06-01 12:00:00"


# ---- write_output: real-cell shapes produce an all-string table --------------------

def test_write_output_handles_list_license_and_datetime(tmp_path, monkeypatch):
    # data_dir() is where write_output lands the parquet; redirect it to tmp_path.
    monkeypatch.setattr(bhb, "data_dir", lambda: tmp_path)

    stack_row = {
        "doc_id": "stack:aaaa",
        "audience": AUDIENCE_HUMAN,
        "era": ERA_PRE,
        "text": "# README\nThis is a tool you can use.",
        "repo": "owner/stack-repo",
        # non-string cells straight off the-stack schema:
        "license_spdx": ["mit", "apache-2.0"],          # list<string>
        "first_timestamp": None,
        "last_timestamp": datetime.datetime(2022, 6, 1),  # datetime object
        "source_detail": "the_stack_v1",
    }
    gh_row = {
        "doc_id": "github:bbbb",
        "audience": AUDIENCE_HUMAN,
        "era": ERA_POST,
        "text": "# README\nAnother tool you can install.",
        "repo": "owner/gh-repo",
        "license_spdx": "MIT",   # GH cell licenses are plain strings
        "first_timestamp": "2024-01-01T00:00:00Z",
        "last_timestamp": "2024-06-01T00:00:00Z",
        "source_detail": "github_active",
    }

    out_path = bhb.write_output([stack_row, gh_row])
    table = pq.read_table(str(out_path))

    # Every output column is string-typed and the write did not crash.
    for col in OUTPUT_COLUMNS:
        assert table.schema.field(col).type == bhb.pa.string()

    d = table.to_pydict()
    # Rows are sorted by doc_id: "github:bbbb" < "stack:aaaa".
    assert d["doc_id"] == ["github:bbbb", "stack:aaaa"]
    # List license JSON-encoded; plain-string license untouched.
    assert d["license_spdx"] == ["MIT", '["mit", "apache-2.0"]']
    # Datetime stringified; None (stack first_timestamp) preserved as null.
    assert d["last_timestamp"] == ["2024-06-01T00:00:00Z", "2022-06-01 00:00:00"]
    assert d["first_timestamp"] == ["2024-01-01T00:00:00Z", None]


# ---- stream checkpoint roundtrip (disk-only, tmp_path — no network) ----------------

def test_stack_checkpoint_roundtrip_and_skip(tmp_path, monkeypatch):
    monkeypatch.setattr(bhb, "data_dir", lambda: tmp_path)

    # No checkpoint yet -> load returns None (caller streams).
    assert bhb.load_stack_checkpoint() is None

    rows = [{"doc_id": "stack:x", "text": "hi"}]
    info = {"n_scanned": 100, "n_matched": 3, "blocked": False}
    bhb.save_stack_checkpoint(rows, info)

    loaded = bhb.load_stack_checkpoint()
    assert loaded is not None
    loaded_rows, loaded_info = loaded
    assert loaded_rows == rows
    assert loaded_info == info
