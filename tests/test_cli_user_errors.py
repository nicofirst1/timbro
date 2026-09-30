"""Expected user errors print one clean `timbro: error: ...` line (issue #137).

The CLI must catch FileNotFoundError, FileExistsError, IsADirectoryError and
UnicodeDecodeError in main() and print a one-line message to stderr; anything
else must still traceback. These tests run the CLI as a subprocess so the real
exit path and stderr are exercised.
"""

from __future__ import annotations

import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from timbro.cli import main

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


class DebugShowsTracebackTests(unittest.TestCase):
    """Debug mode (TIMBRO_DEBUG or `"debug": true` in settings.json) prints the
    full traceback before the one-line error, with the same exit code."""

    def _missing(self, tmp: str) -> str:
        return str(Path(tmp) / "missing.md")

    def _assert_traceback_then_error(self, proc: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("Traceback", proc.stderr)
        self.assertIn("FileNotFoundError", proc.stderr)
        self.assertTrue(proc.stderr.splitlines()[-1].startswith("timbro: error:"), proc.stderr)

    def test_env_var_enables_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run_cli(["check", self._missing(tmp)], {"TIMBRO_DEBUG": "1"})
        self._assert_traceback_then_error(proc)

    def test_settings_json_enables_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            (home / "settings.json").write_text('{"debug": true}', encoding="utf-8")
            proc = _run_cli(["check", self._missing(tmp)], {"TIMBRO_HOME": str(home)})
        self._assert_traceback_then_error(proc)

    def test_malformed_settings_still_prints_the_original_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            (home / "settings.json").write_text("{not json", encoding="utf-8")
            proc = _run_cli(["check", self._missing(tmp)], {"TIMBRO_HOME": str(home)})
        _assert_clean_error(self, proc)
        self.assertIn("missing.md", proc.stderr)

    def test_learn_error_shows_traceback_in_debug(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = _run_cli(
                ["profiles", "learn", "nope", "--draft", self._missing(tmp), "--final", self._missing(tmp)],
                {"TIMBRO_DEBUG": "1", "TIMBRO_PROFILE_ROOT": str(Path(tmp) / "profiles")},
            )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("Traceback", proc.stderr)


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


class AcceptNamesTheFailingFileTests(unittest.TestCase):
    def test_accept_bad_revised_names_revised_not_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "orig.md"
            original.write_text(_DRAFT, encoding="utf-8")
            revised = Path(tmp) / "rev-latin1.md"
            revised.write_bytes(b"caf\xe9 latte\n")
            proc = _run_cli(["accept", str(original), str(revised)])
        _assert_clean_error(self, proc)
        self.assertIn(str(revised), proc.stderr)
        self.assertNotIn(str(original), proc.stderr)


class CorpusDecodeErrorDoesNotBlameTheDraftTests(unittest.TestCase):
    def test_score_with_bad_corpus_file_does_not_name_the_draft(self):
        # add-file copies bytes without UTF-8 validation, so a latin-1 file can
        # enter a corpus legally; the error must not claim the draft is the
        # non-UTF-8 one, and must not name any file it is not sure of.
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            draft.write_text(_DRAFT, encoding="utf-8")
            exemplars = Path(tmp) / "profiles" / "corrupt" / "exemplars"
            exemplars.mkdir(parents=True)
            (exemplars / "good.md").write_text(_DRAFT, encoding="utf-8")
            (exemplars / "old-note.md").write_bytes(b"caf\xe9 latte\n")
            env = {"TIMBRO_PROFILE_ROOT": str(Path(tmp) / "profiles")}
            proc = _run_cli(["score", str(draft), "--profile", "corrupt"], env)
        _assert_clean_error(self, proc)
        self.assertNotIn(str(draft), proc.stderr)


class UncaughtExceptionsStillTracebackTests(unittest.TestCase):
    def test_exception_outside_the_caught_types_still_propagates(self):
        # Bugs must stay loud: a RuntimeError from a command must propagate out
        # of main() (the interpreter then prints the traceback), not be turned
        # into a clean 'timbro: error:' line + sys.exit(1).
        stderr = io.StringIO()
        with (
            mock.patch(
                "timbro.cli.cmd_check", side_effect=RuntimeError("injected bug must stay loud")
            ),
            contextlib.redirect_stderr(stderr),
            mock.patch("sys.argv", ["timbro", "check", "unused.md"]),
            self.assertRaises(RuntimeError),
        ):
            main()
        self.assertNotIn("timbro: error:", stderr.getvalue())
        self.assertNotIn("Traceback", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
