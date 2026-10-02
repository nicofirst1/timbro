"""Issue #158: `accept` validates --threshold and prints similarity at gate precision.

Two owner decisions (issue #158 implementer spec):
- `--threshold` outside [0, 1] is a user error: one clean
  `timbro: error: --threshold must be between 0 and 1` line on stderr, exit 1,
  checked at the start of cmd_accept so a bad threshold never reads files or
  loads a model (same direct print/exit pattern as _require_draft_text).
- The text line prints content similarity with 3 decimals, matching the
  precision the JSON output already carries; the gate itself (evaluate_rewrite)
  still compares the raw float.

Round 3 (#142): the boundary/precision tests run the full accept pipeline, so
their verdict depends on model outputs. The fixture (_DRAFT -> _REVISED) is
rejected with a wide measured margin on BOTH gates (style distance gets worse
by ~47%, similarity 0.71 sits below the 0.85 content gate), so the asserted
verdict cannot flip on cross-platform drift; and the model-output tests skip
on GitHub's macOS runners, whose VMs return wrong MPS embeddings (issue #212,
skip condition defined once in tests/conftest.py).

These tests run the CLI as a subprocess so the real exit path, stdout and
stderr are exercised.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from conftest import skip_model_outputs_on_macos_ci

_DRAFT = "I fixed the parser today. It dropped the last row, so I added a guard and a test."
# Rejected with a wide margin on both gates at the default 0.85 threshold
# (measured on macOS, re-measured on Linux for the round report): the style
# distance gets ~47% WORSE, and the content similarity of 0.71 sits below the
# 0.85 content gate, so neither platform can flip the verdict. The previous
# one-word fixture ("last" -> "final") was rejected by a 0.2-point hair that
# inverted on macOS CI VMs.
_REVISED = (
    "The parser was dropping the last row of the output, which made every file wrong "
    "in the same quiet way, so this morning I fixed it and added a guard and a test."
)


def _run_cli(
    argv: list[str],
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
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


def _sandbox_env(tmp: str) -> dict[str, str]:
    """Point TIMBRO_HOME and TIMBRO_PROFILE_ROOT at tmp dirs, never ~/.timbro."""
    return {
        "TIMBRO_HOME": str(Path(tmp) / "timbro_home"),
        "TIMBRO_PROFILE_ROOT": str(Path(tmp) / "profiles"),
    }


def _write_drafts(tmp: str) -> tuple[Path, Path]:
    original = Path(tmp) / "orig.md"
    original.write_text(_DRAFT, encoding="utf-8")
    revised = Path(tmp) / "rev.md"
    revised.write_text(_REVISED, encoding="utf-8")
    return original, revised


class ThresholdRangeTests(unittest.TestCase):
    """--threshold outside [0, 1] is a clean user error, checked first (issue #158).

    The runs also pass --profile does-not-exist: with an empty profile root that
    would fail later with its own error, so the threshold message being the only
    error proves the check fires before any file read or model load.
    """

    _MESSAGE = "timbro: error: --threshold must be between 0 and 1\n"

    def _assert_threshold_rejected(self, value: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            original, revised = _write_drafts(tmp)
            proc = _run_cli(
                [
                    "accept",
                    str(original),
                    str(revised),
                    "--profile",
                    "does-not-exist",
                    "--threshold",
                    value,
                ],
                env_overrides=_sandbox_env(tmp),
            )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, self._MESSAGE)

    def test_threshold_negative_one_exits_1(self):
        self._assert_threshold_rejected("-1")

    def test_threshold_1_point_5_exits_1(self):
        self._assert_threshold_rejected("1.5")


@skip_model_outputs_on_macos_ci
class ThresholdBoundaryTests(unittest.TestCase):
    """0 and 1 are the meaningful extremes of the gate and must keep working."""

    def test_threshold_0_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, revised = _write_drafts(tmp)
            proc = _run_cli(
                ["accept", str(original), str(revised), "--threshold", "0"],
                env_overrides=_sandbox_env(tmp),
            )
        # #142: this fixture is rejected (not improved: the style distance got
        # worse), which now exits 3; the pin here is that threshold 0 runs and
        # reports content_ok=True (similarity 0.71 clears a threshold of 0).
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertIn("content similarity", proc.stdout)
        self.assertIn("content_ok=True", proc.stdout)
        self.assertNotIn("Traceback", proc.stderr)

    def test_threshold_1_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, revised = _write_drafts(tmp)
            proc = _run_cli(
                ["accept", str(original), str(revised), "--threshold", "1"],
                env_overrides=_sandbox_env(tmp),
            )
        # #142: rejected on both gates (similarity 0.71 never clears a
        # threshold of 1, and the distance got worse), which now exits 3; the
        # pin here is that threshold 1 runs and prints the line.
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertIn("content similarity", proc.stdout)
        self.assertNotIn("Traceback", proc.stderr)


@skip_model_outputs_on_macos_ci
class SimilarityPrecisionTests(unittest.TestCase):
    """The text line carries the JSON's precision: 3 decimals (issue #158)."""

    def test_text_output_prints_three_decimals(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, revised = _write_drafts(tmp)
            proc = _run_cli(
                ["accept", str(original), str(revised)],
                env_overrides=_sandbox_env(tmp),
            )
        # #142: this fixture is rejected on both gates, which now exits 3; the
        # pin here is the 3-decimal precision of the printed similarity.
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertRegex(proc.stdout, r"content similarity \d\.\d{3} ")


if __name__ == "__main__":
    unittest.main()
