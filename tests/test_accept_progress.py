"""Issue #225: `accept` prints stage progress on stderr so a working run is
distinguishable from a hung one.

A first `timbro accept` run silently downloads and loads the content-similarity
embedder (all-MiniLM-L6-v2, which `score` never touches) before encoding both
drafts; with no output until the single verdict line, an operator killed a
healthy run at 120 seconds believing it hung. The fix, per the issue's brief:

- cmd_accept reports the model-loading stage on stderr, naming each model
  (spaCy pipeline, style embedder, content embedder).
- evaluate_rewrite reports the encoding stages (original, revised) on stderr.
- the shared text-embedding loader (timbro.text._model) prints a first-run
  download notice naming the model, mirroring the spaCy loader's cold-start
  notice (spacy_model._install_and_load); it fires for any command that
  triggers the download, not just accept.

stdout contracts stay byte-identical (verified base-vs-head on the same
fixtures): the prose verdict line and the `--json` payload carry no stage
lines -- every stage line goes to stderr. User-error paths (bad threshold,
empty draft, unknown profile) still exit before any stage line.

Subprocess style follows tests/test_issue_158.py / test_cli_exit_codes.py;
the fixtures are the same measured-margin pairs (see those files' comments),
and model-output runs skip on GitHub's macOS runners (#212). The download
notice tests mock SentenceTransformer, so they run everywhere.
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
from unittest.mock import MagicMock, patch

from conftest import skip_model_outputs_on_macos_ci

from timbro import text

# transformers.utils.logging snapshots the progress-bar state at import time
# (`_tqdm_active = not hf_hub_utils.are_progress_bars_disabled()`), and
# patching "sentence_transformers.SentenceTransformer" below imports
# transformers BEFORE any loader body ran its env setdefault. Setting the same
# variable the loaders set (os.environ.setdefault, never overriding a user's
# explicit choice) at module import keeps the 'Loading weights' tqdm bar off
# for every later in-process model load, so stderr-pinning tests stay
# order-independent (test_model_loaders.py has the same latent pattern but
# sorts after the tests that pin stderr).
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

# sentence_transformers.SentenceTransformer is imported lazily inside the
# loader bodies, so patching the source module intercepts the call site
# (same technique as tests/test_model_loaders.py).
ST = "sentence_transformers.SentenceTransformer"
CONTENT_MODEL = "all-MiniLM-L6-v2"

# Accepted pair from test_cli_exit_codes.py: improves the style distance by a
# wide measured margin (12.6% of distance_before on macOS, 12.4% on Linux) and
# clears the content gate (similarity 0.935 measured), so the verdict cannot
# flip on cross-platform drift.
_PASS_DRAFT = (
    "I fixed the parser today. It dropped the last row, so I added a guard and a test."
)
_REVISED_OK = (
    "I fixed the parser today. It was dropping the last row, and so I added a guard "
    "and a test so the last row would not go missing again."
)
# Rejected pair (also from test_cli_exit_codes.py): semantically unrelated, so
# the content gate rejects it and accept exits 3.
_REVISED_BAD = (
    "A cat slept on the warm windowsill all afternoon while it rained outside."
)

# The stage lines, in the order the run must show them on stderr (issue #225
# acceptance): model-loading stage naming each model, then the encoding stages.
_LOADING_STAGE = (
    "timbro: loading models: en_core_web_sm (spaCy), "
    "StyleDistance/styledistance (style), all-MiniLM-L6-v2 (content)..."
)
_ENCODING_ORIGINAL = "timbro: encoding original..."
_ENCODING_REVISED = "timbro: encoding revised..."
_STAGE_LINES = (_LOADING_STAGE, _ENCODING_ORIGINAL, _ENCODING_REVISED)


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


def _write_drafts(tmp: str, revised_text: str) -> tuple[Path, Path]:
    original = Path(tmp) / "orig.md"
    original.write_text(_PASS_DRAFT, encoding="utf-8")
    revised = Path(tmp) / "rev.md"
    revised.write_text(revised_text, encoding="utf-8")
    return original, revised


def _sandbox_env(tmp: str) -> dict[str, str]:
    """Point TIMBRO_HOME and TIMBRO_PROFILE_ROOT at tmp dirs, never ~/.timbro."""
    return {
        "TIMBRO_HOME": str(Path(tmp) / "timbro_home"),
        "TIMBRO_PROFILE_ROOT": str(Path(tmp) / "profiles"),
    }


def _assert_stages_in_order(testcase: unittest.TestCase, stderr: str) -> None:
    """Every stage line present exactly once, in the loading -> encoding order."""
    at = 0
    for line in _STAGE_LINES:
        found = stderr.find(line, at)
        testcase.assertNotEqual(
            found, -1, f"missing stage {line!r} after offset {at} in: {stderr!r}"
        )
        at = found + len(line)
    for line in _STAGE_LINES:
        testcase.assertEqual(stderr.count(line), 1, stderr)


@skip_model_outputs_on_macos_ci
class AcceptStageProgressTests(unittest.TestCase):
    """A normal accept run shows the stages on stderr, verdict on stdout."""

    def test_text_mode_shows_stages_in_order_before_stdout_verdict(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, revised = _write_drafts(tmp, _REVISED_OK)
            proc = _run_cli(
                ["accept", str(original), str(revised)],
                env_overrides=_sandbox_env(tmp),
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        _assert_stages_in_order(self, proc.stderr)
        # stdout carries the verdict only: no stage line ever touches it.
        self.assertTrue(proc.stdout.startswith("accepted:"), proc.stdout)
        for line in _STAGE_LINES:
            self.assertNotIn(line, proc.stdout)

    def test_json_mode_stdout_is_exactly_the_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, revised = _write_drafts(tmp, _REVISED_OK)
            proc = _run_cli(
                ["accept", str(original), str(revised), "--json"],
                env_overrides=_sandbox_env(tmp),
            )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        _assert_stages_in_order(self, proc.stderr)
        # The whole stdout parses as the JSON payload; no stage text mixed in.
        payload = json.loads(proc.stdout)
        self.assertIs(payload["accepted"], True)
        self.assertNotIn("timbro:", proc.stdout)

    def test_rejected_run_keeps_exit_3_and_reports_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, revised = _write_drafts(tmp, _REVISED_BAD)
            proc = _run_cli(
                ["accept", str(original), str(revised)],
                env_overrides=_sandbox_env(tmp),
            )
        # Rejected rewrite: verdict gate failure, exit 3 (issue #142), stages
        # still reported before the stdout verdict line.
        self.assertEqual(proc.returncode, 3, proc.stderr)
        _assert_stages_in_order(self, proc.stderr)
        self.assertTrue(proc.stdout.startswith("rejected:"), proc.stdout)
        for line in _STAGE_LINES:
            self.assertNotIn(line, proc.stdout)


class UserErrorPrintsNoStagesTests(unittest.TestCase):
    """User errors that fire before model loading print no stage lines.

    The threshold check is cmd_accept's first statement (issue #158), so a bad
    threshold exits before anything prints. Later user errors (unknown
    profile, inside fit_model) can follow the loading-stage line: that is the
    stage having begun, not a leak into stdout -- only stdout cleanliness is
    pinned here.
    """

    def test_bad_threshold_prints_no_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, revised = _write_drafts(tmp, _REVISED_OK)
            proc = _run_cli(
                ["accept", str(original), str(revised), "--threshold", "2"],
                env_overrides=_sandbox_env(tmp),
            )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(
            proc.stderr,
            "timbro: error: --threshold must be between 0 and 1\n",
        )

    def test_unknown_profile_exits_1_with_error_on_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            original, revised = _write_drafts(tmp, _REVISED_OK)
            proc = _run_cli(
                ["accept", str(original), str(revised), "--profile", "does-not-exist"],
                env_overrides=_sandbox_env(tmp),
            )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertIn("Unknown profile 'does-not-exist'", proc.stderr)
        self.assertEqual(proc.stdout, "")


class DownloadNoticeTests(unittest.TestCase):
    """The shared text-embedding loader announces a first-run download (#225).

    Unit-level with SentenceTransformer mocked (no network): the cache-miss
    fallback path prints the spaCy-style notice naming the model; the cached
    path stays silent. Runs everywhere (no model outputs asserted).
    """

    def _load_uncached(self):
        # _model is lru_cache'd process-globally; __wrapped__ calls the loader
        # body without touching that cache, so these tests leave no state
        # behind for in-process consumers of the real model (suite-order
        # safety -- a cleared cache would force the next consumer to reload,
        # printing torch's 'Loading weights' bar to stderr).
        return text._model.__wrapped__()

    def test_first_run_download_prints_notice_naming_model(self):
        model = MagicMock(name="model")

        def fake_st(name, **kwargs):
            if kwargs.get("local_files_only"):
                raise OSError("model not in cache")
            return model

        err = io.StringIO()
        with patch(ST, side_effect=fake_st), contextlib.redirect_stderr(err):
            result = self._load_uncached()

        self.assertIs(result, model)
        self.assertEqual(
            err.getvalue(),
            f"timbro: downloading embedding model '{CONTENT_MODEL}' (first run only)...\n",
        )

    def test_cached_load_prints_no_notice(self):
        model = MagicMock(name="model")

        err = io.StringIO()
        with patch(ST, return_value=model), contextlib.redirect_stderr(err):
            result = self._load_uncached()

        self.assertIs(result, model)
        self.assertEqual(err.getvalue(), "")


class EncodingStagesUnitTests(unittest.TestCase):
    """evaluate_rewrite reports the encoding stages on stderr (issue #225).

    Unit-level with the model and the content guard mocked: stage order and
    stderr routing, no model outputs (runs everywhere).
    """

    def test_evaluate_rewrite_prints_encoding_stages_to_stderr(self):
        from timbro import rewrite

        model = MagicMock(name="model")
        model.score.return_value.distance = 1.0
        err = io.StringIO()
        with (
            patch.object(rewrite, "preserves_content", return_value=(True, 0.99)),
            contextlib.redirect_stderr(err),
        ):
            rewrite.evaluate_rewrite(model, "original text", "revised text")

        self.assertEqual(
            err.getvalue(),
            "timbro: encoding original...\ntimbro: encoding revised...\n",
        )
        # verdict logic untouched by the stage reporting
        self.assertEqual(model.score.call_count, 2)


if __name__ == "__main__":
    unittest.main()
