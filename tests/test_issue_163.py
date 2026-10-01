"""Issue #163: the packaged sample voice must reach health "ok" (so a
sample-voice score shows a real direction), and `profiles diagnose` must
surface the same health and thin-corpus warning that `score` shows."""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from timbro.model import _profile_evidence, default_model, read_corpus
from timbro.priors import DEFAULT_EXEMPLARS
from timbro.profiles import diagnose_profile, init_profile

# A fixed off-voice (slop-flavored) draft, the same shape the README example scores.
DRAFT = (
    "In today's fast-paced digital landscape, it's not just about writing code. "
    "It's about architecting experiences that delight, scale, and inspire. Let's "
    "dive in and explore how you can leverage cutting-edge methodologies to "
    "transform your team's productivity.\n\n"
    "First and foremost, it's important to understand that synergy is the "
    "cornerstone of any high-performing organization. Moreover, the modern stack "
    "offers a rich tapestry of tools designed to streamline your processes. The "
    "future is bright, and the possibilities are truly endless."
)

THIN_TEXT = (
    "The team met on Tuesday to review the deployment plan for the new service. "
    "We agreed to ship the migration behind a feature flag and watch the error "
    "rates for one week before switching traffic over. The rollback path stays "
    "open until the old stack is turned off."
)


class SampleCorpusHealthTests(unittest.TestCase):
    """The shipped exemplars must clear the "ok" evidence band of
    _profile_evidence (>= 2500 words, >= 16 substantive paragraphs)."""

    def test_packaged_sample_exemplars_fit_to_health_ok(self):
        texts = read_corpus(DEFAULT_EXEMPLARS)
        total_words, total_paragraphs, health, warning = _profile_evidence(texts)
        self.assertGreaterEqual(total_words, 2500)
        self.assertGreaterEqual(total_paragraphs, 16)
        self.assertEqual(health, "ok")
        self.assertIsNone(warning)

    def test_default_model_scores_sample_with_non_empty_direction(self):
        with TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["TIMBRO_HOME"] = tmp
            env["TIMBRO_PROFILE_ROOT"] = str(Path(tmp) / "profiles")
            env.pop("TIMBRO_EXEMPLARS", None)
            env.pop("TIMBRO_CONTRAST", None)
            with patch.dict(os.environ, env, clear=True):
                model = default_model()  # no corpus env vars: the packaged sample
        self.assertEqual(model.health, "ok")
        result = model.score(DRAFT)
        self.assertTrue(result.direction, "sample-voice score must show a direction")


class DiagnoseHealthTests(unittest.TestCase):
    def test_thin_corpus_gets_insufficient_health_and_evidence_warning(self):
        with TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            prof = init_profile("thin", root=root)
            (prof.exemplars_dir / "one.md").write_text(THIN_TEXT, encoding="utf-8")
            result = diagnose_profile("thin", root=root)
        self.assertEqual(result["exemplars"], 1)
        self.assertEqual(result["health"], "insufficient")
        self.assertEqual(
            result["warning"],
            f"Insufficient profile evidence: {result['files'][0]['words']} words / "
            f"{result['files'][0]['paragraphs']} substantive paragraphs. "
            "Distance is noisy and direction is suppressed.",
        )

    def test_empty_profile_reports_insufficient_health(self):
        with TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            init_profile("empty", root=root)
            result = diagnose_profile("empty", root=root)
        self.assertEqual(result["health"], "insufficient")
        self.assertEqual(result["warning"], "No exemplar files found.")

    def test_sample_sized_corpus_reports_ok_health(self):
        with TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            prof = init_profile("sized", root=root)
            for f in Path(DEFAULT_EXEMPLARS).glob("*.md"):
                shutil.copy2(f, prof.exemplars_dir / f.name)
            result = diagnose_profile("sized", root=root)
        # The sample clears the evidence band. (The outlier detector may still
        # flag a stylistically distinct file; that is the existing heuristic,
        # not the evidence signal this test pins.)
        self.assertEqual(result["health"], "ok")

    def test_outlier_warning_keeps_priority_over_evidence_warning(self):
        para = (
            "The deploy pipeline runs the test suite before every release, and a "
            "failed run blocks the train until someone fixes the break. Reviews "
            "land within a day, and small patches ship the same week they are "
            "written. The team keeps the runbook next to the service so the "
            "on-call engineer can act without hunting through old tickets. New "
            "engineers pair with the on-call for their first month, and the "
            "handoff notes from each shift land in the same channel."
        )
        filler = f"{para}\n\n{para}"
        outlier_text = f"{para}\n\n{para}\n\n{para}"
        vecs = {filler: (1.0, 0.1), f"{para}\n\n{para}\n\n{para}": (-1.0, 0.0)}
        with TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            prof = init_profile("outl", root=root)
            for i in range(6):
                (prof.exemplars_dir / f"doc{i}.md").write_text(filler, encoding="utf-8")
            (prof.exemplars_dir / "doc6.md").write_text(outlier_text, encoding="utf-8")

            def fake_style_vec(text: str):
                return vecs[text]

            with patch("timbro.profiles._style_vec", side_effect=fake_style_vec):
                result = diagnose_profile("outl", root=root)
        # ~2000 words / 14 paragraphs: past the "insufficient" gate (an evidence
        # warning exists), but under "ok" -- yet the outlier must win the merge.
        self.assertEqual(result["health"], "weak")
        self.assertTrue(result["warning"].startswith("Outlier exemplars detected"))


class CliDiagnoseHealthTests(unittest.TestCase):
    def _run(self, argv: list[str]) -> str:
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            patch("sys.argv", ["timbro", *argv]),
        ):
            from timbro.cli import main

            main()
        return stdout.getvalue()

    def test_diagnose_prints_health_after_exemplars(self):
        with TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            prof = init_profile("thin", root=root)
            (prof.exemplars_dir / "one.md").write_text(THIN_TEXT, encoding="utf-8")
            env = os.environ.copy()
            env["TIMBRO_PROFILE_ROOT"] = str(root)
            env["TIMBRO_HOME"] = td
            with patch.dict(os.environ, env, clear=True):
                out = self._run(["profiles", "diagnose", "thin"])
        lines = out.splitlines()
        idx = next(i for i, ln in enumerate(lines) if ln.startswith("exemplars:"))
        self.assertEqual(lines[idx + 1], "health: insufficient")


if __name__ == "__main__":
    unittest.main()
