"""Multi-file score (issue #224): several candidate drafts in one invocation.

One model load and one profile fit serve every file; each file's own vector
is then encoded exactly as a single-file run encodes it, so per-file numbers
are numerically identical to scoring the file alone. Single-file output stays
byte-identical (proven base-vs-head by the round's snapshot comparison; the
pins here guard the rendering and payload shapes).

The subprocess style follows tests/test_cli_exit_codes.py; runs inherit the
conftest sandbox (TIMBRO_HOME etc. per-test), never the real ~/.timbro.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from conftest import skip_model_outputs_on_macos_ci

import timbro
from timbro import cli
from timbro.profiles import Profile, add_file, init_profile

_DRAFT_A = (
    "I fixed the parser today. It dropped the last row, so I added a guard and a test."
)
_DRAFT_B = (
    "The release notes went out this morning. Two people replied with corrections, "
    "and I folded them in before the afternoon sync."
)


def _run_cli(argv: list[str], stdin_text: str = "") -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = "0"
    return subprocess.run(
        [sys.executable, "-m", "timbro.cli", *argv],
        capture_output=True,
        text=True,
        timeout=600,
        env=env,
        input=stdin_text,
        check=False,
    )


def _write_drafts(tmp: str) -> tuple[str, str]:
    a = Path(tmp) / "a.md"
    a.write_text(_DRAFT_A, encoding="utf-8")
    b = Path(tmp) / "b.md"
    b.write_text(_DRAFT_B, encoding="utf-8")
    return str(a), str(b)


class MultiFileProseTests(unittest.TestCase):
    """Prose mode: one labeled block per file, in argument order."""

    def test_two_files_print_two_labeled_blocks_in_argument_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = _write_drafts(tmp)
            proc = _run_cli(["score", a, b])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        label_a = f"==> {a} <==\n"
        label_b = f"==> {b} <==\n"
        self.assertIn(label_a, out)
        self.assertIn(label_b, out)
        self.assertLess(out.index(label_a), out.index(label_b), out)
        self.assertIn(f"\n\n{label_b}", out)  # blocks separated by one blank line
        self.assertTrue(
            out.startswith(label_a + "distance from your voice:"), out[:120]
        )
        self.assertIn("revise toward your voice:", out)

    def test_two_files_quiet_prints_one_labeled_line_per_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = _write_drafts(tmp)
            proc = _run_cli(["score", a, b, "--quiet"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        lines = proc.stdout.splitlines()
        self.assertEqual(lines[0], f"==> {a} <==")
        self.assertTrue(lines[1].startswith("distance="), lines[1])
        self.assertEqual(lines[3], f"==> {b} <==")
        self.assertTrue(lines[4].startswith("distance="), lines[4])


class MultiFileErrorTests(unittest.TestCase):
    """Fail fast, before any output or model load, naming the file (#224)."""

    def test_missing_file_fails_fast_and_names_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, _ = _write_drafts(tmp)
            missing = str(Path(tmp) / "missing.md")
            proc = _run_cli(["score", a, missing])
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.startswith("timbro: error: "), proc.stderr)
        self.assertIn("missing.md", proc.stderr)

    def test_empty_second_file_names_the_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, _ = _write_drafts(tmp)
            empty = Path(tmp) / "empty.md"
            empty.write_text("", encoding="utf-8")
            proc = _run_cli(["score", a, str(empty)])
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr.strip(), f"timbro: error: {empty} is empty")

    def test_stdin_is_only_valid_as_the_sole_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            _, b = _write_drafts(tmp)
            proc = _run_cli(["score", "-", b], stdin_text=_DRAFT_A)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.startswith("timbro: error: "), proc.stderr)
        self.assertIn("sole input", proc.stderr)

    def test_stdin_as_sole_input_still_scores_without_label(self):
        proc = _run_cli(["score", "-"], stdin_text=_DRAFT_A)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(
            proc.stdout.startswith("distance from your voice:"), proc.stdout
        )
        self.assertNotIn("==>", proc.stdout)

    def test_multi_file_with_several_profiles_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = _write_drafts(tmp)
            proc = _run_cli(["score", a, b, "--profile", "one,two"])
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(proc.stdout, "")
        self.assertTrue(proc.stderr.startswith("timbro: error: "), proc.stderr)
        self.assertIn("one file with several profiles", proc.stderr)


