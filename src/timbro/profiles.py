"""Manage named Timbro corpus profiles.

Profiles are folder pairs under a root directory, by default `~/.timbro/profiles/`
(override with `TIMBRO_PROFILE_ROOT`):

    <root>/<name>/exemplars/
    <root>/<name>/contrast/
    <root>/<name>/README.md

The README describes what the profile is for; the corpus folders hold `.md` / `.txt`
documents that Timbro scores against.
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from timbro.cleanup import tex_to_markdown
from timbro.core import _style_vec


_VALID_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


@dataclass(frozen=True)
class Profile:
    name: str
    root: Path

    @property
    def path(self) -> Path:
        return self.root / self.name

    @property
    def exemplars_dir(self) -> Path:
        return self.path / "exemplars"

    @property
    def contrast_dir(self) -> Path:
        return self.path / "contrast"

    @property
    def readme_path(self) -> Path:
        return self.path / "README.md"

    @property
    def env(self) -> dict[str, str]:
        return {
            "TIMBRO_EXEMPLARS": str(self.exemplars_dir.resolve()),
            "TIMBRO_CONTRAST": str(self.contrast_dir.resolve()),
        }

    def summary(self) -> str:
        if not self.readme_path.exists():
            return ""
        lines = self.readme_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        body = [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]
        return body[0] if body else ""


def profile_root(root: str | Path | None = None) -> Path:
    # ponytail: default to ~/.timbro/profiles so profiles are user-global, not CWD-relative
    base = Path(root) if root is not None else Path(
        os.environ.get("TIMBRO_PROFILE_ROOT", Path.home() / ".timbro" / "profiles")
    ).expanduser()
    return base.resolve()


def normalize_profile_name(name: str) -> str:
    out = name.strip().lower().replace(" ", "-")
    if not _VALID_NAME.fullmatch(out):
        raise ValueError(
            f"Invalid profile name {name!r}. Use lowercase letters, digits, '-' or '_'."
        )
    return out


def get_profile(name: str, root: str | Path | None = None) -> Profile:
    return Profile(normalize_profile_name(name), profile_root(root))


def list_profiles(root: str | Path | None = None) -> list[Profile]:
    base = profile_root(root)
    if not base.exists():
        return []
    out = []
    for child in sorted(p for p in base.iterdir() if p.is_dir()):
        if child.name.startswith("."):
            continue
        out.append(Profile(child.name, base))
    return out


def _corpus_files(directory: Path) -> list[Path]:
    return sorted([*directory.glob("*.md"), *directory.glob("*.txt")])


def diagnose_profile(name: str, root: str | Path | None = None) -> dict:
    profile = get_profile(name, root)
    files = _corpus_files(profile.exemplars_dir)
    if not files:
        return {
            "name": profile.name,
            "exemplars": 0,
            "coherence": None,
            "mixed_profile": False,
            "silhouette": None,
            "warning": "No exemplar files found.",
            "outliers": [],
            "files": [],
        }

    rows = []
    vecs = []
    for path in files:
        text = path.read_text(encoding="utf-8", errors="ignore")
        words = len(re.findall(r"\b\w+\b", text))
        paragraphs = len([p for p in re.split(r"\n\s*\n", text) if len(re.findall(r"\b\w+\b", p)) >= 30])
        rows.append({
            "file": path.name,
            "words": words,
            "paragraphs": paragraphs,
        })
        vecs.append(np.array(_style_vec(text), dtype=float))

    V = np.vstack(vecs)
    Vn = V / (np.linalg.norm(V, axis=1, keepdims=True) + 1e-9)
    sims = Vn @ Vn.T
    pairwise = sims[np.triu_indices(len(files), k=1)]
    mean_similarity = float(pairwise.mean()) if len(pairwise) else 1.0

    nn_dist = []
    for i in range(len(files)):
        d = np.linalg.norm(V[i] - np.delete(V, i, axis=0), axis=1) if len(files) > 1 else np.array([0.0])
        nn_dist.append(float(d.min()))
        rows[i]["nearest_neighbor_distance"] = nn_dist[-1]

    median = float(np.median(nn_dist))
    spread = float(np.std(nn_dist) or 1.0)
    outliers = [row["file"] for row in rows if row["nearest_neighbor_distance"] > median + 1.5 * spread]

    mixed_profile = False
    silhouette = None
    if len(files) >= 6:
        labels = KMeans(n_clusters=2, n_init=10, random_state=0).fit_predict(V)
        if len(set(labels)) == 2:
            silhouette = float(silhouette_score(V, labels))
            mixed_profile = silhouette > 0.25

    warning = None
    if outliers:
        warning = f"Outlier exemplars detected: {', '.join(outliers)}"
    elif mixed_profile:
        warning = "Profile may mix multiple modes; consider splitting it."
    elif mean_similarity < 0.75:
        warning = "Profile coherence is low; exemplars may not represent one writing mode."

    return {
        "name": profile.name,
        "exemplars": len(files),
        "coherence": mean_similarity,
        "mixed_profile": mixed_profile,
        "silhouette": silhouette,
        "warning": warning,
        "outliers": outliers,
        "files": rows,
    }


def _readme_text(name: str, about: str) -> str:
    return (
        f"# {name}\n\n"
        f"{about.strip() or 'Describe what this profile is for and what writing it moves toward/away from.'}\n\n"
        "## Layout\n\n"
        "- `exemplars/` - writing to move toward\n"
        "- `contrast/` - writing to move away from (optional but useful)\n"
    )


def init_profile(name: str, about: str = "", root: str | Path | None = None) -> Profile:
    profile = get_profile(name, root)
    profile.exemplars_dir.mkdir(parents=True, exist_ok=True)
    profile.contrast_dir.mkdir(parents=True, exist_ok=True)
    if not profile.readme_path.exists():
        profile.readme_path.write_text(_readme_text(profile.name, about), encoding="utf-8")
    elif about.strip():
        profile.readme_path.write_text(_readme_text(profile.name, about), encoding="utf-8")
    return profile


def _slug_filename(name: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "document"
    return stem


def add_text(
    profile_name: str,
    text: str,
    *,
    bucket: str,
    title: str,
    root: str | Path | None = None,
    overwrite: bool = False,
) -> Path:
    profile = init_profile(profile_name, root=root)
    target_dir = profile.exemplars_dir if bucket == "exemplars" else profile.contrast_dir
    path = target_dir / f"{_slug_filename(title)}.md"
    if path.exists() and not overwrite:
        raise FileExistsError(f"Destination already exists: {path}")
    path.write_text(text, encoding="utf-8")
    return path


def add_file(
    profile_name: str,
    source: str | Path,
    *,
    bucket: str,
    dest_name: str | None = None,
    root: str | Path | None = None,
    overwrite: bool = False,
) -> Path:
    profile = init_profile(profile_name, root=root)
    src = Path(source)
    if not src.exists():
        raise FileNotFoundError(src)
    target_dir = profile.exemplars_dir if bucket == "exemplars" else profile.contrast_dir
    ext = src.suffix.lower() or ".md"
    if ext not in {".md", ".txt", ".tex"}:
        raise ValueError("Only .md, .txt, and .tex files can be added to a Timbro profile.")
    name = dest_name or (f"{src.stem}.md" if ext == ".tex" else src.name)
    dst = target_dir / name
    if dst.exists() and not overwrite:
        raise FileExistsError(f"Destination already exists: {dst}")
    if ext == ".tex":
        dst.write_text(tex_to_markdown(src), encoding="utf-8")
    else:
        shutil.copy2(src, dst)
    return dst
