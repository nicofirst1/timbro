"""Manage named Timbro corpus profiles.

Profiles are folder pairs under a root directory. Root resolution precedence
(highest first): the `root` argument, `TIMBRO_PROFILE_ROOT` env var, then
`<TIMBRO_HOME>/profiles` (`TIMBRO_HOME` defaults to `~/.timbro`):

    <root>/<name>/exemplars/
    <root>/<name>/contrast/
    <root>/<name>/README.md

The README describes what the profile is for; the corpus folders hold `.md` / `.txt`
documents that Timbro scores against. The whole root can be kept in sync across
machines with `sync_profiles` (git remote, no server).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from timbro.cleanup import tex_to_markdown
from timbro.model import VoiceModel
from timbro.model.embedding import _style_vec
from timbro.profilelog import log_learn
from timbro.rewrite import evaluate_rewrite
from timbro.settings import timbro_home

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
    if root is not None:
        return Path(root).expanduser().resolve()
    if "TIMBRO_PROFILE_ROOT" in os.environ:
        return Path(os.environ["TIMBRO_PROFILE_ROOT"]).expanduser().resolve()
    return (timbro_home() / "profiles").resolve()


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
    if not profile.readme_path.exists() or about.strip():
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


def _read_pair_text(path: str | Path, label: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    text = p.read_text(encoding="utf-8", errors="ignore")
    if not text.strip():
        raise ValueError(f"{label} file is empty: {p}")
    return text


def _check_pair_slots_free(profile: Profile, title: str) -> None:
    # ponytail: pre-flight existence check, not a temp-write+rename transaction --
    # covers the realistic case (stale title collides with one bucket) without
    # a real fs transaction; upgrade only if concurrent writers to the same
    # profile become a real concern.
    slug = _slug_filename(title)
    exemplar_path = profile.exemplars_dir / f"{slug}.md"
    contrast_path = profile.contrast_dir / f"{slug}.md"
    if exemplar_path.exists():
        raise FileExistsError(f"Destination already exists: {exemplar_path}. Pass force=True or a different title.")
    if contrast_path.exists():
        raise FileExistsError(f"Destination already exists: {contrast_path}. Pass force=True or a different title.")


def learn(
    profile_name: str,
    draft: str | Path,
    final: str | Path,
    *,
    title: str | None = None,
    force: bool = False,
    root: str | Path | None = None,
) -> dict:
    """Save a (raw draft, polished final) editing pair into a profile.

    The final goes to `exemplars/` (move-toward), the raw draft to `contrast/`
    (move-away) -- but only when the pair is worth learning from. The guard is
    the same acceptance check the rewrite loop uses (`evaluate_rewrite`): the
    final must have moved closer to the profile's own voice AND preserved the
    draft's meaning. Scoring is always against the target profile's corpus,
    never the ambient/default model.
    """
    draft_text = _read_pair_text(draft, "draft")
    final_text = _read_pair_text(final, "final")

    profile = get_profile(profile_name, root)
    title = title or Path(final).stem

    model = None
    if _corpus_files(profile.exemplars_dir):
        try:
            model = VoiceModel.from_dir(profile.exemplars_dir, contrast=profile.contrast_dir)
        except FileNotFoundError:
            model = None

    if model is None:
        if not force:
            raise ValueError(
                f"Profile '{profile.name}' has no exemplars to measure against yet, so the "
                "guard can't run. Seed it first (`profiles add-file`) or pass force=True to "
                "bootstrap it with this pair."
            )
        exemplar_path = add_text(profile_name, final_text, bucket="exemplars", title=title, root=root, overwrite=force)
        contrast_path = add_text(profile_name, draft_text, bucket="contrast", title=title, root=root, overwrite=force)
        log_learn(profile, model, draft_text, final_text, title=title, outcome="bootstrap", guard=None)
        return {
            "saved": True,
            "exemplar": str(exemplar_path),
            "contrast": str(contrast_path),
            "title": title,
            "accepted": None,
            "content_ok": None,
            "similarity": None,
            "distance_before": None,
            "distance_after": None,
            "improved": None,
        }

    res = evaluate_rewrite(model, draft_text, final_text)

    if not res["accepted"] and not force:
        reasons = []
        if not res["improved"]:
            reasons.append(
                f"final (distance {res['distance_after']:.1f}) is not closer to the voice than "
                f"the draft (distance {res['distance_before']:.1f}) — nothing to learn. "
                "Pass force=True to save anyway."
            )
        if not res["content_ok"]:
            reasons.append(
                f"meaning drifted (similarity {res['similarity']:.2f} < 0.85) — draft and final "
                "aren't the same content, so this isn't a clean voice pair. Pass force=True to override."
            )
        log_learn(profile, model, draft_text, final_text, title=title, outcome="refused", guard=res)
        return {"saved": False, "reason": " ".join(reasons), **res}

    if not force:
        _check_pair_slots_free(profile, title)
    exemplar_path = add_text(profile_name, final_text, bucket="exemplars", title=title, root=root, overwrite=force)
    contrast_path = add_text(profile_name, draft_text, bucket="contrast", title=title, root=root, overwrite=force)
    log_learn(profile, model, draft_text, final_text, title=title, outcome="saved", guard=res)
    return {
        "saved": True,
        "exemplar": str(exemplar_path),
        "contrast": str(contrast_path),
        "title": title,
        **res,
    }


_SYNC_TIMEOUT_SECONDS = 60


def _sync_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run one git command in the profile root; never prompts, never hangs."""
    return subprocess.run(
        ["git", "-C", str(root), *args],
        env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        timeout=_SYNC_TIMEOUT_SECONDS,
        check=False,
    )