class SingleModelLoadTests(unittest.TestCase):
    """One model load / one profile fit serves every file (#224)."""

    def _score_in_process(self, argv: list[str]) -> list[str]:
        calls: list[str] = []
        real_default_model = cli.default_model

        def counting_default_model():
            calls.append("default_model")
            return real_default_model()

        with (
            mock.patch.object(cli, "default_model", counting_default_model),
            contextlib.redirect_stdout(io.StringIO()),
            mock.patch("sys.argv", ["timbro", *argv]),
        ):
            cli.main()
        return calls

    def test_multi_file_default_path_loads_the_model_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = _write_drafts(tmp)
            calls = self._score_in_process(["score", a, b])
        self.assertEqual(calls, ["default_model"], calls)

    def test_multi_file_profile_path_fits_the_model_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = _write_drafts(tmp)
            init_profile("loadcount", about="single model load probe")
            sample = Path(timbro.__file__).parent / "sample" / "exemplars"
            for f in sorted(sample.glob("*.md")):
                add_file(
                    "loadcount", str(f), bucket="exemplars", overwrite=True, create=True
                )
            calls: list[str] = []
            real_fit = Profile.fit_model

            def counting_fit(profile):
                calls.append("fit_model")
                return real_fit(profile)

            # Profile is a frozen dataclass: patch fit_model at class level.
            with (
                mock.patch.object(Profile, "fit_model", counting_fit),
                contextlib.redirect_stdout(io.StringIO()),
                mock.patch(
                    "sys.argv", ["timbro", "score", a, b, "--profile", "loadcount"]
                ),
            ):
                cli.main()
        self.assertEqual(calls, ["fit_model"], calls)


@skip_model_outputs_on_macos_ci
class MultiFileJsonPayloadTests(unittest.TestCase):
    """JSON array shape + numerical identity vs single-file runs (#224).

    The single and multi runs happen in separate fresh processes, so each
    encodes its drafts from an empty style cache: the comparison exercises
    the real encode path, not a warm-cache shortcut.
    """

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.a = str(Path(cls._tmp.name) / "a.md")
        cls.b = str(Path(cls._tmp.name) / "b.md")
        Path(cls.a).write_text(_DRAFT_A, encoding="utf-8")
        Path(cls.b).write_text(_DRAFT_B, encoding="utf-8")
        cls.single_a = _run_cli(["score", cls.a, "--json"])
        cls.single_b = _run_cli(["score", cls.b, "--json"])
        cls.multi = _run_cli(["score", cls.a, cls.b, "--json"])

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def _payloads(self) -> tuple[dict, dict, list]:
        for proc in (self.single_a, self.single_b, self.multi):
            self.assertEqual(proc.returncode, 0, proc.stderr)
        return (
            json.loads(self.single_a.stdout),
            json.loads(self.single_b.stdout),
            json.loads(self.multi.stdout),
        )

    def test_multi_file_json_is_an_array_with_one_object_per_file(self):
        _, _, multi = self._payloads()
        self.assertIsInstance(multi, list)
        self.assertEqual(len(multi), 2)

    def test_each_object_keeps_the_single_file_json_shape(self):
        single_a, single_b, multi = self._payloads()
        self.assertEqual(list(multi[0].keys()), list(single_a.keys()))
        self.assertEqual(list(multi[1].keys()), list(single_b.keys()))

    def test_per_file_numbers_match_single_file_runs_exactly(self):
        single_a, single_b, multi = self._payloads()
        for single, row in ((single_a, multi[0]), (single_b, multi[1])):
            self.assertEqual(row["distance"], single["distance"])
            self.assertEqual(row["distance_z"], single["distance_z"])
            self.assertEqual(row["on_voice"], single["on_voice"])


if __name__ == "__main__":
    unittest.main()
