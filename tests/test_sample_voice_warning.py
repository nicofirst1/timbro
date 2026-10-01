from __future__ import annotations

import os
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from timbro.model import default_model


class SampleVoiceWarningTests(unittest.TestCase):
    """Round-3 addendum to #161: the packaged-sample warning points at managed
    profiles, not at the TIMBRO_EXEMPLARS/TIMBRO_CONTRAST env vars (direction #96)."""

    def test_sample_fallback_warning_names_the_profile_commands(self):
        with TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.pop("TIMBRO_EXEMPLARS", None)
            env.pop("TIMBRO_CONTRAST", None)
            env["TIMBRO_HOME"] = tmp
            env["TIMBRO_PROFILE_ROOT"] = str(os.path.join(tmp, "profiles"))
            with patch.dict(os.environ, env):
                model = default_model()  # no corpus env vars: sample_fallback is on
            model.warning = None  # isolate the sample fallback from the evidence warning
            self.assertTrue(model.sample_fallback)
            self.assertEqual(
                model.profile_report()["warning"],
                "Using packaged sample voice, not a user profile. "
                "Use --profile <name> (create one with: timbro profiles init <name>).",
            )


if __name__ == "__main__":
    unittest.main()
