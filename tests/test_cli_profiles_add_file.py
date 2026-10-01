"""`profiles add-file` reports a missing detex as one clean stderr line (issue #147).

Without detex on PATH, a `.tex` add-file used to print the full RuntimeError
traceback; the CLI must catch it and print `timbro: error: <exc>` instead,
like `cmd_profiles_sync` does for its RuntimeError.
"""

from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from timbro.cli import main


def _run(argv: list[str]) -> tuple[str, str, int]:
    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            with patch("sys.argv", ["timbro", *argv]):
                main()
        except SystemExit as exc:
            code = exc.code or 0
    return stdout.getvalue(), stderr.getvalue(), code


class AddFileMissingDetexTests(unittest.TestCase):
    def test_tex_without_detex_prints_one_error_line_and_exits_1(self):
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "paper.tex"
            src.write_text("\\section{Intro}\nThis is the introduction.\n", encoding="utf-8")

            # No detex anywhere on PATH: latex.detex_text raises RuntimeError.
            with patch("shutil.which", return_value=None):
                out, err, code = _run(["profiles", "add-file", "demo", str(src), "--to", "exemplars"])

        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", err)
        self.assertEqual(err.count("\n"), 1, f"expected a single stderr line, got: {err!r}")
        self.assertTrue(err.startswith("timbro: error: "), f"unexpected stderr: {err!r}")
        self.assertIn("detex is not installed", err)
        self.assertEqual(out, "")
