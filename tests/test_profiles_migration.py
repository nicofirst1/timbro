"""Migration warning for the 0.8 -> 0.9 profile-root move (issue #138).

0.8.0 resolved profiles under `$XDG_DATA_HOME/timbro/profiles`; 0.9.0 reads
only `TIMBRO_PROFILE_ROOT` or `$TIMBRO_HOME/profiles`. After upgrading, an
existing user's profiles silently vanish from `profiles list` and `--profile`.
The fix prints one stderr line naming both paths and the `mv` command; the
legacy path is never read automatically.
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import timbro.cli as cli
from timbro.cli import cmd_accept, cmd_profiles_list, cmd_score, main
from timbro.profiles import _legacy_xdg_root, init_profile, legacy_profile_warning


def _seed_profile(root: Path, name: str) -> None:
    (root / name / "exemplars").mkdir(parents=True, exist_ok=True)
    (root / name / "contrast").mkdir(parents=True, exist_ok=True)
    (root / name / "exemplars" / "doc.md").write_text("sample text", encoding="utf-8")


def _seed_legacy(xdg: Path) -> None:
    """The issue's setup: two profiles left behind at 0.8.0's XDG default."""
    _seed_profile(xdg / "timbro" / "profiles", "old-a")
    _seed_profile(xdg / "timbro" / "profiles", "old-b")


@contextlib.contextmanager
def _default_resolution(home: Path, xdg: Path):
    """Pin TIMBRO_HOME and XDG_DATA_HOME; drop TIMBRO_PROFILE_ROOT (default resolution)."""
    with patch.dict(os.environ, {"TIMBRO_HOME": str(home), "XDG_DATA_HOME": str(xdg)}, clear=False):
        os.environ.pop("TIMBRO_PROFILE_ROOT", None)
        yield


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


class LegacyXdgRootTests(unittest.TestCase):
    def test_xdg_data_home_env_wins(self):
        with TemporaryDirectory() as td:
            with patch.dict(os.environ, {"XDG_DATA_HOME": td}, clear=False):
                self.assertEqual(_legacy_xdg_root(), (Path(td) / "timbro" / "profiles").resolve())

    def test_defaults_to_local_share_without_env(self):
        with TemporaryDirectory() as home:
            env = dict(os.environ)
            env.pop("XDG_DATA_HOME", None)
            with patch.dict(os.environ, env, clear=True):
                with patch.object(Path, "home", return_value=Path(home)):
                    result = _legacy_xdg_root()
            expected = (Path(home) / ".local" / "share" / "timbro" / "profiles").resolve()
            self.assertEqual(result, expected)


class LegacyProfileWarningTests(unittest.TestCase):
    def test_warns_when_default_root_empty_and_legacy_has_profiles(self):
        with TemporaryDirectory() as td:
            td = Path(td)
            home, xdg = td / "home", td / "xdg"
            _seed_legacy(xdg)
            with _default_resolution(home, xdg):
                warning = legacy_profile_warning()
        new_root = str((home / "profiles").resolve())
        legacy_root = str((xdg / "timbro" / "profiles").resolve())
        self.assertIsNotNone(warning)
        self.assertNotIn("\n", warning)  # exactly one line
        self.assertIn("mv", warning)
        self.assertIn(new_root, warning)
        self.assertIn(legacy_root, warning)

    def test_silent_when_default_root_has_profiles(self):
        with TemporaryDirectory() as td:
            td = Path(td)
            home, xdg = td / "home", td / "xdg"
            _seed_legacy(xdg)
            init_profile("fresh", root=home / "profiles")
            with _default_resolution(home, xdg):
                self.assertIsNone(legacy_profile_warning())

    def test_silent_when_profile_root_env_is_set(self):
        with TemporaryDirectory() as td:
            td = Path(td)
            xdg = td / "xdg"
            _seed_legacy(xdg)
            env = {
                "TIMBRO_HOME": str(td / "home"),
                "TIMBRO_PROFILE_ROOT": str(td / "elsewhere"),
                "XDG_DATA_HOME": str(xdg),
            }
            with patch.dict(os.environ, env, clear=False):
                self.assertIsNone(legacy_profile_warning())

    def test_silent_when_legacy_dir_is_missing(self):
        with TemporaryDirectory() as td:
            td = Path(td)
            home, xdg = td / "home", td / "xdg"  # xdg never created: fresh install
            with _default_resolution(home, xdg):
                self.assertIsNone(legacy_profile_warning())

    def test_silent_when_legacy_has_no_profile_dirs(self):
        with TemporaryDirectory() as td:
            td = Path(td)
            home, xdg = td / "home", td / "xdg"
            (xdg / "timbro" / "profiles" / ".stale").mkdir(parents=True)  # dot-dirs don't count
            with _default_resolution(home, xdg):
                self.assertIsNone(legacy_profile_warning())

    def test_warning_quotes_paths_with_spaces(self):
        with TemporaryDirectory() as td:
            td = Path(td)
            home, xdg = td / "timbro home", td / "xdg data"  # spaces: command must survive copy-paste
            _seed_legacy(xdg)
            with _default_resolution(home, xdg):
                warning = legacy_profile_warning()
        new_root = str((home / "profiles").resolve())
        legacy_root = str((xdg / "timbro" / "profiles").resolve())
        self.assertIsNotNone(warning)
        self.assertIn(f"mkdir -p '{new_root}'", warning)
        self.assertIn(f"mv '{legacy_root}'/* '{new_root}'/", warning)

    def test_silent_when_explicit_root_arg_is_given(self):
        with TemporaryDirectory() as td:
            td = Path(td)
            xdg = td / "xdg"
            _seed_legacy(xdg)
            with _default_resolution(td / "home", xdg):
                self.assertIsNone(legacy_profile_warning(root=td / "explicit"))


class ProfilesListMigrationTests(unittest.TestCase):
    def test_list_json_still_empty_but_warns_once(self):
        """The issue's regression: OLD list --json gives 2 entries, NEW gives [] — and says why."""
        with TemporaryDirectory() as td:
            td = Path(td)
            home, xdg = td / "home", td / "xdg"
            _seed_legacy(xdg)
            with _default_resolution(home, xdg):
                out, err, code = _run(["profiles", "list", "--json"])
        new_root = str((home / "profiles").resolve())
        legacy_root = str((xdg / "timbro" / "profiles").resolve())
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [])  # never reads the legacy path
        lines = err.splitlines()
        self.assertEqual(len(lines), 1)
        self.assertIn("mv", lines[0])
        self.assertIn(new_root, lines[0])
        self.assertIn(legacy_root, lines[0])

    def test_list_human_output_warns_to_stderr_not_stdout(self):
        with TemporaryDirectory() as td:
            td = Path(td)
            home, xdg = td / "home", td / "xdg"
            _seed_legacy(xdg)
            with _default_resolution(home, xdg):
                out, err, code = _run(["profiles", "list"])
        self.assertEqual(code, 0)
        self.assertEqual(out, "")
        self.assertIn("mv", err)

    def test_no_warning_when_new_root_has_profiles(self):
        with TemporaryDirectory() as td:
            td = Path(td)
            home, xdg = td / "home", td / "xdg"
            _seed_legacy(xdg)
            init_profile("fresh", root=home / "profiles")
            with _default_resolution(home, xdg):
                out, err, code = _run(["profiles", "list"])
        self.assertEqual(code, 0)
        self.assertIn("fresh", out)
        self.assertEqual(err, "")


