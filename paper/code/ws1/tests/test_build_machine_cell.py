"""Pure-logic tests for build_machine_cell.py's parsing/transform seams (ADR-0009).

No network I/O anywhere in this file — small deterministic fixtures. Seams under test
(all pure, importable):

    domain_for_task_family(task_family: str) -> str | None
    rows_from_skillflow_index(index: dict) -> list[dict]
    row_for_trace2skill_variant(variant: str, text: str) -> dict
    row_for_trace2skill_baseline(text: str) -> dict

The network fetch functions (hf_hub_download / requests.get calls inside
build_machine_cell()) are intentionally NOT tested here — they're exercised by actually
running the builder, per the other WS1 builders' convention.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from _schema import SOURCE_MACHINE_AUTHORED  # noqa: E402
from build_machine_cell import (  # noqa: E402
    _TRACE2SKILL_BASELINE_MODEL,
    domain_for_task_family,
    row_for_trace2skill_baseline,
    row_for_trace2skill_variant,
    rows_from_skillflow_index,
)

# ---- domain_for_task_family ---------------------------------------------------


def test_domain_for_known_task_family():
    assert domain_for_task_family("SEC-13F-Financial-Analysis") == "Finance & Economics"
    assert domain_for_task_family("OCR-Data-Extraction") == "Data & Document Intelligence"
    assert domain_for_task_family("Medical-Data-Standardization") == "Healthcare & Life Sciences"


def test_domain_for_unknown_task_family_is_none():
    assert domain_for_task_family("Not-A-Real-Family") is None


def test_all_20_task_families_map_to_one_of_5_domains():
    # Transcribed from zhang-ziao/SkillFlow-Task's README (2026-07-08): 20 families -> 5 domains.
    families = [
        "Compensation-Scenario-Modeling", "Cross-Format-Data-Reconciliation",
        "DMAIC-Quality-Analysis", "Distribution-Center-Auditing", "Document-Fraud-Detection",
        "Embedded-Data-Repair", "Financial-Statement-Rolling", "HWPX-Document-Automation",
        "Healthcare-Cost-Benefit-Analysis", "Industry-Correlation-Analysis",
        "Inventory-&-Finance-Integration", "Medical-Data-Standardization",
        "OCR-Data-Extraction", "Operational-Recovery-Planning", "PPT-Formatting-Optimization",
        "Production-Capacity-Planning", "SEC-13F-Financial-Analysis", "Sales-Pivot-Analysis",
        "Supply-Chain-Replenishment", "Weighted-Risk-Assessment",
    ]
    assert len(families) == 20
    domains = {domain_for_task_family(f) for f in families}
    assert None not in domains
    assert domains == {
        "Finance & Economics", "Operations & Supply Chain", "Healthcare & Life Sciences",
        "Governance & Strategy", "Data & Document Intelligence",
    }


# ---- rows_from_skillflow_index -------------------------------------------------


def _fixture_index():
    return {
        "entries": [
            {
                "model": "claude-code-minimax2dot5-skill",
                "task_family": "Compensation-Scenario-Modeling",
                "skill_name": "excel-compensation-model",
                "skill_md_relative_path": (
                    "claude-code-minimax2dot5-skill/Compensation-Scenario-Modeling/"
                    "skills/excel-compensation-model/SKILL.md"
                ),
                "has_skill_md": True,
            },
            {
                "model": "codex-cli-gpt-5.3-codex-skill",
                "task_family": "OCR-Data-Extraction",
                "skill_name": "jpg-ocr",
                "skill_md_relative_path": (
                    "codex-cli-gpt-5.3-codex-skill/OCR-Data-Extraction/skills/jpg-ocr/SKILL.md"
                ),
                "has_skill_md": True,
            },
            {
                # has_skill_md False entries (16 of 598, verified 2026-07-08) must be skipped.
                "model": "kimi-cli-kimi-k2dot5-skill",
                "task_family": "Weighted-Risk-Assessment",
                "skill_name": "some-empty-entry",
                "skill_md_relative_path": (
                    "kimi-cli-kimi-k2dot5-skill/Weighted-Risk-Assessment/skills/some-empty-entry/SKILL.md"
                ),
                "has_skill_md": False,
            },
        ]
    }


def test_rows_from_skillflow_index_skips_entries_without_skill_md():
    rows = rows_from_skillflow_index(_fixture_index())
    assert len(rows) == 2


def test_rows_from_skillflow_index_tags_source_and_generator_model():
    rows = rows_from_skillflow_index(_fixture_index())
    for r in rows:
        assert r["source"] == SOURCE_MACHINE_AUTHORED
    assert rows[0]["generator_model"] == "claude-code-minimax2dot5-skill"
    assert rows[1]["generator_model"] == "codex-cli-gpt-5.3-codex-skill"


def test_rows_from_skillflow_index_joins_domain_from_task_family():
    rows = rows_from_skillflow_index(_fixture_index())
    assert rows[0]["task_family"] == "Compensation-Scenario-Modeling"
    assert rows[0]["domain"] == "Governance & Strategy"
    assert rows[1]["task_family"] == "OCR-Data-Extraction"
    assert rows[1]["domain"] == "Data & Document Intelligence"


def test_rows_from_skillflow_index_skill_id_is_deterministic_and_unique():
    rows = rows_from_skillflow_index(_fixture_index())
    ids = [r["skill_id"] for r in rows]
    assert len(ids) == len(set(ids))
    assert ids[0] == (
        "machine:skillflow:claude-code-minimax2dot5-skill:"
        "Compensation-Scenario-Modeling:excel-compensation-model"
    )


def test_rows_from_skillflow_index_carries_relative_path_for_caller_to_pop():
    rows = rows_from_skillflow_index(_fixture_index())
    assert rows[0]["_skill_md_relative_path"].endswith("SKILL.md")


def test_rows_from_skillflow_index_empty_entries_yields_empty_list():
    assert rows_from_skillflow_index({"entries": []}) == []


# ---- row_for_trace2skill_variant / row_for_trace2skill_baseline ---------------

_XLSX_TEXT = """---
name: xlsx
description: "Comprehensive spreadsheet creation"
license: Proprietary. LICENSE.txt has complete terms
---

