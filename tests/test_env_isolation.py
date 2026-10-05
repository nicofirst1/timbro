"""The autouse fixture makes every test hermetic to timbro's env (issue #202).

`tests/conftest.py::_isolated_timbro_home` used to sandbox only ``TIMBRO_HOME``,
so anything a developer exported in their shell leaked into the suite:
``TIMBRO_PROFILE_ROOT`` (which beats ``$TIMBRO_HOME/profiles``) sent test
writes into the developer's real profile root, ``TIMBRO_EXEMPLARS`` /
``TIMBRO_CONTRAST`` silently swapped the scored corpus, and ``TIMBRO_DEBUG``
/ ``TIMBRO_NO_LOG`` changed behavior. The fixture must delete those five and
point ``XDG_DATA_HOME`` at a tmp dir too.

The inherited-value tests only fail when the variables are actually present
in the shell running pytest, which is the issue's own verification protocol:
export junk values, run the suite, expect green. Run this file as::

    TIMBRO_PROFILE_ROOT=/tmp/timbro-202-junk/root \
    TIMBRO_EXEMPLARS=/tmp/timbro-202-junk/exemplars \
    TIMBRO_CONTRAST=/tmp/timbro-202-junk/contrast \
    TIMBRO_NO_LOG=1 TIMBRO_DEBUG=1 uv run pytest tests/test_env_isolation.py
"""

from __future__ import annotations

import contextlib
import io
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from timbro.cli import main


def _run(argv: list[str]) -> tuple[str, str, int]:
    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            with patch("sys.argv", ["timbro", *argv]):
                main()
        except SystemExit as exc:
            code = exc.code or 0
    return stdout.getvalue(), stderr.getvalue(), code


class InheritedEnvDeletedTests(unittest.TestCase):
    """The fixture deletes every timbro env var the shell may have exported."""

    def test_profile_root_not_inherited(self):
        # TIMBRO_PROFILE_ROOT beats $TIMBRO_HOME/profiles (profiles.py), so an
        # inherited value sends test writes into the developer's real profiles.
        self.assertNotIn("TIMBRO_PROFILE_ROOT", os.environ)

    def test_corpus_vars_not_inherited(self):
        # Inherited corpus paths would silently swap the scored corpus.
        self.assertNotIn("TIMBRO_EXEMPLARS", os.environ)
        self.assertNotIn("TIMBRO_CONTRAST", os.environ)

    def test_flag_vars_not_inherited(self):
        # Inherited flags change behavior: debug traces, learn-log opt-out.
        self.assertNotIn("TIMBRO_DEBUG", os.environ)
        self.assertNotIn("TIMBRO_NO_LOG", os.environ)


class SandboxTmpDirsTests(unittest.TestCase):
    """TIMBRO_HOME stays sandboxed and XDG_DATA_HOME joins it in tmp."""

    def test_home_sandboxed_outside_real_home(self):
        home = Path(os.environ["TIMBRO_HOME"])
        self.assertEqual(home.name, "timbro_home")
        self.assertFalse(
            str(home).startswith(str(Path.home())),
            f"TIMBRO_HOME escaped into the real home: {home}",
        )

    def test_xdg_data_home_points_at_tmp(self):
        xdg = os.environ.get("XDG_DATA_HOME")
        self.assertTrue(xdg, "XDG_DATA_HOME must be set to a tmp dir, not deleted")
        self.assertFalse(
            str(Path(xdg)).startswith(str(Path.home())),
            f"XDG_DATA_HOME points into the real home: {xdg}",
        )


class CliWritesSandboxedTests(unittest.TestCase):
    """The CLI writes into the sandboxed home even under the issue's protocol."""

    def test_profiles_add_file_lands_in_sandboxed_home(self):
        # The issue's example: AddFileDestNameCliTests.test_plain_dest_name_still_exits_0
        # writes demo/exemplars/plain.md into whatever TIMBRO_PROFILE_ROOT points
        # at. Under the protocol (junk root exported in the shell) the write must
        # still land in $TIMBRO_HOME/profiles, never in the exported root.
        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "draft.md"
            src.write_text("draft text\n", encoding="utf-8")

            out, err, code = _run(
                ["profiles", "add-file", "demo", str(src),
                 "--to", "exemplars", "--dest-name", "plain.md"]
            )

            self.assertEqual(code, 0)
            # #166: add-file scaffolds on purpose and prints the created line.
            self.assertEqual(err, "created profile demo\n", f"unexpected stderr: {err!r}")
            home = Path(os.environ["TIMBRO_HOME"])
            written = home / "profiles" / "demo" / "exemplars" / "plain.md"
            self.assertTrue(
                written.exists(),
                f"expected the write under the sandboxed home {home}, stdout was: {out!r}",
            )


if __name__ == "__main__":
    unittest.main()