class ScoreProfileMigrationTests(unittest.TestCase):
    def test_score_profile_warns_before_missing_profile_error(self):
        with TemporaryDirectory() as td:
            td = Path(td)
            home, xdg = td / "home", td / "xdg"
            _seed_legacy(xdg)
            draft = td / "draft.md"
            draft.write_text("A short draft.", encoding="utf-8")
            with _default_resolution(home, xdg):
                out, err = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    with self.assertRaises(FileNotFoundError):
                        cmd_score(
                            argparse.Namespace(
                                file=str(draft), profile="old-a", json=True, quiet=False
                            )
                        )
        self.assertEqual(out.getvalue(), "")
        self.assertIn("mv", err.getvalue())
        self.assertIn(str((xdg / "timbro" / "profiles").resolve()), err.getvalue())


_DRAFT = "The committee reviewed the budget and asked for a revised proposal today."


class WarningCoversEveryProfileCommandTests(unittest.TestCase):
    """Every command that resolves a profile by name warns in the firing state (#138)."""

    def _firing(self):
        """TemporaryDirectory + seeded legacy XDG dir + default-resolution env pin."""
        td = TemporaryDirectory()
        tdp = Path(td.name)
        home, xdg = tdp / "home", tdp / "xdg"
        _seed_legacy(xdg)
        self.addCleanup(td.cleanup)
        return home, xdg

    def test_check_profile_warns(self):
        home, xdg = self._firing()
        draft = Path(xdg).parent / "draft.md"
        draft.write_text(_DRAFT, encoding="utf-8")
        with _default_resolution(home, xdg):
            out, err, code = _run(["check", str(draft), "--profile", "old-a"])
        self.assertNotEqual(code, 0)  # empty new-root corpus: pre-existing error path
        self.assertIn("mv", err)

    def test_check_non_slop_profile_does_not_resolve_so_no_warning(self):
        home, xdg = self._firing()
        draft = Path(xdg).parent / "draft.md"
        draft.write_text(_DRAFT, encoding="utf-8")
        with _default_resolution(home, xdg):
            out, err, code = _run(["check", str(draft), "--profile", "old-a", "--rubric", "density"])
        self.assertNotEqual(code, 0)  # --profile only affects the slop rubric
        self.assertNotIn("mv", err)

    def test_accept_profile_warns_before_missing_profile_error(self):
        home, xdg = self._firing()
        tdp = Path(xdg).parent
        orig, revised = tdp / "orig.md", tdp / "revised.md"
        orig.write_text(_DRAFT, encoding="utf-8")
        revised.write_text(_DRAFT, encoding="utf-8")
        with _default_resolution(home, xdg):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                with self.assertRaises(FileNotFoundError):
                    cmd_accept(
                        argparse.Namespace(
                            original=str(orig), revised=str(revised), profile="old-a", threshold=0.85, json=True
                        )
                    )
        self.assertEqual(out.getvalue(), "")
        self.assertIn("mv", err.getvalue())

    def test_profiles_env_warns(self):
        home, xdg = self._firing()
        with _default_resolution(home, xdg):
            out, err, code = _run(["profiles", "env", "old-a"])
        self.assertEqual(code, 0)
        self.assertIn("TIMBRO_EXEMPLARS=", out)  # behavior unchanged: still the new root
        self.assertIn("mv", err)

    def test_profiles_diagnose_warns(self):
        home, xdg = self._firing()
        with _default_resolution(home, xdg):
            out, err, code = _run(["profiles", "diagnose", "old-a"])
        self.assertEqual(code, 0)
        self.assertIn("mv", err)

    def test_profiles_learn_warns_before_refusal(self):
        home, xdg = self._firing()
        tdp = Path(xdg).parent
        draft, final = tdp / "draft.md", tdp / "final.md"
        draft.write_text(_DRAFT, encoding="utf-8")
        final.write_text(_DRAFT, encoding="utf-8")
        with _default_resolution(home, xdg):
            out, err, code = _run(
                ["profiles", "learn", "old-a", "--draft", str(draft), "--final", str(final)]
            )
        self.assertNotEqual(code, 0)  # cold-start refusal: pre-existing error path
        self.assertIn("mv", err)

    def test_profiles_add_file_warns_and_keeps_new_root_behavior(self):
        home, xdg = self._firing()
        tdp = Path(xdg).parent
        src = tdp / "doc.md"
        src.write_text(_DRAFT, encoding="utf-8")
        with _default_resolution(home, xdg):
            out, err, code = _run(
                ["profiles", "add-file", "old-a", str(src), "--to", "exemplars"]
            )
        self.assertEqual(code, 0)
        self.assertIn("mv", err)
        # warning only: the profile is still created at the new root, unchanged
        self.assertTrue((home / "profiles" / "old-a" / "exemplars" / "doc.md").exists())


if __name__ == "__main__":
    unittest.main()