# Requirements for Outputs
Some body text.
"""


def test_row_for_trace2skill_variant_tags_source_and_generator_model():
    row = row_for_trace2skill_variant("xlsx-35B", _XLSX_TEXT)
    assert row["source"] == SOURCE_MACHINE_AUTHORED
    assert row["generator_model"] == "xlsx-35B"
    assert row["skill_id"] == "machine:trace2skill:xlsx-35B"


def test_row_for_trace2skill_variant_splits_frontmatter():
    row = row_for_trace2skill_variant("xlsx-35B", _XLSX_TEXT)
    assert row["frontmatter_json"] is not None
    assert "name: xlsx" in row["frontmatter_json"]
    assert "---" not in row["text"]
    assert "Requirements for Outputs" in row["text"]


def test_row_for_trace2skill_variant_domain_and_task_family_are_none():
    # Trace2Skill is a single-domain xlsx vignette, not SkillFlow-task-labeled.
    row = row_for_trace2skill_variant("xlsx-122B", _XLSX_TEXT)
    assert row["domain"] is None
    assert row["task_family"] is None


def test_row_for_trace2skill_baseline_tags_human_generator_model():
    row = row_for_trace2skill_baseline(_XLSX_TEXT)
    assert row["source"] == SOURCE_MACHINE_AUTHORED  # cell membership, not authorship
    assert row["generator_model"] == _TRACE2SKILL_BASELINE_MODEL
    assert row["generator_model"] == "human_anthropic_baseline"
    assert row["license_spdx"] == "Proprietary"


def test_row_for_trace2skill_baseline_skill_id_is_stable():
    row = row_for_trace2skill_baseline(_XLSX_TEXT)
    assert row["skill_id"] == "machine:trace2skill:human_anthropic_baseline"
