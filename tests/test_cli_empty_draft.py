"""Empty drafts are user errors, not results (issue #152).

`score`, `check` and `accept` print one clean `timbro: error: ... is empty`
line to stderr and exit 1 when the draft text is empty
(`text.strip() == ""`, so whitespace-only counts too); nothing goes to
stdout. JSON output must never contain NaN/Infinity tokens: the CLI's single
dumps helper maps non-finite floats to null. These tests run the CLI as a
subprocess so the real exit path, stdout and stderr are exercised.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_DRAFT = "I fixed the parser today. It dropped the last row, so I added a guard and a test."


def _run_cli(
    argv: list[str],
    stdin_text: str | None = None,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-m", "timbro.cli", *argv],
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        check=False,
    )


def _assert_empty_draft_error(test: unittest.TestCase, proc: subprocess.CompletedProcess[str]) -> None:
    test.assertEqual(proc.returncode, 1, proc.stderr)
    test.assertEqual(proc.stdout, "")
    test.assertEqual(proc.stderr, "timbro: error: draft is empty\n")


class ScoreEmptyDraftTests(unittest.TestCase):
    def test_score_stdin_empty_text(self):
        proc = _run_cli(["score", "-"], stdin_text="")
        _assert_empty_draft_error(self, proc)

    def test_score_stdin_empty_json(self):
        proc = _run_cli(["score", "-", "--json"], stdin_text="")
        _assert_empty_draft_error(self, proc)

    def test_score_stdin_whitespace_only_text(self):
        proc = _run_cli(["score", "-"], stdin_text="   \n\t\n")
        _assert_empty_draft_error(self, proc)

    def test_score_stdin_whitespace_only_json(self):
        proc = _run_cli(["score", "-", "--json"], stdin_text="   \n\t\n")
        _assert_empty_draft_error(self, proc)

    def test_score_empty_file_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.md"
            empty.write_text("", encoding="utf-8")
            proc = _run_cli(["score", str(empty)])
        _assert_empty_draft_error(self, proc)

    def test_score_empty_file_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.md"
            empty.write_text("", encoding="utf-8")
            proc = _run_cli(["score", str(empty), "--json"])
        _assert_empty_draft_error(self, proc)

    def test_score_whitespace_only_file_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws.md"
            ws.write_text("  \n\t\n", encoding="utf-8")
            proc = _run_cli(["score", str(ws)])
        _assert_empty_draft_error(self, proc)

    def test_score_whitespace_only_file_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            ws = Path(tmp) / "ws.md"
            ws.write_text("  \n\t\n", encoding="utf-8")
            proc = _run_cli(["score", str(ws), "--json"])
        _assert_empty_draft_error(self, proc)


class CheckEmptyDraftTests(unittest.TestCase):
    def test_check_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty.md"
            empty.write_text("", encoding="utf-8")
            proc = _run_cli(["check", str(empty)])
        _assert_empty_draft_error(self, proc)

    def test_check_stdin_empty_text(self):
        proc = _run_cli(["check", "-"], stdin_text="")
        _assert_empty_draft_error(self, proc)

    def test_check_stdin_whitespace_only_json(self):
        proc = _run_cli(["check", "-", "--json"], stdin_text=" \n\t")
        _assert_empty_draft_error(self, proc)


class AcceptEmptyDraftTests(unittest.TestCase):
    def test_accept_empty_original_names_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "orig.md"
            original.write_text("", encoding="utf-8")
            revised = Path(tmp) / "rev.md"
            revised.write_text(_DRAFT, encoding="utf-8")
            proc = _run_cli(["accept", str(original), str(revised)])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, f"timbro: error: {original} is empty\n")

    def test_accept_whitespace_only_revised_names_revised_not_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "orig.md"
            original.write_text(_DRAFT, encoding="utf-8")
            revised = Path(tmp) / "rev.md"
            revised.write_text("  \n\t\n", encoding="utf-8")
            proc = _run_cli(["accept", str(original), str(revised)])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, f"timbro: error: {revised} is empty\n")
        self.assertNotIn(str(original), proc.stderr)


class EmptyDraftCheckedBeforeProfileLoadTests(unittest.TestCase):
    """The empty check must fire before any profile or model load (issue #152).

    With empty stdin and an unknown profile, the draft error wins: an edit
    that moves _require_draft_text after the profile/model block flips this
    to the unknown-profile error (or a traceback) and fails here.
    """

    def test_score_empty_stdin_unknown_profile_reports_the_draft(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {"TIMBRO_PROFILE_ROOT": str(Path(tmp) / "profiles")}
            proc = _run_cli(
                ["score", "-", "--profile", "nonexistent"], stdin_text="", env_overrides=env
            )
        _assert_empty_draft_error(self, proc)
        self.assertNotIn("nonexistent", proc.stderr)


class DumpJsonNonFiniteTests(unittest.TestCase):
    """The CLI's single dumps helper maps non-finite floats to null (issue #152).

    The helper is imported inside the tests so a missing implementation shows
    up as this test's failure without masking the subprocess tests above.
    """

    @staticmethod
    def _reject_constant(name: str) -> float:
        raise ValueError(f"non-finite constant in JSON output: {name}")

    def test_nested_non_finite_floats_become_null(self):
        from timbro.cli import _dump_json

        payload = {
            "z": float("nan"),
            "list": [1, float("inf"), -float("inf"), {"deep": float("nan")}],
            "text": "ok",
            "none": None,
        }
        out = _dump_json(payload, indent=2)
        parsed = json.loads(out, parse_constant=self._reject_constant)
        self.assertIsNone(parsed["z"])
        self.assertEqual(parsed["list"], [1, None, None, {"deep": None}])
        self.assertEqual(parsed["text"], "ok")
        self.assertIsNone(parsed["none"])

    def test_finite_values_and_indent_choices_are_untouched(self):
        from timbro.cli import _dump_json

        payload = {"a": 0.5, "b": -2, "c": [1.25], "d": "ok", "e": None}
        self.assertEqual(json.loads(_dump_json(payload, indent=2)), payload)
        self.assertEqual(json.loads(_dump_json(payload)), payload)
        self.assertIn("\n", _dump_json(payload, indent=2))
        self.assertNotIn("\n", _dump_json(payload))


if __name__ == "__main__":
    unittest.main()
