"""Expected user errors print one clean `timbro: error: ...` line (issue #137).

The CLI must catch FileNotFoundError, FileExistsError, IsADirectoryError and
UnicodeDecodeError in main() and print a one-line message to stderr; anything
else must still traceback. These tests run the CLI as a subprocess so the real
exit path and stderr are exercised.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_DRAFT = "I fixed the parser today. It dropped the last row, so I added a guard and a test."


def _run_cli(argv: list[str], env_overrides: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "timbro.cli", *argv],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        check=False,
    )


def _assert_clean_error(test: unittest.TestCase, proc: subprocess.CompletedProcess[str]) -> None:
    test.assertEqual(proc.returncode, 1, proc.stderr)
    lines = proc.stderr.splitlines()
    test.assertTrue(
        any(line.startswith("timbro: error:") for line in lines),
        f"no 'timbro: error:' line in stderr:\n{proc.stderr}",
    )
    test.assertNotIn("Traceback", proc.stderr)


class DuplicateAddFileTests(unittest.TestCase):
    def test_second_add_file_without_overwrite_prints_clean_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "note.md"
            source.write_text(_DRAFT, encoding="utf-8")
            env = {"TIMBRO_PROFILE_ROOT": str(Path(tmp) / "profiles")}
            first = _run_cli(
                ["profiles", "add-file", "demo", str(source), "--to", "exemplars"], env
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            second = _run_cli(
                ["profiles", "add-file", "demo", str(source), "--to", "exemplars"], env
            )
        _assert_clean_error(self, second)
        self.assertIn("Destination already exists", second.stderr)


class MissingFileTests(unittest.TestCase):
    def test_check_missing_file_prints_clean_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "missing.md")
            proc = _run_cli(["check", missing])
        _assert_clean_error(self, proc)
        self.assertIn("missing.md", proc.stderr)

    def test_score_missing_file_prints_clean_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "missing.md")
            proc = _run_cli(["score", missing])
        _assert_clean_error(self, proc)
        self.assertIn("missing.md", proc.stderr)


class NonUtf8FileTests(unittest.TestCase):
    def test_check_non_utf8_file_prints_clean_error_naming_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            latin1 = Path(tmp) / "latin1.md"
            latin1.write_bytes(b"caf\xe9 latte\n")
            proc = _run_cli(["check", str(latin1)])
        _assert_clean_error(self, proc)
        self.assertIn(str(latin1), proc.stderr)
        self.assertIn("not UTF-8", proc.stderr)


class UnknownProfileTests(unittest.TestCase):
    def test_score_unknown_profile_prints_clean_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            draft.write_text(_DRAFT, encoding="utf-8")
            env = {"TIMBRO_PROFILE_ROOT": str(Path(tmp) / "profiles")}
            proc = _run_cli(["score", str(draft), "--profile", "no-such-profile"], env)
        _assert_clean_error(self, proc)
        self.assertIn("no-such-profile", proc.stderr)


if __name__ == "__main__":
    unittest.main()
