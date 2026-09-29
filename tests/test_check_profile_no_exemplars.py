from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from timbro.model import VoiceModel
from timbro.rubrics import check_text


class CheckProfileNoExemplarsTests(unittest.TestCase):
    """#161: `check --profile` with a missing or empty corpus must name the problem
    (the exemplars path), not an internal function (`tell_baseline needs a ...`)."""

    def _patched_root(self, tmp: str):
        return patch.dict(os.environ, {"TIMBRO_PROFILE_ROOT": str(Path(tmp) / "profiles")})

    def test_missing_profile_raises_filenotfound_naming_exemplars_path(self):
        with TemporaryDirectory() as tmp, self._patched_root(tmp):
            (Path(tmp) / "profiles").mkdir()
            with self.assertRaises(FileNotFoundError) as ctx:
                check_text("x", ["slop"], profile="nope")
        self.assertIn("No .md/.txt exemplars found at", str(ctx.exception))
        self.assertIn(
            str((Path(tmp) / "profiles" / "nope" / "exemplars").resolve()), str(ctx.exception)
        )

    def test_empty_exemplars_dir_raises_the_same_error(self):
        # the profile exists but its exemplars folder is empty: same problem, same message
        with TemporaryDirectory() as tmp, self._patched_root(tmp):
            (Path(tmp) / "profiles" / "nope" / "exemplars").mkdir(parents=True)
            with self.assertRaises(FileNotFoundError) as ctx:
                check_text("x", ["slop"], profile="nope")
        self.assertIn("No .md/.txt exemplars found at", str(ctx.exception))

    def test_message_matches_voice_model_from_dir_wording(self):
        # the wording is VoiceModel.from_dir's; reuse it, don't invent a new one (#161)
        with TemporaryDirectory() as tmp, self._patched_root(tmp):
            (Path(tmp) / "profiles").mkdir()
            exemplars = Path(tmp) / "profiles" / "nope" / "exemplars"
            with self.assertRaises(FileNotFoundError) as ctx:
                check_text("x", ["slop"], profile="nope")
            with self.assertRaises(FileNotFoundError) as donor:
                VoiceModel.from_dir(exemplars)
        self.assertEqual(str(donor.exception), str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
