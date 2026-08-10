from __future__ import annotations

import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

from timbro import spacy_model

_COMPAT = {"en_core_web_sm": ["3.8.0"]}
_WHEEL_URL = (
    "https://github.com/explosion/spacy-models/releases/download/"
    "en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
)


class LoadSpacyColdStartTests(unittest.TestCase):
    def test_installs_with_uv_python_flag_and_returns_loaded_model(self):
        loaded = MagicMock(name="loaded_model")
        with (
            patch("spacy.load", side_effect=[OSError("missing"), loaded]) as mock_load,
            patch("spacy.cli.download.get_compatibility", return_value=_COMPAT),
            patch("shutil.which", return_value="/opt/homebrew/bin/uv"),
            patch("subprocess.run") as mock_run,
        ):
            result = spacy_model.load_spacy()

        self.assertIs(result, loaded)
        self.assertEqual(mock_load.call_count, 2)
        mock_run.assert_called_once()
        cmd = mock_run.call_args.args[0]
        self.assertEqual(
            cmd,
            [
                "/opt/homebrew/bin/uv",
                "pip",
                "install",
                "--python",
                sys.executable,
                _WHEEL_URL,
            ],
        )
        self.assertTrue(mock_run.call_args.kwargs.get("check"))

    def test_falls_back_to_pip_when_uv_unavailable(self):
        loaded = MagicMock(name="loaded_model")
        with (
            patch("spacy.load", side_effect=[OSError("missing"), loaded]),
            patch("spacy.cli.download.get_compatibility", return_value=_COMPAT),
            patch("shutil.which", return_value=None),
            patch("subprocess.run") as mock_run,
        ):
            spacy_model.load_spacy()

        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd, [sys.executable, "-m", "pip", "install", _WHEEL_URL])

    def test_install_failure_propagates_instead_of_silent_e050(self):
        with (
            patch("spacy.load", side_effect=OSError("missing")),
            patch("spacy.cli.download.get_compatibility", return_value=_COMPAT),
            patch("shutil.which", return_value="/opt/homebrew/bin/uv"),
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, ["uv"]),
            ),
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                spacy_model.load_spacy()


if __name__ == "__main__":
    unittest.main()
