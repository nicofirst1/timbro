"""Filesystem errors print one clean `timbro: error: ...` line (issue #154).

Extends #137: main() catches OSError as a whole, so a 300-char profile name
(ENAMETOOLONG) or an init on a read-only root (PermissionError, EROFS) is one
line, not a traceback; TIMBRO_DEBUG still shows the traceback. And `profiles
sync` on a git repo with no `origin` fails up front with a hint to run
`--init`, before any local commit is made. These tests run the CLI as a
subprocess so the real exit path and stderr are exercised.

Sandbox: TIMBRO_HOME / TIMBRO_PROFILE_ROOT / XDG_DATA_HOME point at tmp dirs;
the real ~/.timbro is never touched.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_LONG_NAME = "a" * 300


def _sandbox_env(tmp: str, extra: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    env["TIMBRO_HOME"] = str(Path(tmp) / "home")
    env["TIMBRO_PROFILE_ROOT"] = str(Path(tmp) / "profiles")
    env["XDG_DATA_HOME"] = str(Path(tmp) / "xdg-data")
    if extra:
        env.update(extra)
    return env


def _run_cli_in(tmp: str, argv: list[str], extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "timbro.cli", *argv],
        capture_output=True,
        text=True,
        timeout=120,
        env=_sandbox_env(tmp, extra),
        check=False,
    )


def _run_cli(argv: list[str], extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        return _run_cli_in(tmp, argv, extra)


def _assert_one_clean_error_line(test: unittest.TestCase, proc: subprocess.CompletedProcess[str]) -> None:
    test.assertEqual(proc.returncode, 1, proc.stderr)
    lines = proc.stderr.splitlines()
    test.assertEqual(len(lines), 1, proc.stderr)
    test.assertTrue(lines[0].startswith("timbro: error:"), proc.stderr)
    test.assertNotIn("Traceback", proc.stderr)


class LongProfileNameTests(unittest.TestCase):
    def test_init_300_char_name_prints_one_clean_line(self):
        proc = _run_cli(["profiles", "init", _LONG_NAME])
        _assert_one_clean_error_line(self, proc)


class ReadOnlyRootTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name) / "profiles"
        self.root.mkdir(parents=True)

    def tearDown(self):
        # A read-only root would break TemporaryDirectory cleanup.
        if self.root.exists():
            self.root.chmod(0o755)

    @unittest.skipIf(os.geteuid() == 0, "root ignores read-only directories")
    def test_init_on_read_only_root_prints_one_clean_line(self):
        self.root.chmod(0o555)
        proc = _run_cli_in(self._tmp.name, ["profiles", "init", "x"])
        _assert_one_clean_error_line(self, proc)


class DebugShowsTracebackTests(unittest.TestCase):
    def test_long_name_shows_traceback_then_one_liner(self):
        proc = _run_cli(["profiles", "init", _LONG_NAME], {"TIMBRO_DEBUG": "1"})
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("Traceback", proc.stderr)
        last = proc.stderr.splitlines()[-1]
        self.assertTrue(last.startswith("timbro: error:"), proc.stderr)


class SyncWithoutOriginTests(unittest.TestCase):
    def test_sync_on_git_root_without_origin_fails_before_committing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "profiles"
            profile = root / "demo"
            profile.mkdir(parents=True)
            readme = profile / "README.md"
            readme.write_text("# demo\n", encoding="utf-8")
            env = _sandbox_env(
                tmp,
                {"GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"},
            )
            init = subprocess.run(
                ["git", "init", str(root)], capture_output=True, text=True, env=env, check=False
            )
            self.assertEqual(init.returncode, 0, init.stderr)

            proc = _run_cli_in(tmp, ["profiles", "sync"])

            head = subprocess.run(
                ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
            )
            status = subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=False,
            )
        self.assertNotEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("--init", proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertNotEqual(head.returncode, 0, "a commit was made")
        # Still untracked, not staged: sync stopped before doing anything.
        self.assertTrue(status.stdout.startswith("?? demo/"), status.stdout)


if __name__ == "__main__":
    unittest.main()
