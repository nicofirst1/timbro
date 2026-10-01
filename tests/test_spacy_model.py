from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from timbro import spacy_model
from timbro.errors import UserError

_COMPAT = {"en_core_web_sm": ["3.8.0"]}
_WHEEL_URL = (
    "https://github.com/explosion/spacy-models/releases/download/"
    "en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"
)

# Child harness for the closed-stdout repro (issue #136): the child points its
# own fd 1 at a pipe, closes the pipe's read end (as a `| head -2` reader that
# exits early would), then calls _install_model with subprocess.run mocked to
# emit pip-sized output on whatever stream it was handed. If the install
# inherits stdout, the write hits the dead pipe and the child dies with
# BrokenPipeError; if it targets sys.stderr, the child prints CHILD-OK.
_CHILD_CLOSED_STDOUT_SCRIPT = """\
import os
import sys
from unittest import mock


def fake_run(cmd, check=False, **kwargs):
    stream = kwargs.get("stdout")
    if stream is None:
        stream = sys.stdout
    stream.write("x" * (1 << 20))
    stream.flush()
    return mock.Mock(returncode=0)


read_end, write_end = os.pipe()
os.dup2(write_end, 1)
os.close(read_end)
os.close(write_end)

import timbro.spacy_model as spacy_model

with mock.patch("subprocess.run", fake_run):
    spacy_model._install_model()

devnull = os.open(os.devnull, os.O_WRONLY)
os.dup2(devnull, 1)
sys.stderr.write("CHILD-OK\\n")
"""


class LoadSpacyColdStartTests(unittest.TestCase):
    def setUp(self):
        # load_spacy takes its install lock under tempfile.gettempdir(); keep
        # that (and everything else) out of the real tmp dir.
        self._tmp = tempfile.mkdtemp(prefix="timbro-spacy-model-")
        self.addCleanup(shutil.rmtree, self._tmp, True)

    def test_installs_with_uv_python_flag_and_returns_loaded_model(self):
        loaded = MagicMock(name="loaded_model")
        with (
            patch("tempfile.gettempdir", return_value=self._tmp),
            patch(
                "spacy.load",
                side_effect=[OSError("missing"), OSError("still missing"), loaded],
            ) as mock_load,
            patch("spacy.cli.download.get_compatibility", return_value=_COMPAT),
            patch("shutil.which", return_value="/opt/homebrew/bin/uv"),
            patch("subprocess.run") as mock_run,
        ):
            result = spacy_model.load_spacy()

        self.assertIs(result, loaded)
        self.assertEqual(mock_load.call_count, 3)
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
            patch("tempfile.gettempdir", return_value=self._tmp),
            patch(
                "spacy.load",
                side_effect=[OSError("missing"), OSError("still missing"), loaded],
            ),
            patch("spacy.cli.download.get_compatibility", return_value=_COMPAT),
            patch("shutil.which", return_value=None),
            patch("subprocess.run") as mock_run,
        ):
            spacy_model.load_spacy()

        cmd = mock_run.call_args.args[0]
        self.assertEqual(cmd, [sys.executable, "-m", "pip", "install", _WHEEL_URL])

    def test_install_failure_propagates_instead_of_silent_e050(self):
        # #191: the failed install is re-typed from CalledProcessError to
        # UserRuntimeError (a UserError), so the CLI prints one clean line
        # instead of a traceback; it still propagates, it is not silent.
        with (
            patch("tempfile.gettempdir", return_value=self._tmp),
            patch("spacy.load", side_effect=OSError("missing")),
            patch("spacy.cli.download.get_compatibility", return_value=_COMPAT),
            patch("shutil.which", return_value="/opt/homebrew/bin/uv"),
            patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, ["uv"]),
            ),
        ):
            with self.assertRaises(UserError) as ctx:
                spacy_model.load_spacy()
        self.assertIsInstance(ctx.exception, RuntimeError)
        self.assertIn("no network", str(ctx.exception))


class InstallStdoutRedirectTests(unittest.TestCase):
    """Issue #136: pip's output must never touch the user's stdout."""

    def test_install_targets_stderr_and_keeps_check(self):
        with (
            patch("spacy.cli.download.get_compatibility", return_value=_COMPAT),
            patch("shutil.which", return_value="/opt/homebrew/bin/uv"),
            patch("subprocess.run") as mock_run,
        ):
            spacy_model._install_model()

        mock_run.assert_called_once()
        self.assertIs(mock_run.call_args.kwargs.get("stdout"), sys.stderr)
        self.assertTrue(mock_run.call_args.kwargs.get("check"))

    def test_install_survives_closed_stdout_pipe(self):
        proc = subprocess.run(
            [sys.executable, "-c", _CHILD_CLOSED_STDOUT_SCRIPT],
            capture_output=True,
            text=True,
            timeout=60,
        )

        self.assertEqual(
            proc.returncode, 0, f"child failed:\n{proc.stderr}"
        )
        self.assertIn("CHILD-OK", proc.stderr)


if __name__ == "__main__":
    unittest.main()
