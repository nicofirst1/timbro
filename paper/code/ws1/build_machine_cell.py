#!/usr/bin/env python3
"""Build the machine-authored register cell (ADR-0009, exploratory only — never confirmatory).

Two sub-sources, joined into one output:

1. HF `zhang-ziao/SkillFlow-exp-skills` — ~598 final machine-generated SKILL.md files
   evolved by 11 different LLMs over the SkillFlow benchmark. The dataset ships a curated
   `index.json` (598 entries, `has_skill_md` flag) that we use as the row manifest instead
   of walking the file tree ourselves — it already carries `model` / `task_family` per
   skill, so no path-parsing heuristics are needed. Only entries with `has_skill_md=True`
   (582 of 598, verified 2026-07-08) actually have text to score.
   Domain labels are joined from the companion HF `zhang-ziao/SkillFlow-Task` dataset's
   20-workflow-family -> 5-domain mapping (see `_TASK_FAMILY_TO_DOMAIN`, transcribed
   verbatim from that dataset's README "Workflow Families" section, 2026-07-08 — task.toml
   itself carries no domain field, only category/tags/difficulty).

2. GitHub `Qwen-Applications/Trace2Skill` `released_skills/` — a vignette-scale N=5 case
   study, not a statistical cell: 4 optimizer-evolved xlsx-skill variants
   (`trace2skill-xlsx-{35B,122B}-combined` = self-deepening; `xlsx-{35B,122B}` =
   self-creation-from-scratch) plus the 1 human-written Anthropic baseline they evolved
   from (`spreadsheet_agent/skills/xlsx/SKILL.md` — byte-identical frontmatter+opening to
   the two "combined" deepening variants, confirming it is their evolution source).
   `generator_model` for the 4 evolved variants is the variant slug itself (there is no
   separate "LLM name" — Trace2Skill's factor is the evolution *mode*, not an LLM
   identity); the baseline row is tagged `generator_model=human_anthropic_baseline` and
   would need `is_canonical=false`-style exclusion in any analysis that wants
   machine-only rows (WS3 step 8 handles that; not this builder's job).

CRITICAL name-collision guard (ADR-0009, hit twice on 2026-07-08): HF
`beita6969/SkillFlow-Dataset` is an UNRELATED GFlowNet project sharing the "SkillFlow"
name. Every ID below is pinned exactly; nothing here is discovered by search.

Tags every row `source=machine_authored` (see _schema.SOURCE_MACHINE_AUTHORED) and adds
two columns beyond the shared CORPUS_COLUMNS: `generator_model`, `domain` (task_family
also carried, since it's the SkillFlow-native unit domain was derived from). Not merged
into corpus.parquet — this is a standalone exploratory cell (PLAN WS1 step 10 / WS3 step 8),
mirroring how build_human_baseline.py (step 9) writes its own human_baseline.parquet.
Same dedup/English-filter treatment as every other cell happens downstream in WS3, not here
(this builder only pools + tags, per every other builder's division of labor).
"""
from __future__ import annotations

import json
from pathlib import Path

import pyarrow.parquet as pq
import requests
from huggingface_hub import hf_hub_download

from _manifest import data_dir, write_manifest
from _schema import (
    CORPUS_COLUMNS,
    SKILLFLOW_EXP_SKILLS_EXPECTED,
    SOURCE_MACHINE_AUTHORED,
    TRACE2SKILL_EXPECTED_VARIANTS,
)
from _text import extract_frontmatter, string_table

# Pinned dataset/repo IDs (ADR-0009). Never resolved by search.
SKILLFLOW_EXP_SKILLS_REPO = "zhang-ziao/SkillFlow-exp-skills"
SKILLFLOW_TASK_REPO = "zhang-ziao/SkillFlow-Task"
TRACE2SKILL_GITHUB_REPO = "Qwen-Applications/Trace2Skill"
TRACE2SKILL_REF = "main"

