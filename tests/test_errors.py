"""One UserError path for every expected CLI error (issue #191).

Every converted raise site raises a class that is BOTH `timbro.errors.UserError`
AND the builtin it replaces, so existing `except` clauses and API callers keep
working. `UserError` itself derives from `Exception`, not from any builtin.
The six known bug sites must stay plain builtins, so bugs keep tracing back.
Unit-level: raise the errors directly, no CLI subprocess.

Sandbox: TIMBRO_HOME / TIMBRO_PROFILE_ROOT / XDG_DATA_HOME point at tmp dirs;
the real ~/.timbro is never touched.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from timbro.errors import (
    UserError,
    UserFileExistsError,
    UserFileNotFoundError,
    UserRuntimeError,
    UserValueError,
)

_TEXT = "I fixed the parser today. It dropped the last row, so I added a guard and a test."


class _SandboxCase(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name)
        env = {
            "TIMBRO_HOME": str(self.tmp / "home"),
            "TIMBRO_PROFILE_ROOT": str(self.tmp / "profiles"),
            "XDG_DATA_HOME": str(self.tmp / "xdg-data"),
        }
        patcher = patch.dict(os.environ, env, clear=False)
        patcher.start()
        self.addCleanup(patcher.stop)


class UserErrorClassShapeTests(unittest.TestCase):
    def test_user_error_derives_from_exception_not_from_a_builtin(self):
        self.assertTrue(issubclass(UserError, Exception))
        for builtin in (ValueError, FileNotFoundError, FileExistsError, RuntimeError, OSError):
            self.assertFalse(issubclass(UserError, builtin), builtin.__name__)

    def test_compat_classes_are_both_user_error_and_their_builtin(self):
        pairs = [
            (UserValueError, ValueError),
            (UserFileNotFoundError, FileNotFoundError),
            (UserFileExistsError, FileExistsError),
            (UserRuntimeError, RuntimeError),
        ]
        for cls, builtin in pairs:
            self.assertTrue(issubclass(cls, UserError), cls.__name__)
            self.assertTrue(issubclass(cls, builtin), cls.__name__)


class ConvertedRaiseSitesTests(_SandboxCase):
    """Each converted site raises a class that is both UserError and the old builtin."""

    def test_normalize_profile_name_invalid_name(self):
        from timbro.profiles import normalize_profile_name

        with self.assertRaises(ValueError) as ctx:
            normalize_profile_name("Bad Name!")
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserValueError)

    def test_add_file_dest_name_not_plain(self):
        from timbro.profiles import add_file

        with self.assertRaises(ValueError) as ctx:
            add_file("demo", "src.md", bucket="exemplars", dest_name="../escape.md")
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserValueError)

    def test_add_file_bad_extension(self):
        from timbro.profiles import add_file

        src = self.tmp / "src.rst"
        src.write_text(_TEXT, encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            add_file("demo", str(src), bucket="exemplars", create=True)
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserValueError)

    def test_add_file_missing_source(self):
        from timbro.profiles import add_file

        with self.assertRaises(FileNotFoundError) as ctx:
            add_file("demo", "no-such-file.md", bucket="exemplars", create=True)
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserFileNotFoundError)

    def test_add_file_destination_exists(self):
        from timbro.profiles import add_file

        src = self.tmp / "note.md"
        src.write_text(_TEXT, encoding="utf-8")
        add_file("demo", str(src), bucket="exemplars", create=True)
        with self.assertRaises(FileExistsError) as ctx:
            add_file("demo", str(src), bucket="exemplars")
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserFileExistsError)

    def test_read_pair_text_missing_file(self):
        from timbro.profiles import _read_pair_text

        with self.assertRaises(FileNotFoundError) as ctx:
            _read_pair_text("no-such-pair.md", "draft")
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserFileNotFoundError)

    def test_read_pair_text_empty_file(self):
        from timbro.profiles import _read_pair_text

        empty = self.tmp / "empty.md"
        empty.write_text("", encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            _read_pair_text(empty, "draft")
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserValueError)

    def test_check_pair_slots_free_collision(self):
        from timbro.profiles import _check_pair_slots_free, init_profile

        profile = init_profile("demo")
        (profile.exemplars_dir / "taken.md").write_text(_TEXT, encoding="utf-8")
        with self.assertRaises(FileExistsError) as ctx:
            _check_pair_slots_free(profile, "taken")
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserFileExistsError)

    def test_learn_guard_needs_exemplars(self):
        from timbro.profiles import learn

        draft = self.tmp / "d.md"
        final = self.tmp / "f.md"
        draft.write_text(_TEXT, encoding="utf-8")
        final.write_text(_TEXT, encoding="utf-8")
        with self.assertRaises(ValueError) as ctx:
            learn("demo", draft, final)
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserValueError)

    def test_load_settings_malformed_json(self):
        from timbro.settings import load_settings

        with _settings_home("{nope") as path, self.assertRaises(ValueError) as ctx:
            load_settings()
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserValueError)
        self.assertIn(str(path), str(ctx.exception))

    def test_load_settings_non_object(self):
        from timbro.settings import load_settings

        with _settings_home("[]"), self.assertRaises(ValueError) as ctx:
            load_settings()
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserValueError)

    def test_load_settings_unknown_key(self):
        from timbro.settings import load_settings

        with _settings_home('{"bogus": 1}'), self.assertRaises(ValueError) as ctx:
            load_settings()
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserValueError)

    def test_load_settings_wrong_value_type(self):
        from timbro.settings import load_settings

        with _settings_home('{"no_log": "yes"}'), self.assertRaises(ValueError) as ctx:
            load_settings()
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserValueError)

    def test_check_text_profile_without_slop(self):
        from timbro.rubrics import check_text

        with self.assertRaises(ValueError) as ctx:
            check_text("x", ["density"], profile="demo")
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserValueError)

    def test_no_exemplars_error_is_user_file_not_found(self):
        from timbro.model import no_exemplars_error

        exc = no_exemplars_error("/tmp/no-such-corpus")
        self.assertIsInstance(exc, UserError)
        self.assertIsInstance(exc, UserFileNotFoundError)
        self.assertIsInstance(exc, FileNotFoundError)

    def test_detex_not_installed(self):
        from timbro.cleanup.latex import detex_text

        with (
            patch("timbro.cleanup.latex.shutil.which", return_value=None),
            self.assertRaises(RuntimeError) as ctx,
        ):
            detex_text("plain text")
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserRuntimeError)

    def test_detex_timeout(self):
        from timbro.cleanup.latex import detex_text

        with (
            patch("timbro.cleanup.latex.shutil.which", return_value="/usr/bin/detex"),
            patch(
                "timbro.cleanup.latex.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="detex", timeout=60),
            ),
            self.assertRaises(RuntimeError) as ctx,
        ):
            detex_text(r"\section{Intro}" "\nHello.")
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserRuntimeError)

    def test_detex_nonzero_exit(self):
        from timbro.cleanup.latex import detex_text

        with (
            patch("timbro.cleanup.latex.shutil.which", return_value="/usr/bin/detex"),
            patch(
                "timbro.cleanup.latex.subprocess.run",
                return_value=SimpleNamespace(returncode=1, stderr="detex exploded", stdout=""),
            ),
            self.assertRaises(RuntimeError) as ctx,
        ):
            detex_text(r"\section{Intro}" "\nHello.")
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserRuntimeError)
        self.assertEqual(str(ctx.exception), "detex exploded")

    def test_sync_git_missing(self):
        from timbro.profiles import sync_profiles

        with (
            patch("timbro.profiles.shutil.which", return_value=None),
            self.assertRaises(RuntimeError) as ctx,
        ):
            sync_profiles()
        self.assertIsInstance(ctx.exception, UserError)
        self.assertIsInstance(ctx.exception, UserRuntimeError)
        self.assertEqual(str(ctx.exception), "git not found on PATH; profile sync needs git")

    def test_spacy_install_failure_is_user_error_with_exact_message(self):
        from timbro import spacy_model

        with (
            patch.object(
                spacy_model, "_model_wheel_url", return_value="https://example.invalid/model.whl"
            ),
            patch.object(
                spacy_model.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(1, ["uv", "pip", "install"]),
            ),
            self.assertRaises(UserError) as ctx,
        ):
            spacy_model._install_model()
        self.assertIsInstance(ctx.exception, UserRuntimeError)
        self.assertIsInstance(ctx.exception, RuntimeError)
        self.assertEqual(
            str(ctx.exception),
            "could not install the spaCy model (no network?); re-run when online",
        )


class BugSitesStayLoudTests(unittest.TestCase):
    """The six bug sites stay plain builtins: not UserError, so they traceback."""

    def test_get_rubric_unknown_name_is_not_user_error(self):
        from timbro.rubrics.registry import get_rubric

        with self.assertRaises(KeyError) as ctx:
            get_rubric("bogus-rubric")
        self.assertNotIsInstance(ctx.exception, UserError)

    def test_axis_report_unknown_metric_is_not_user_error(self):
        from timbro.model import VoiceModel

        model = VoiceModel(
            ["pos_NOUN"], np_array([1.0]), np_array([1.0]), np_array([[0.0]]), np_array([1.0]),
            np_array([0.0]), np_array([1.0]), np_array([[0.0]]), 6, 1, 1, 0, 3000, 4, "ok", None,
            1.0, 0.5, None,
        )
        with self.assertRaises(KeyError) as ctx:
            model.axis_report("no-such-axis", "text")
        self.assertNotIsInstance(ctx.exception, UserError)

    def test_tell_baseline_empty_corpus_is_not_user_error(self):
        from timbro.axes.tells import tell_baseline

        with self.assertRaises(ValueError) as ctx:
            tell_baseline([])
        self.assertNotIsInstance(ctx.exception, UserError)

    def test_flow_report_short_input_is_not_user_error(self):
        from timbro.flow import flow_report

        with self.assertRaises(ValueError) as ctx:
            flow_report("One short paragraph only.")
        self.assertNotIsInstance(ctx.exception, UserError)

    def test_add_text_bucket_kwarg_is_not_user_error(self):
        from timbro.profiles import add_text

        with self.assertRaises(ValueError) as ctx:
            add_text("demo", "text", bucket="bogus", title="t")
        self.assertNotIsInstance(ctx.exception, UserError)

    def test_add_file_bucket_kwarg_is_not_user_error(self):
        from timbro.profiles import add_file

        with self.assertRaises(ValueError) as ctx:
            add_file("demo", "src.md", bucket="bogus")
        self.assertNotIsInstance(ctx.exception, UserError)


# ----------------------------------------------------------------- helpers


def np_array(values):
    import numpy as np

    return np.array(values)


@contextmanager
def _settings_home(text: str):
    """TIMBRO_HOME pointed at a tmp dir whose settings.json holds `text`."""
    with tempfile.TemporaryDirectory() as td:
        home = Path(td) / "home"
        home.mkdir(parents=True)
        path = home / "settings.json"
        path.write_text(text, encoding="utf-8")
        with patch.dict(os.environ, {"TIMBRO_HOME": str(home)}, clear=False):
            os.environ.pop("TIMBRO_DEBUG", None)
            os.environ.pop("TIMBRO_NO_LOG", None)
            yield path


if __name__ == "__main__":
    unittest.main()
