"""Manage named Timbro corpus profiles.

Profiles are folder pairs under a root directory, typically `data/profiles/`:

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

from timbro.cleanup import tex_to_markdown


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
    base = Path(root) if root is not None else Path(os.environ.get("TIMBRO_PROFILE_ROOT", "data/profiles"))
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