MACHINE_CELL_COLUMNS = CORPUS_COLUMNS + ["generator_model", "domain", "task_family"]

# Verbatim from zhang-ziao/SkillFlow-Task's README "Workflow Families" section
# (fetched + read 2026-07-08): 20 task families -> 5 domains. task.toml carries no
# domain field itself, so this table is the join key, not a live API call.
_TASK_FAMILY_TO_DOMAIN = {
    "Industry-Correlation-Analysis": "Finance & Economics",
    "Financial-Statement-Rolling": "Finance & Economics",
    "SEC-13F-Financial-Analysis": "Finance & Economics",
    "Supply-Chain-Replenishment": "Operations & Supply Chain",
    "Production-Capacity-Planning": "Operations & Supply Chain",
    "Inventory-&-Finance-Integration": "Operations & Supply Chain",
    "DMAIC-Quality-Analysis": "Operations & Supply Chain",
    "Operational-Recovery-Planning": "Operations & Supply Chain",
    "Healthcare-Cost-Benefit-Analysis": "Healthcare & Life Sciences",
    "Medical-Data-Standardization": "Healthcare & Life Sciences",
    "Distribution-Center-Auditing": "Governance & Strategy",
    "Compensation-Scenario-Modeling": "Governance & Strategy",
    "Document-Fraud-Detection": "Data & Document Intelligence",
    "Embedded-Data-Repair": "Data & Document Intelligence",
    "OCR-Data-Extraction": "Data & Document Intelligence",
    "HWPX-Document-Automation": "Data & Document Intelligence",
    "Cross-Format-Data-Reconciliation": "Data & Document Intelligence",
    "Weighted-Risk-Assessment": "Governance & Strategy",
    "PPT-Formatting-Optimization": "Data & Document Intelligence",
    "Sales-Pivot-Analysis": "Finance & Economics",
}

# Trace2Skill released_skills/ variant slug -> generator_model tag.
_TRACE2SKILL_VARIANTS = [
    "trace2skill-xlsx-35B-combined",
    "trace2skill-xlsx-122B-combined",
    "xlsx-35B",
    "xlsx-122B",
]
_TRACE2SKILL_BASELINE_PATH = "spreadsheet_agent/skills/xlsx/SKILL.md"
_TRACE2SKILL_BASELINE_MODEL = "human_anthropic_baseline"


def domain_for_task_family(task_family: str) -> str | None:
    """Look up the SkillFlow-Task domain for a task family name. None if unmapped."""
    return _TASK_FAMILY_TO_DOMAIN.get(task_family)


def rows_from_skillflow_index(index: dict) -> list[dict]:
    """Turn a SkillFlow-exp-skills index.json dict into corpus-shaped row dicts
    (text/frontmatter_json left unset — caller fills those in after downloading
    each SKILL.md). Skips entries with has_skill_md=False. Pure function: no I/O.
    """
    rows = []
    for entry in index.get("entries", []):
        if not entry.get("has_skill_md"):
            continue
        model = entry["model"]
        task_family = entry["task_family"]
        skill_name = entry["skill_name"]
        rows.append({
            "skill_id": f"machine:skillflow:{model}:{task_family}:{skill_name}",
            "source": SOURCE_MACHINE_AUTHORED,
            "platform": None,
            "text": None,
            "frontmatter_json": None,
            "repo": SKILLFLOW_EXP_SKILLS_REPO,
            "stars": None,
            "downloads": None,
            "installs": None,
            "created_at": None,
            "updated_at": None,
            "license_spdx": None,  # HF "other"/unspecified — ADR-0009 license caveat
            "n_revisions": None,
            "near_dup_cluster_id": None,
            "is_canonical": None,
            "generator_model": model,
            "domain": domain_for_task_family(task_family),
            "task_family": task_family,
            "_skill_md_relative_path": entry["skill_md_relative_path"],
        })
    return rows


