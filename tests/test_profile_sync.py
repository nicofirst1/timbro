"""Tests for git-based profile-root sync (`timbro profiles sync`).

All local, no network: a bare repo in tmp_path plays the remote, two profile
roots play two machines.
"""

from __future__ import annotations

import contextlib
import io
import json
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from timbro.cli import main
from timbro.profiles import sync_profiles

pytestmark = pytest.mark.skipif(
    shutil.which("git") is None, reason="git is required for profile sync tests"
)


@pytest.fixture(autouse=True)
def git_env(monkeypatch):
    """Deterministic git: no global/system config, and an identity for CI."""
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "timbro-test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "timbro-test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "timbro-test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "timbro-test@example.com")


def _git(root: Path, *args: str) -> str:
    res = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    assert res.returncode == 0, f"git {args} failed: {res.stderr}"
    return res.stdout


def _git_fails(root: Path, *args: str) -> bool:
    res = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
    return res.returncode != 0


def _bare_remote(tmp_path: Path, name: str = "profiles-remote.git") -> Path:
    remote = tmp_path / name
    subprocess.run(["git", "init", "--bare", str(remote)], check=True, capture_output=True, text=True)
    return remote


def _seed_profile(root: Path, name: str = "demo", marker: str = "shared") -> Path:
    prof = root / name
    (prof / "exemplars").mkdir(parents=True, exist_ok=True)
    (prof / "contrast").mkdir(parents=True, exist_ok=True)
    (prof / "README.md").write_text(f"# {name}\n\n{marker}\n", encoding="utf-8")
    (prof / "exemplars" / "post.md").write_text(f"{marker} exemplar text\n", encoding="utf-8")
    return prof


def _run_cli(monkeypatch, root: Path, *argv: str) -> tuple[str, str, int]:
    monkeypatch.setenv("TIMBRO_PROFILE_ROOT", str(root))
    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            with patch("sys.argv", ["timbro", "profiles", *argv]):
                main()
        except SystemExit as exc:
            code = exc.code or 0
    return stdout.getvalue(), stderr.getvalue(), code


def test_not_configured_is_silent_no_op(tmp_path):
    root = tmp_path / "profiles"
    result = sync_profiles(root)
    assert result == {"status": "not-configured"}
    assert not (root / ".git").exists()
    assert not root.exists()


def test_nested_root_without_own_git_is_not_configured(tmp_path):
    parent = tmp_path / "parent"
    parent.mkdir()
    _git(parent, "init")
    root = parent / "profiles"
    root.mkdir()
    _seed_profile(root)
    before = _git(parent, "status", "--porcelain")
    assert _git_fails(parent, "rev-parse", "--verify", "HEAD")  # unborn HEAD

    result = sync_profiles(root)

    assert result == {"status": "not-configured"}
    assert not (root / ".git").exists()
    assert _git(parent, "status", "--porcelain") == before
    assert _git_fails(parent, "rev-parse", "--verify", "HEAD")  # still no commits


def test_init_empty_root_empty_remote_is_ok(tmp_path):
    remote = _bare_remote(tmp_path)
    root = tmp_path / "machine-a"
    result = sync_profiles(root, init_remote=str(remote))
    assert result == {"status": "ok"}


def test_init_pushes_and_second_machine_merges(tmp_path):
    remote = _bare_remote(tmp_path)
    a, b = tmp_path / "machine-a", tmp_path / "machine-b"
    _seed_profile(a, "demo", "from-a")
    assert sync_profiles(a, init_remote=str(remote)) == {"status": "ok"}

    _seed_profile(b, "other", "from-b")
    assert sync_profiles(b, init_remote=str(remote)) == {"status": "ok"}

    # B pulled A's profile instead of recreating it...
    assert (b / "demo" / "exemplars" / "post.md").read_text(encoding="utf-8") == "from-a exemplar text\n"
    # ...and the remote has both machines' files.
    remote_files = _git(remote, "ls-tree", "-r", "--name-only", "main")
    assert "demo/exemplars/post.md" in remote_files
    assert "other/exemplars/post.md" in remote_files


