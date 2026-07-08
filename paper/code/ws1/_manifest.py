"""Shared reproducibility helpers for WS1 corpus builders.

Every builder resolves paths through here and, after writing its output parquet,
calls write_manifest(). Data goes to paper/data/ (gitignored); the manifest JSON
goes to paper/code/ws1/manifests/ (committed) so provenance is version-controlled
even though the data is not. See LEDGER.md for the reproducibility contract.
"""
from __future__ import annotations

import hashlib
import importlib.metadata as im
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SEED = 42  # fixed everywhere: MinHash permutations, any sampling


def repo_root() -> Path:
    out = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True)
    return Path(out.strip())


def data_dir() -> Path:
    d = repo_root() / "paper" / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def manifest_dir() -> Path:
    d = repo_root() / "paper" / "code" / "ws1" / "manifests"
    d.mkdir(parents=True, exist_ok=True)
    return d


def git_commit() -> str | None:
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
        return sha + ("-dirty" if dirty else "")
    except Exception:
        return None


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pkg_versions(names) -> dict:
    out = {}
    for n in names:
        try:
            out[n] = im.version(n)
        except im.PackageNotFoundError:
            out[n] = None
    return out


def write_manifest(output_path, *, source, inputs, n_rows, packages=(), extra=None) -> dict:
    """Write <name>.manifest.json into the committed manifests/ dir.

    output_path : the produced parquet in paper/data/ (hashed, not committed)
    source      : short source tag (see _schema.SOURCE_*)
    inputs      : list of dicts describing upstream inputs (dataset id + revision,
                  or URL + fetch date, ideally with a sha256)
    n_rows      : row count of the output, read from the artifact itself
    packages    : package names whose resolved versions to record
    """
    output_path = Path(output_path)
    manifest = {
        "script": Path(sys.argv[0]).name,
        "source": source,
        "git_commit": git_commit(),
        "seed": SEED,
        "utc": datetime.now(timezone.utc).isoformat(),
        "inputs": list(inputs),
        "output": output_path.name,
        "output_sha256": sha256_file(output_path) if output_path.exists() else None,
        "n_rows": n_rows,
        "packages": pkg_versions(packages),
        **(extra or {}),
    }
    mp = manifest_dir() / (output_path.name + ".manifest.json")
    mp.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    print(f"[manifest] {mp.relative_to(repo_root())}  n_rows={n_rows}")
    return manifest
