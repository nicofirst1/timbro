"""Very large drafts get a clear size error instead of a silent endless run (#153).

`score` (file and stdin), `check` and `accept` (each side) reject drafts over
`MAX_DRAFT_WORDS` (50,000) words with one clean `timbro: error:` line and exit 1,
counting words with the same regex `_profile_evidence` uses. The guard fires right
after the empty-draft check and before any model or profile load. A draft of exactly
the limit is accepted. Three speedups ship with it: `feature_vector` extracts
features once per call (byte-identical output), the span encodes in `report.py`
are batched, and `novelty_curve` keeps a running sum instead of re-meaning the
whole prefix (agreement within 1e-12).

The guard tests run the CLI as a subprocess so the real exit path, stdout and
stderr are exercised (same approach as test_cli_empty_draft.py).
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

import numpy as np

from timbro.cli import MAX_DRAFT_WORDS
from timbro.flow import novelty_curve
from timbro.model import _WORD, VoiceModel, read_corpus
from timbro.model.direction import feature_matrix, features
from timbro.priors import DEFAULT_EXEMPLARS
from timbro.text import cosine

_OVER = MAX_DRAFT_WORDS + 1
_LIMIT_MSG = (
    f"timbro: error: draft is {_OVER:,} words; "
    f"timbro scores drafts up to {MAX_DRAFT_WORDS:,} words (split it into sections)\n"
)


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


def _oversized_text() -> str:
    return " ".join(["word"] * _OVER)


class DraftSizeGuardTests(unittest.TestCase):
    """50,001-word drafts exit 1 with the exact message; nothing reaches scoring."""

    def test_score_stdin_over_limit_rejected(self):
        proc = _run_cli(["score", "-"], stdin_text=_oversized_text())
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, _LIMIT_MSG)

    def test_score_stdin_over_limit_json_rejected(self):
        proc = _run_cli(["score", "-", "--json"], stdin_text=_oversized_text())
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, _LIMIT_MSG)

    def test_score_file_over_limit_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "big.md"
            draft.write_text(_oversized_text(), encoding="utf-8")
            proc = _run_cli(["score", str(draft)])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, _LIMIT_MSG)

    def test_check_file_over_limit_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "big.md"
            draft.write_text(_oversized_text(), encoding="utf-8")
            proc = _run_cli(["check", str(draft)])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, _LIMIT_MSG)

    def test_accept_over_limit_original_rejected_names_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "orig.md"
            original.write_text(_oversized_text(), encoding="utf-8")
            revised = Path(tmp) / "rev.md"
            revised.write_text("a short revised draft", encoding="utf-8")
            proc = _run_cli(["accept", str(original), str(revised)])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(
            proc.stderr,
            f"timbro: error: {original} is {_OVER:,} words; "
            f"timbro scores drafts up to {MAX_DRAFT_WORDS:,} words (split it into sections)\n",
        )

    def test_accept_over_limit_revised_rejected_names_revised(self):
        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "orig.md"
            original.write_text("a short original draft", encoding="utf-8")
            revised = Path(tmp) / "rev.md"
            revised.write_text(_oversized_text(), encoding="utf-8")
            proc = _run_cli(["accept", str(original), str(revised)])
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(
            proc.stderr,
            f"timbro: error: {revised} is {_OVER:,} words; "
            f"timbro scores drafts up to {MAX_DRAFT_WORDS:,} words (split it into sections)\n",
        )
        self.assertNotIn(str(original), proc.stderr)

    def test_guard_runs_before_profile_load(self):
        """With oversized stdin and an unknown profile, the size error wins (like
        the empty-draft check in #152): an edit that moves the size check after
        the profile/model block flips this to the unknown-profile error."""
        with tempfile.TemporaryDirectory() as tmp:
            env = {"TIMBRO_PROFILE_ROOT": str(Path(tmp) / "profiles")}
            proc = _run_cli(
                ["score", "-", "--profile", "nonexistent"], stdin_text=_oversized_text(), env_overrides=env
            )
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(proc.stderr, _LIMIT_MSG)
        self.assertNotIn("nonexistent", proc.stderr)


_REWRITE_RESULT = {
    "accepted": True,
    "distance_before": 10.0,
    "distance_after": 5.0,
    "improved": True,
    "similarity": 0.95,
    "content_ok": True,
}


class DraftAtLimitAcceptedTests(unittest.TestCase):
    """A draft of exactly MAX_DRAFT_WORDS words passes the guard.

    The heavy scoring behind the guard is mocked: the assertion is that the run
    gets past the size check and reaches (mocked) scoring, not that it scores.
    """

    def _run_score(self, draft: Path) -> tuple[str, str]:
        from timbro import cli

        stdout, stderr = io.StringIO(), io.StringIO()
        argv = ["timbro", "score", str(draft), "--json"]
        with (
            mock.patch.object(sys, "argv", argv),
            mock.patch.object(cli, "default_model", return_value=mock.Mock()),
            mock.patch.object(cli, "voice_report", return_value={"distance": 1.0}),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            cli.main()
        return stdout.getvalue(), stderr.getvalue()

    def test_score_file_at_limit_gets_past_the_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            draft = Path(tmp) / "at-limit.md"
            draft.write_text(" ".join(["word"] * MAX_DRAFT_WORDS), encoding="utf-8")
            stdout, stderr = self._run_score(draft)
        self.assertNotIn("timbro: error:", stderr, stderr)
        self.assertEqual(json.loads(stdout), {"distance": 1.0})

    def test_accept_both_sides_at_limit_get_past_the_guard(self):
        from timbro import cli

        with tempfile.TemporaryDirectory() as tmp:
            original = Path(tmp) / "orig.md"
            original.write_text(" ".join(["word"] * MAX_DRAFT_WORDS), encoding="utf-8")
            revised = Path(tmp) / "rev.md"
            revised.write_text(" ".join(["word"] * MAX_DRAFT_WORDS), encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            argv = ["timbro", "accept", str(original), str(revised)]
            with (
                mock.patch.object(sys, "argv", argv),
                mock.patch.object(cli, "default_model", return_value=mock.Mock()),
                mock.patch.object(cli, "evaluate_rewrite", return_value=dict(_REWRITE_RESULT)),
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                cli.main()
        self.assertNotIn("timbro: error:", stderr.getvalue(), stderr.getvalue())
        self.assertIn("accepted:", stdout.getvalue())

    def test_draft_count_matches_the_shared_word_regex(self):
        """Fixture sanity: the generated boundary drafts really measure as claimed."""
        self.assertEqual(len(_WORD.findall(_oversized_text())), _OVER)
        self.assertEqual(len(_WORD.findall(" ".join(["word"] * MAX_DRAFT_WORDS))), MAX_DRAFT_WORDS)


class FeatureVectorExtractionTests(unittest.TestCase):
    """`feature_vector` must extract features once per call (issue #153, change A)
    and keep byte-identical output on the packaged sample exemplars."""

    @classmethod
    def setUpClass(cls):
        cls.exemplars = read_corpus(DEFAULT_EXEMPLARS)
        # Real feature names from the real corpus (no embedding fit needed).
        _X, cls.names = feature_matrix(cls.exemplars)

    def _model(self) -> VoiceModel:
        return VoiceModel(
            self.names,
            np.zeros(len(self.names)),
            np.ones(len(self.names)),
            np.zeros((1, len(self.names))),
            np.ones(len(self.names)),
            np.zeros(1),
            np.ones(1),
            np.zeros((1, 1)),
            6,
            1,
            1,
            0,
            3000,
            20,
            "ok",
            None,
            1.0,
            0.5,
            None,
        )

    def test_output_matches_the_per_name_implementation_byte_for_byte(self):
        model = self._model()
        for text in self.exemplars:
            vec = model.feature_vector(text)
            expected = np.array([features(text)[k] for k in model.names])
            self.assertEqual(vec.dtype, expected.dtype)
            self.assertEqual(vec.shape, expected.shape)
            self.assertEqual(vec.tobytes(), expected.tobytes(), text[:40])

    def test_features_runs_once_per_feature_vector_call(self):
        import timbro.model as tm

        model = self._model()
        real_features = tm.features
        calls: list[str] = []

        def counting(text: str):
            calls.append(text)
            return real_features(text)

        with mock.patch.object(tm, "features", counting):
            model.feature_vector(self.exemplars[0])
        self.assertEqual(len(calls), 1)


class NoveltyCurveIncrementalTests(unittest.TestCase):
    """The incremental novelty curve must match the recomputed-from-scratch
    reference within 1e-12 on random embeddings (issue #153, change C)."""

    def _old_curve(self, emb: np.ndarray) -> np.ndarray:
        return np.array([1 - cosine(emb[i], emb[:i].mean(0)) for i in range(1, len(emb))])

    def test_matches_reference_on_random_embeddings(self):
        rng = np.random.default_rng(0)
        for n in (1, 2, 50):
            with self.subTest(n=n):
                emb = rng.standard_normal((n, 16))
                np.testing.assert_allclose(
                    novelty_curve(emb), self._old_curve(emb), rtol=0, atol=1e-12
                )


if __name__ == "__main__":
    unittest.main()