def _sync_error(res: subprocess.CompletedProcess[str]) -> dict:
    return {"status": "error", "message": (res.stderr or "").strip() or "git failed"}


def _sync_merge_in_progress(root: Path) -> bool:
    git_dir = root / ".git"
    if (
        (git_dir / "MERGE_HEAD").exists()
        or (git_dir / "rebase-merge").exists()
        or (git_dir / "rebase-apply").exists()
    ):
        return True
    return bool(_sync_git(root, "ls-files", "-u").stdout.strip())


def _sync_conflict_files(root: Path) -> list[str]:
    res = _sync_git(root, "diff", "--name-only", "--diff-filter=U")
    return [line for line in res.stdout.splitlines() if line.strip()]


def _sync_append_line(path: Path, line: str) -> None:
    """Append `line` to `path` unless a line with that exact text is already there."""
    if path.exists():
        content = path.read_text(encoding="utf-8", errors="ignore")
        if line in content.splitlines():
            return
        prefix = "\n" if content and not content.endswith("\n") else ""
        path.write_text(content + prefix + line + "\n", encoding="utf-8")
    else:
        path.write_text(line + "\n", encoding="utf-8")


def _sync_init(root: Path, remote_url: str) -> dict | None:
    """First-time setup; returns an error dict on failure, None on success."""
    root.mkdir(parents=True, exist_ok=True)
    if not (root / ".git").exists():
        res = _sync_git(root, "init")
        if res.returncode != 0:
            return _sync_error(res)
        # Pin the branch to main explicitly; `git init -b` needs git >= 2.28.
        res = _sync_git(root, "symbolic-ref", "HEAD", "refs/heads/main")
        if res.returncode != 0:
            return _sync_error(res)
    _sync_append_line(root / ".gitattributes", "runs.jsonl merge=union")
    _sync_append_line(root / ".gitignore", ".DS_Store")
    res = _sync_git(root, "remote", "add", "origin", remote_url)
    if res.returncode != 0:
        res = _sync_git(root, "remote", "set-url", "origin", remote_url)
        if res.returncode != 0:
            return _sync_error(res)
    return None