def row_for_trace2skill_variant(variant: str, text: str) -> dict:
    """Build one corpus-shaped row for a Trace2Skill released_skills/ variant. Pure."""
    text_body, frontmatter = extract_frontmatter(text)
    return {
        "skill_id": f"machine:trace2skill:{variant}",
        "source": SOURCE_MACHINE_AUTHORED,
        "platform": None,
        "text": text_body,
        "frontmatter_json": frontmatter,
        "repo": TRACE2SKILL_GITHUB_REPO,
        "stars": None,
        "downloads": None,
        "installs": None,
        "created_at": None,
        "updated_at": None,
        "license_spdx": "Apache-2.0",  # repo license; xlsx baseline itself is Proprietary (see SKILL.md frontmatter)
        "n_revisions": None,
        "near_dup_cluster_id": None,
        "is_canonical": None,
        "generator_model": variant,
        "domain": None,  # Trace2Skill is a single xlsx vignette, not SkillFlow-task-labeled
        "task_family": None,
    }


def row_for_trace2skill_baseline(text: str) -> dict:
    """Build the human-written Anthropic baseline row that the 4 variants evolved from."""
    text_body, frontmatter = extract_frontmatter(text)
    return {
        "skill_id": "machine:trace2skill:human_anthropic_baseline",
        "source": SOURCE_MACHINE_AUTHORED,  # cell membership; generator_model marks it non-machine-generated
        "platform": None,
        "text": text_body,
        "frontmatter_json": frontmatter,
        "repo": TRACE2SKILL_GITHUB_REPO,
        "stars": None,
        "downloads": None,
        "installs": None,
        "created_at": None,
        "updated_at": None,
        "license_spdx": "Proprietary",  # SKILL.md frontmatter: "Proprietary. LICENSE.txt has complete terms"
        "n_revisions": None,
        "near_dup_cluster_id": None,
        "is_canonical": None,
        "generator_model": _TRACE2SKILL_BASELINE_MODEL,
        "domain": None,
        "task_family": None,
    }


def _raw_github_url(path: str) -> str:
    return f"https://raw.githubusercontent.com/{TRACE2SKILL_GITHUB_REPO}/{TRACE2SKILL_REF}/{path}"


def fetch_trace2skill_text(path: str, *, session: requests.Session | None = None) -> str:
    """Download one file's raw text from the pinned Trace2Skill ref."""
    s = session or requests
    resp = s.get(_raw_github_url(path), timeout=30)
    resp.raise_for_status()
    return resp.text


