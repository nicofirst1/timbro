#!/usr/bin/env python3
"""Build graph-of-skills source table from HF dataset davidliuk/graph-of-skills-data.

Downloads skills_2000.tar.gz, extracts all SKILL.md files, and emits src_gos.parquet.
One row per skill, with skill_id, source, text, frontmatter_json, license_spdx, and nulls.
Deterministic (sorted by skill_id). Manifest records provenance.
"""

import io
import re
import tarfile
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

from _manifest import SEED, data_dir, write_manifest
from _schema import CORPUS_COLUMNS, GOS_EXPECTED_SKILLS, SOURCE_GOS


def extract_frontmatter(text: str) -> tuple[str, str | None]:
    """Extract frontmatter block (---...---) and return (body, frontmatter_str).

    Handles both Unix (\n) and Windows (\r\n) line endings.

    Returns:
        (body_without_frontmatter, frontmatter_raw_string_or_none)
    """
    # Match frontmatter: --- at start, then content, then --- on its own line
    # Pattern matches both \n and \r\n line endings
    match = re.match(r'^---[\r\n]+(.*?)[\r\n]+---[\r\n]+(.*)$', text, re.DOTALL)
    if match:
        frontmatter_block = match.group(1)
        body = match.group(2)
        return body, frontmatter_block
    return text, None


def build_gos():
    """Download skills_2000.tar.gz, extract SKILL.md files, emit src_gos.parquet."""

    print("[build_gos] Starting corpus assembly from graph-of-skills data")

    # Step 1: Download tar from HF
    print("[build_gos] Downloading skills_2000.tar.gz from HuggingFace...")
    tar_path = hf_hub_download(
        repo_id="davidliuk/graph-of-skills-data",
        filename="skills_2000.tar.gz",
        repo_type="dataset"
    )
    print(f"[build_gos] Downloaded to {tar_path}")

    # Step 2: Inspect tar layout (list members)
    print("[build_gos] Inspecting tar layout...")
    with tarfile.open(tar_path, "r:gz") as tar:
        members = tar.getmembers()
        print(f"[build_gos] Tar contains {len(members)} members")
        # Filter: only SKILL.md files, exclude macOS resource forks (._SKILL.md)
        skill_md_files = [m for m in members if m.name.endswith("SKILL.md") and not Path(m.name).name.startswith("._")]
        print(f"[build_gos] Found {len(skill_md_files)} SKILL.md files (excluding macOS resource forks)")

        # Print sample paths to understand structure
        if skill_md_files:
            print(f"[build_gos] Sample SKILL.md paths:")
            for m in skill_md_files[:5]:
                print(f"  - {m.name}")

    # Step 3: Extract SKILL.md files and build rows
    print("[build_gos] Extracting SKILL.md files and building rows...")
    rows = []

    with tarfile.open(tar_path, "r:gz") as tar:
        for member in tar.getmembers():
            # Only process SKILL.md files, exclude macOS resource forks (._SKILL.md)
            if member.name.endswith("SKILL.md") and not Path(member.name).name.startswith("._"):
                # Extract file content
                f = tar.extractfile(member)
                if f is None:
                    continue
                content = f.read().decode('utf-8', errors='replace')

                # Parse frontmatter
                text, frontmatter = extract_frontmatter(content)

                # Build skill_id: prefix "gos:" + tar-relative path
                skill_id = f"gos:{member.name}"

                # Build row with CORPUS_COLUMNS
                row = {
                    "skill_id": skill_id,
                    "source": SOURCE_GOS,
                    "platform": None,
                    "text": text,
                    "frontmatter_json": frontmatter,
                    "repo": None,
                    "stars": None,
                    "downloads": None,
                    "installs": None,
                    "created_at": None,
                    "updated_at": None,
                    "license_spdx": "MIT",
                    "n_revisions": None,
                    "near_dup_cluster_id": None,
                    "is_canonical": None,
                }
                rows.append(row)

    n_rows = len(rows)
    print(f"[build_gos] Extracted {n_rows} skills")

    # Step 4: Check count against expected
    tolerance = 0.05 * GOS_EXPECTED_SKILLS  # ±5%
    lower_bound = GOS_EXPECTED_SKILLS * (1 - 0.05)
    upper_bound = GOS_EXPECTED_SKILLS * (1 + 0.05)

    if not (lower_bound <= n_rows <= upper_bound):
        print(f"D7 SPEC/REALITY CONFLICT: Expected {GOS_EXPECTED_SKILLS} skills (±5%), got {n_rows}")
    else:
        print(f"[build_gos] Row count {n_rows} is within ±5% of expected {GOS_EXPECTED_SKILLS}")

    # Step 5: Sort by skill_id (determinism)
    print("[build_gos] Sorting rows by skill_id...")
    rows.sort(key=lambda r: r["skill_id"])

    # Step 6: Convert to PyArrow table with correct schema
    print("[build_gos] Converting to PyArrow table...")
    # Build schema with all columns as string or null
    schema = pa.schema([
        (col, pa.string()) for col in CORPUS_COLUMNS
    ])

    # Convert rows to PyArrow format
    arrays = []
    for col in CORPUS_COLUMNS:
        col_values = [row.get(col) for row in rows]
        arrays.append(pa.array(col_values, type=pa.string()))

    table = pa.table({col: arr for col, arr in zip(CORPUS_COLUMNS, arrays)}, schema=schema)

    # Step 7: Write parquet
    out_path = data_dir() / "src_gos.parquet"
    print(f"[build_gos] Writing to {out_path}...")
    pq.write_table(table, str(out_path))

    # Step 8: Write manifest
    print("[build_gos] Writing manifest...")
    write_manifest(
        out_path,
        source=SOURCE_GOS,
        inputs=[{
            "hf_dataset": "davidliuk/graph-of-skills-data",
            "file": "skills_2000.tar.gz"
        }],
        n_rows=n_rows,
        packages=["huggingface_hub", "pyarrow"]
    )

    print(f"[build_gos] Complete. Wrote {n_rows} rows to {out_path.name}")


if __name__ == "__main__":
    build_gos()