def _sync_run(root: Path, allow_unrelated_histories: bool) -> dict:
    # 1. Commit local changes.
    res = _sync_git(root, "add", "-A")
    if res.returncode != 0:
        return _sync_error(res)
    res = _sync_git(root, "diff", "--cached", "--quiet")
    if res.returncode != 0:
        identity: list[str] = []
        if _sync_git(root, "config", "user.email").returncode != 0:
            identity = ["-c", "user.name=timbro", "-c", "user.email=timbro@localhost"]
        stamp = datetime.now(UTC).isoformat(timespec="seconds")
        res = _sync_git(root, *identity, "commit", "-m", f"timbro sync {stamp}")
        if res.returncode != 0:
            return _sync_error(res)
    # 2. Does the remote branch exist yet?
    res = _sync_git(root, "ls-remote", "--exit-code", "--heads", "origin", "main")
    if res.returncode not in (0, 2):
        return _sync_error(res)
    # 3. Explicit fetch and merge, not pull: the user's pull.rebase / pull.ff
    # config must not change behaviour.
    if res.returncode == 0:
        res = _sync_git(root, "fetch", "origin", "main")
        if res.returncode != 0:
            return _sync_error(res)
        merge_args = ["merge", "--no-edit", "--no-ff"]
        if allow_unrelated_histories:
            merge_args.append("--allow-unrelated-histories")
        merge_args.append("origin/main")
        res = _sync_git(root, *merge_args)
        if res.returncode != 0:
            files = _sync_conflict_files(root)
            if files:
                # Collect the paths first, then abort: the local commit is kept,
                # nothing is auto-resolved, no conflict markers get committed.
                _sync_git(root, "merge", "--abort")
                return {"status": "conflict", "files": files}
            return _sync_error(res)
    # 4. Push, unless nothing was ever committed (empty root, empty remote).
    res = _sync_git(root, "rev-parse", "--verify", "HEAD")
    if res.returncode != 0:
        return {"status": "ok"}
    res = _sync_git(root, "push", "-u", "origin", "main")
    if res.returncode != 0:
        return _sync_error(res)
    return {"status": "ok"}


def sync_profiles(root: str | Path | None = None, init_remote: str | None = None) -> dict:
    """Sync the whole profile root with a git remote.

    Syncs everything under the root (`<name>/exemplars`, `<name>/contrast`,
    `README.md`, `runs.jsonl`); `settings.json` lives outside the root and is
    per-machine, so it is never synced. Merges only -- no rebase, no force push,
    no auto-resolved conflicts.

    Returns one of:

    - {"status": "ok"}
    - {"status": "not-configured"}          no `.git` in the root, no remote given
    - {"status": "conflict", "files": ...}   merge conflicts, left for the user
    - {"status": "error", "message": ...}    a git step failed or timed out

    `init_remote` runs first-time setup (same command on every machine): init on
    branch `main`, write `.gitattributes` (`runs.jsonl merge=union`) and
    `.gitignore` (`.DS_Store`), point `origin` at the remote, then sync. The
    remote must be a private repo -- profiles hold private writing.
    """
    if shutil.which("git") is None:
        raise RuntimeError("git not found on PATH; profile sync needs git")
    base = profile_root(root)
    allow_unrelated_histories = init_remote is not None
    try:
        if not (base / ".git").exists():
            if not allow_unrelated_histories:
                return {"status": "not-configured"}
        elif _sync_merge_in_progress(base):
            # Report and stop: never stage or commit over a merge in progress.
            return {"status": "conflict", "files": _sync_conflict_files(base)}
        if allow_unrelated_histories:
            error = _sync_init(base, init_remote)
            if error is not None:
                return error
        return _sync_run(base, allow_unrelated_histories)
    except subprocess.TimeoutExpired as exc:
        stderr = exc.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        return {"status": "error", "message": (stderr or "").strip() or "timed out"}
