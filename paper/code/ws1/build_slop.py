#!/usr/bin/env python3
"""Build slop (low-quality) stub source table from HF dataset amoghacloud/clawskills-intelligence-corpus.

Downloads the entire dataset via snapshot_download, extracts all SKILL.md files,
and emits src_slop.parquet. One row per skill, with skill_id, source, text,
frontmatter_json, license_spdx, and nulls for other columns.
Deterministic (sorted by skill_id). Manifest records provenance.
"""

from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import snapshot_download

from _manifest import data_dir, write_manifest
from _schema import CORPUS_COLUMNS, SLOP_EXPECTED_STUBS, SOURCE_SLOP
from _text import extract_frontmatter, string_table


def build_slop():
    """Download clawskills corpus via snapshot_download, emit src_slop.parquet."""

    print("[build_slop] Starting corpus assembly from clawskills intelligence corpus")

    # Step 1: Download entire dataset snapshot
    print("[build_slop] Downloading dataset snapshot from amoghacloud/clawskills-intelligence-corpus...")
    dataset_dir = snapshot_download(
        repo_id="amoghacloud/clawskills-intelligence-corpus",
        repo_type="dataset",
        cache_dir=None  # Use default HF cache
    )
    print(f"[build_slop] Dataset downloaded to {dataset_dir}")

    # Step 2: Find all SKILL.md files
    print("[build_slop] Scanning for SKILL.md files...")
    dataset_path = Path(dataset_dir)
    skill_files = sorted(dataset_path.glob("skills/*/SKILL.md"))
    print(f"[build_slop] Found {len(skill_files)} SKILL.md files")

    # Print sample paths to understand structure
    if skill_files:
        print("[build_slop] Sample SKILL.md paths:")
        for f in skill_files[:5]:
            print(f"  - {f.relative_to(dataset_path)}")

    # Step 3: Extract each SKILL.md file
    print("[build_slop] Extracting SKILL.md files...")
    rows = []

    for i, skill_file in enumerate(skill_files):
        if (i + 1) % 500 == 0:
            print(f"[build_slop] Progress: {i + 1}/{len(skill_files)}")

        # Read content
        try:
            with open(skill_file, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            print(f"[build_slop] Warning: Failed to read {skill_file}: {e}")
            continue

        # Parse frontmatter
        text, frontmatter = extract_frontmatter(content)

        # Build skill_id: prefix "slop:" + skill directory name
        # Example: "skills/0g-compute/SKILL.md" -> "slop:0g-compute"
        skill_dir = skill_file.parent.name  # Get the directory name (e.g., "0g-compute")
        skill_id = f"slop:{skill_dir}"

        # Build row with CORPUS_COLUMNS
        row = {
            "skill_id": skill_id,
            "source": SOURCE_SLOP,
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
    print(f"[build_slop] Extracted {n_rows} skills")

    # Step 4: Check count against expected (±5%)
    lower_bound = SLOP_EXPECTED_STUBS * (1 - 0.05)
    upper_bound = SLOP_EXPECTED_STUBS * (1 + 0.05)

    if not (lower_bound <= n_rows <= upper_bound):
        print(f"D7 SPEC/REALITY CONFLICT: Expected {SLOP_EXPECTED_STUBS} stubs (±5%), got {n_rows}")
    else:
        print(f"[build_slop] Row count {n_rows} is within ±5% of expected {SLOP_EXPECTED_STUBS}")

    # Step 5: Sort by skill_id (determinism)
    print("[build_slop] Sorting rows by skill_id...")
    rows.sort(key=lambda r: r["skill_id"])

    # Step 6: Write parquet (all CORPUS_COLUMNS as string)
    out_path = data_dir() / "src_slop.parquet"
    print(f"[build_slop] Writing to {out_path}...")
    pq.write_table(string_table(rows, CORPUS_COLUMNS), str(out_path))

    # Step 7: Write manifest
    print("[build_slop] Writing manifest...")
    write_manifest(
        out_path,
        source=SOURCE_SLOP,
        inputs=[{
            "hf_dataset": "amoghacloud/clawskills-intelligence-corpus"
        }],
        n_rows=n_rows,
        packages=["huggingface_hub", "pyarrow"]
    )

    print(f"[build_slop] Complete. Wrote {n_rows} rows to {out_path.name}")


if __name__ == "__main__":
    build_slop()