def build_machine_cell():
    """Download both sub-sources, tag rows, emit src_machine_cell.parquet + manifest."""

    print("[build_machine_cell] Starting machine-authored cell assembly (ADR-0009)")

    # --- Sub-source 1: SkillFlow-exp-skills ---------------------------------
    print(f"[build_machine_cell] Downloading index.json from {SKILLFLOW_EXP_SKILLS_REPO}...")
    index_path = hf_hub_download(
        repo_id=SKILLFLOW_EXP_SKILLS_REPO,
        repo_type="dataset",
        filename="index.json",
    )
    index = json.loads(Path(index_path).read_text())
    skillflow_rows = rows_from_skillflow_index(index)
    print(f"[build_machine_cell] index.json: {len(skillflow_rows)} entries with has_skill_md=True")

    n_skillflow = len(skillflow_rows)
    if n_skillflow != SKILLFLOW_EXP_SKILLS_EXPECTED:
        print(
            f"D7 SPEC/REALITY CONFLICT: expected {SKILLFLOW_EXP_SKILLS_EXPECTED} "
            f"SkillFlow-exp-skills entries with has_skill_md=True, got {n_skillflow}"
        )
    else:
        print(f"[build_machine_cell] Row count {n_skillflow} matches expected {SKILLFLOW_EXP_SKILLS_EXPECTED}")

    n_unmapped_domain = sum(1 for r in skillflow_rows if r["domain"] is None)
    if n_unmapped_domain:
        print(
            f"[build_machine_cell] WARNING: {n_unmapped_domain} rows have a task_family "
            "not in _TASK_FAMILY_TO_DOMAIN (unmapped domain)"
        )

    print(f"[build_machine_cell] Downloading {n_skillflow} SKILL.md files from {SKILLFLOW_EXP_SKILLS_REPO}...")
    for i, row in enumerate(skillflow_rows):
        if (i + 1) % 100 == 0:
            print(f"[build_machine_cell] Progress: {i + 1}/{n_skillflow}")
        md_path = hf_hub_download(
            repo_id=SKILLFLOW_EXP_SKILLS_REPO,
            repo_type="dataset",
            filename=row.pop("_skill_md_relative_path"),
        )
        raw = Path(md_path).read_text(encoding="utf-8", errors="replace")
        text_body, frontmatter = extract_frontmatter(raw)
        row["text"] = text_body
        row["frontmatter_json"] = frontmatter

    # --- Sub-source 2: Trace2Skill released_skills/ (vignette, N=5) --------
    print("[build_machine_cell] Fetching Trace2Skill released_skills/ variants from GitHub...")
    session = requests.Session()
    trace2skill_rows = []
    for variant in _TRACE2SKILL_VARIANTS:
        path = f"released_skills/{variant}/SKILL.md"
        text = fetch_trace2skill_text(path, session=session)
        trace2skill_rows.append(row_for_trace2skill_variant(variant, text))
    baseline_text = fetch_trace2skill_text(_TRACE2SKILL_BASELINE_PATH, session=session)
    trace2skill_rows.append(row_for_trace2skill_baseline(baseline_text))

    n_trace2skill = len(trace2skill_rows)
    if n_trace2skill != TRACE2SKILL_EXPECTED_VARIANTS:
        print(
            f"D7 SPEC/REALITY CONFLICT: expected {TRACE2SKILL_EXPECTED_VARIANTS} "
            f"Trace2Skill rows (4 evolved + 1 baseline), got {n_trace2skill}"
        )
    else:
        print(f"[build_machine_cell] Trace2Skill row count {n_trace2skill} matches expected {TRACE2SKILL_EXPECTED_VARIANTS}")

    # --- Pool + write --------------------------------------------------------
    rows = skillflow_rows + trace2skill_rows
    rows.sort(key=lambda r: r["skill_id"])
    n_rows = len(rows)
    print(f"[build_machine_cell] Pooled {n_rows} rows total ({n_skillflow} SkillFlow + {n_trace2skill} Trace2Skill)")

    out_path = data_dir() / "src_machine_cell.parquet"
    print(f"[build_machine_cell] Writing to {out_path}...")
    pq.write_table(string_table(rows, MACHINE_CELL_COLUMNS), str(out_path))

    print("[build_machine_cell] Writing manifest...")
    write_manifest(
        out_path,
        source=SOURCE_MACHINE_AUTHORED,
        inputs=[
            {"hf_dataset": SKILLFLOW_EXP_SKILLS_REPO, "file": "index.json + per-entry SKILL.md"},
            {"hf_dataset": SKILLFLOW_TASK_REPO, "note": "domain-mapping README only, no data files downloaded"},
            {"github_repo": TRACE2SKILL_GITHUB_REPO, "ref": TRACE2SKILL_REF, "path": "released_skills/ + spreadsheet_agent/skills/xlsx/"},
        ],
        n_rows=n_rows,
        packages=["huggingface_hub", "pyarrow", "requests"],
        extra={
            "n_skillflow_exp_skills": n_skillflow,
            "n_trace2skill": n_trace2skill,
            "n_unmapped_domain": n_unmapped_domain,
        },
    )

    print(f"[build_machine_cell] Complete. Wrote {n_rows} rows to {out_path.name}")


if __name__ == "__main__":
    build_machine_cell()