def test_concurrent_runs_jsonl_appends_merge_losslessly(tmp_path):
    remote = _bare_remote(tmp_path)
    a, b = tmp_path / "machine-a", tmp_path / "machine-b"
    prof_a = _seed_profile(a, "demo", "shared")
    (prof_a / "runs.jsonl").write_text('{"run": 1}\n', encoding="utf-8")
    assert sync_profiles(a, init_remote=str(remote)) == {"status": "ok"}

    prof_b = _seed_profile(b, "demo", "shared")
    (prof_b / "runs.jsonl").write_text('{"run": 1}\n', encoding="utf-8")
    assert sync_profiles(b, init_remote=str(remote)) == {"status": "ok"}

    # Both machines append offline.
    with open(prof_a / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write('{"run": "a"}\n')
    with open(prof_b / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write('{"run": "b"}\n')

    assert sync_profiles(a) == {"status": "ok"}
    assert sync_profiles(b) == {"status": "ok"}
    assert sync_profiles(a) == {"status": "ok"}

    for line in ('{"run": 1}', '{"run": "a"}', '{"run": "b"}'):
        assert line in (prof_a / "runs.jsonl").read_text(encoding="utf-8")
        assert line in (prof_b / "runs.jsonl").read_text(encoding="utf-8")


def test_conflicting_exemplar_is_reported_never_resolved(tmp_path):
    remote = _bare_remote(tmp_path)
    a, b = tmp_path / "machine-a", tmp_path / "machine-b"
    _seed_profile(a, "demo", "shared")
    assert sync_profiles(a, init_remote=str(remote)) == {"status": "ok"}
    _seed_profile(b, "demo", "shared")
    assert sync_profiles(b, init_remote=str(remote)) == {"status": "ok"}

    # Same file, different offline edits.
    (a / "demo" / "exemplars" / "post.md").write_text("version A\n", encoding="utf-8")
    (b / "demo" / "exemplars" / "post.md").write_text("version B\n", encoding="utf-8")
    assert sync_profiles(a) == {"status": "ok"}

    result = sync_profiles(b)

    assert result["status"] == "conflict"
    assert "demo/exemplars/post.md" in result["files"]
    assert not (b / ".git" / "MERGE_HEAD").exists()
    # Local edit kept, local commit intact, nothing auto-resolved.
    assert (b / "demo" / "exemplars" / "post.md").read_text(encoding="utf-8") == "version B\n"
    assert _git(b, "show", "HEAD:demo/exemplars/post.md") == "version B\n"


def test_merge_in_progress_by_hand_is_conflict_and_nothing_committed(tmp_path):
    remote = _bare_remote(tmp_path)
    root = tmp_path / "machine-a"
    _seed_profile(root, "demo", "shared")
    assert sync_profiles(root, init_remote=str(remote)) == {"status": "ok"}

    # Hand-craft a merge left in progress with a real conflict.
    _git(root, "checkout", "-b", "side")
    (root / "demo" / "README.md").write_text("# demo\n\nside edit\n", encoding="utf-8")
    _git(root, "commit", "-am", "side")
    _git(root, "checkout", "main")
    (root / "demo" / "README.md").write_text("# demo\n\nmain edit\n", encoding="utf-8")
    _git(root, "commit", "-am", "main")
    assert subprocess.run(
        ["git", "-C", str(root), "merge", "--no-commit", "side"],
        capture_output=True,
        text=True,
        check=False,
    ).returncode != 0  # conflicted, merge left in progress

    head_before = _git(root, "rev-parse", "HEAD")
    result = sync_profiles(root)

    assert result["status"] == "conflict"
    # Nothing new committed: HEAD unchanged, conflict markers never reach history.
    assert _git(root, "rev-parse", "HEAD") == head_before
    assert "<<<<<<<" not in _git(root, "show", "HEAD:demo/README.md")
    # The in-progress merge is left for the user to resolve.
    assert (root / ".git" / "MERGE_HEAD").exists()
    assert _git(root, "ls-files", "-u") != ""


def test_reinit_does_not_duplicate_attribute_lines(tmp_path):
    remote = _bare_remote(tmp_path)
    root = tmp_path / "machine-a"
    sync_profiles(root, init_remote=str(remote))
    attrs = (root / ".gitattributes").read_text(encoding="utf-8")
    ignore = (root / ".gitignore").read_text(encoding="utf-8")
    assert attrs.count("runs.jsonl merge=union") == 1
    assert ignore.count(".DS_Store") == 1

    sync_profiles(root, init_remote=str(remote))

    assert (root / ".gitattributes").read_text(encoding="utf-8") == attrs
    assert (root / ".gitignore").read_text(encoding="utf-8") == ignore


def test_reinit_new_url_reports_previous_remote_and_warns(tmp_path, monkeypatch):
    remote_a = _bare_remote(tmp_path, "remote-a.git")
    remote_b = _bare_remote(tmp_path, "remote-b.git")
    root = tmp_path / "machine-a"
    assert sync_profiles(root, init_remote=str(remote_a)) == {"status": "ok"}

    result = sync_profiles(root, init_remote=str(remote_b))

    assert result["status"] == "ok"
    assert result["previous_remote"] == str(remote_a)
    assert _git(root, "remote", "get-url", "origin").strip() == str(remote_b)

    # The human CLI warns on stderr, naming both URLs.
    out, err, code = _run_cli(monkeypatch, root, "sync", "--init", str(remote_a))
    assert code == 0
    assert out == "synced\n"
    assert f"warning: sync --init repointed origin from {remote_b} to {remote_a}" in err

    # In --json mode the key is part of the payload, with no extra stderr line.
    out, err, code = _run_cli(monkeypatch, root, "sync", "--init", str(remote_b), "--json")
    assert code == 0
    assert json.loads(out) == {"status": "ok", "previous_remote": str(remote_a)}
    assert err == ""


def test_reinit_same_url_has_no_previous_remote_and_no_warning(tmp_path, monkeypatch):
    remote = _bare_remote(tmp_path)
    root = tmp_path / "machine-a"
    assert sync_profiles(root, init_remote=str(remote)) == {"status": "ok"}

    result = sync_profiles(root, init_remote=str(remote))

    assert result == {"status": "ok"}

    out, err, code = _run_cli(monkeypatch, root, "sync", "--init", str(remote))
    assert code == 0
    assert out == "synced\n"
    assert err == ""


def test_first_init_has_no_previous_remote_and_no_warning(tmp_path, monkeypatch):
    remote = _bare_remote(tmp_path)
    root = tmp_path / "machine-a"

    result = sync_profiles(root, init_remote=str(remote))

    assert result == {"status": "ok"}

    out, err, code = _run_cli(monkeypatch, tmp_path / "machine-cli", "sync", "--init", str(remote))
    assert code == 0
    assert out == "synced\n"
    assert err == ""


def test_bogus_remote_is_error_cli_exit_2_no_traceback(tmp_path, monkeypatch):
    result = sync_profiles(tmp_path / "machine-a", init_remote=str(tmp_path / "no-such-remote.git"))
    assert result["status"] == "error"
    assert result["message"]

    out, err, code = _run_cli(
        monkeypatch, tmp_path / "machine-cli", "sync", "--init", str(tmp_path / "also-bogus.git")
    )
    assert code == 2
    assert "sync failed" in err
    assert "Traceback" not in out and "Traceback" not in err


def test_conflict_cli_exit_1(tmp_path, monkeypatch):
    remote = _bare_remote(tmp_path)
    a, b = tmp_path / "machine-a", tmp_path / "machine-b"
    _seed_profile(a, "demo", "shared")
    assert sync_profiles(a, init_remote=str(remote)) == {"status": "ok"}
    _seed_profile(b, "demo", "shared")
    assert sync_profiles(b, init_remote=str(remote)) == {"status": "ok"}
    (a / "demo" / "exemplars" / "post.md").write_text("version A\n", encoding="utf-8")
    (b / "demo" / "exemplars" / "post.md").write_text("version B\n", encoding="utf-8")
    assert sync_profiles(a) == {"status": "ok"}

    out, err, code = _run_cli(monkeypatch, b, "sync")

    assert code == 1
    assert "conflict in: demo/exemplars/post.md" in err
    assert 'see README "Resolving a sync conflict"' in err
    assert "Traceback" not in out and "Traceback" not in err


def test_unconfigured_cli_sync_exits_zero(tmp_path, monkeypatch):
    root = tmp_path / "profiles"
    out, _err, code = _run_cli(monkeypatch, root, "sync")
    assert code == 0
    assert "profile sync not configured" in out
    assert not (root / ".git").exists()


def test_profiles_init_tip_printed_only_for_first_profile(tmp_path, monkeypatch):
    root = tmp_path / "profiles"
    tip = "tip: using Timbro on another machine? run 'timbro profiles sync --init <url>' before creating profiles"

    _out, err, code = _run_cli(monkeypatch, root, "init", "demo")
    assert code == 0
    assert tip in err

    _out, err, code = _run_cli(monkeypatch, root, "init", "second")
    assert code == 0
    assert err == ""

    # An init under a configured root prints nothing, even with no profiles yet.
    configured = tmp_path / "configured-root"
    (configured / ".git").mkdir(parents=True)
    _out, err, code = _run_cli(monkeypatch, configured, "init", "third")
    assert code == 0
    assert err == ""


def test_no_git_identity_falls_back_to_timbro_identity(tmp_path, monkeypatch):
    for var in ("GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL", "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL"):
        monkeypatch.delenv(var, raising=False)
    remote = _bare_remote(tmp_path)
    root = tmp_path / "machine-a"
    _seed_profile(root, "demo", "from-a")

    result = sync_profiles(root, init_remote=str(remote))

    assert result == {"status": "ok"}
    assert _git(root, "log", "-1", "--format=%ae").strip() == "timbro@localhost"


def test_no_git_identity_syncs_merge_with_seeded_remote_main(tmp_path, monkeypatch):
    # No identity from anywhere: config is already /dev/null via the fixture;
    # drop the env identities (and EMAIL) too, and make git refuse to
    # auto-detect, like machines where auto-detection fails (e.g. Docker).
    for var in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "EMAIL",
    ):
        monkeypatch.delenv(var, raising=False)

    remote = _bare_remote(tmp_path)
    # Seed the remote's main with one commit from a third, unrelated repo.
    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init")
    _git(seed, "symbolic-ref", "HEAD", "refs/heads/main")
    (seed / "README.md").write_text("seed\n", encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "-c", "user.name=seeder", "-c", "user.email=seeder@example.com", "commit", "-m", "seed")
    _git(seed, "push", str(remote), "main")

    root = tmp_path / "machine-b"
    root.mkdir()
    _git(root, "init")
    _git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(root, "config", "user.useConfigOnly", "true")
    _seed_profile(root, "demo", "from-b")

    result = sync_profiles(root, init_remote=str(remote))

    assert result == {"status": "ok"}
    remote_files = _git(remote, "ls-tree", "-r", "--name-only", "main")
    assert "demo/README.md" in remote_files
    assert "demo/exemplars/post.md" in remote_files
    # Root HEAD is the merge commit: authored and committed with the fallback,
    # same identity the sync commit gets.
    head = _git(root, "log", "-1", "--format=%an|%ae|%cn|%ce").strip()
    assert head == "timbro|timbro@localhost|timbro|timbro@localhost"


def test_configured_identity_survives_sync_merge(tmp_path, monkeypatch):
    # A user with a configured identity keeps it on the merge commit; the
    # fallback must never override it. Env identities are dropped so the
    # repo-local config below is the only identity source, like real machines.
    for var in (
        "GIT_AUTHOR_NAME",
        "GIT_AUTHOR_EMAIL",
        "GIT_COMMITTER_NAME",
        "GIT_COMMITTER_EMAIL",
        "EMAIL",
    ):
        monkeypatch.delenv(var, raising=False)

    remote = _bare_remote(tmp_path)
    seed = tmp_path / "seed"
    seed.mkdir()
    _git(seed, "init")
    _git(seed, "symbolic-ref", "HEAD", "refs/heads/main")
    (seed / "README.md").write_text("seed\n", encoding="utf-8")
    _git(seed, "add", "-A")
    _git(seed, "-c", "user.name=seeder", "-c", "user.email=seeder@example.com", "commit", "-m", "seed")
    _git(seed, "push", str(remote), "main")

    root = tmp_path / "machine-c"
    root.mkdir()
    _git(root, "init")
    _git(root, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(root, "config", "user.name", "nico")
    _git(root, "config", "user.email", "nico@example.com")
    _seed_profile(root, "demo", "from-c")

    result = sync_profiles(root, init_remote=str(remote))

    assert result == {"status": "ok"}
    # Remote main's tip is the merge commit (two parents) and it keeps the
    # user's own identity; the fallback never leaks into the history.
    author_email, committer_email, parents = _git(remote, "log", "-1", "main", "--format=%ae|%ce|%p").strip().split("|")
    assert author_email == "nico@example.com"
    assert committer_email == "nico@example.com"
    assert len(parents.split()) == 2
    assert "timbro@localhost" not in _git(remote, "log", "main", "--format=%an <%ae> %cn <%ce>")
