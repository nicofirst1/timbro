from __future__ import annotations

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from timbro.profiles import add_text
from timbro.rubrics import check_text


class CheckProfileNoExemplarsTests(unittest.TestCase):
    """#161: `check --profile` with an empty corpus must name the problem (the
    exemplars path), not an internal function (`tell_baseline needs a ...`).
    #166 round 2: a profile dir that does not exist is instead the unknown-
    profile error, one wording shared by every named-profile reader."""

    def _patched_root(self, tmp: str):
        return patch.dict(os.environ, {"TIMBRO_PROFILE_ROOT": str(Path(tmp) / "profiles")})

    def test_missing_profile_raises_the_unknown_profile_error(self):
        # #166 round 2: a profile dir that does not exist is an unknown profile
        # (the spec's item-1 error, shared by every named-profile reader), not
        # an empty corpus; the #161 wording stays for the empty-exemplars cases
        # below.
        with TemporaryDirectory() as tmp, self._patched_root(tmp):
            (Path(tmp) / "profiles").mkdir()
            with self.assertRaises(FileNotFoundError) as ctx:
                check_text("x", ["slop"], profile="nope")
        profile_dir = (Path(tmp) / "profiles" / "nope").resolve()
        expected = (
            f"Unknown profile 'nope': {profile_dir} does not exist. "
            "Create it with 'timbro profiles init nope' or pass create=True."
        )
        self.assertEqual(str(ctx.exception), expected)

    def test_empty_exemplars_dir_raises_the_same_error(self):
        # the profile exists but its exemplars folder is empty: same problem, same message
        with TemporaryDirectory() as tmp, self._patched_root(tmp):
            (Path(tmp) / "profiles" / "nope" / "exemplars").mkdir(parents=True)
            with self.assertRaises(FileNotFoundError) as ctx:
                check_text("x", ["slop"], profile="nope")
        self.assertIn("No .md/.txt exemplars found at", str(ctx.exception))

    def test_error_message_points_at_managed_profiles(self):
        # round 3: one message for everyone, pointing at managed profiles; the env
        # var is no longer suggested (#161 addendum, direction #96). #166 moved the
        # missing-directory case to read_corpus's own message, so the #161 wording
        # is pinned here on the empty-corpus case it still covers.
        with TemporaryDirectory() as tmp, self._patched_root(tmp):
            (Path(tmp) / "profiles" / "nope" / "exemplars").mkdir(parents=True)
            with self.assertRaises(FileNotFoundError) as ctx:
                check_text("x", ["slop"], profile="nope")
        exemplars = (Path(tmp) / "profiles" / "nope" / "exemplars").resolve()
        expected = (
            f"No .md/.txt exemplars found at {exemplars}. "
            "Add posts that define your voice with: timbro profiles add-file <profile> <file> --to exemplars"
        )
        self.assertEqual(str(ctx.exception), expected)

    def test_unknown_profile_wording_matches_add_text(self):
        # #166 round 2: the unknown-profile wording is the profiles layer's (the
        # spec's item-1 message); check_text reuses it instead of inventing its
        # own. The #161 from_dir wording stays pinned above on the empty-corpus
        # cases it still covers.
        with TemporaryDirectory() as tmp, self._patched_root(tmp):
            (Path(tmp) / "profiles").mkdir()
            with self.assertRaises(FileNotFoundError) as ctx:
                check_text("x", ["slop"], profile="nope")
            with self.assertRaises(FileNotFoundError) as donor:
                add_text("nope", "text", bucket="exemplars", title="note")
        self.assertEqual(str(donor.exception), str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
