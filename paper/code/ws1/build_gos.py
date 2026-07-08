#!/usr/bin/env python3
"""Build graph-of-skills source table from HF dataset davidliuk/graph-of-skills-data.

Downloads skills_2000.tar.gz, extracts all SKILL.md files, and emits src_gos.parquet.
One row per skill, with skill_id, source, text, frontmatter_json, license_spdx, and nulls.
Deterministic (sorted by skill_id). Manifest records provenance.
"""

import tarfile
from pathlib import Path

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

from _manifest import data_dir, write_manifest
from _schema import CORPUS_COLUMNS, GOS_EXPECTED_SKILLS, SOURCE_GOS
from _text import extract_frontmatter, string_table


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

    # Step 2: Extract SKILL.md files and build rows in a single pass.
    # (Skip macOS resource forks, ._SKILL.md.) One tar open = one gzip decompress.
    print("[build_gos] Extracting SKILL.md files and building rows...")
    rows = []

    with tarfile.open(tar_path, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.name.endswith("SKILL.md") or Path(member.name).name.startswith("._"):
                continue
            f = tar.extractfile(member)
            if f is None:
                continue
            content = f.read().decode("utf-8", errors="replace")
            text, frontmatter = extract_frontmatter(content)
            rows.append({
                "skill_id": f"gos:{member.name}",  # prefix + tar-relative path
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
            })

    n_rows = len(rows)
    print(f"[build_gos] Extracted {n_rows} skills")

    # Step 3: Check count against expected (±5%)
    lower_bound = GOS_EXPECTED_SKILLS * (1 - 0.05)
    upper_bound = GOS_EXPECTED_SKILLS * (1 + 0.05)

    if not (lower_bound <= n_rows <= upper_bound):
        print(f"D7 SPEC/REALITY CONFLICT: Expected {GOS_EXPECTED_SKILLS} skills (±5%), got {n_rows}")
    else:
        print(f"[build_gos] Row count {n_rows} is within ±5% of expected {GOS_EXPECTED_SKILLS}")

    # Step 4: Sort by skill_id (determinism)
    print("[build_gos] Sorting rows by skill_id...")
    rows.sort(key=lambda r: r["skill_id"])

    # Step 5: Write parquet (all CORPUS_COLUMNS as string)
    out_path = data_dir() / "src_gos.parquet"
    print(f"[build_gos] Writing to {out_path}...")
    pq.write_table(string_table(rows, CORPUS_COLUMNS), str(out_path))

    # Step 6: Write manifest
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
