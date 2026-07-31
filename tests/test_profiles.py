from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from timbro.cleanup.latex import has_detex
from timbro.profiles import add_file, diagnose_profile, init_profile, profile_root


@unittest.skipUnless(has_detex(), "detex is required for .tex ingestion tests")
class ProfileTexIngestionTests(unittest.TestCase):
    def test_add_file_converts_tex_to_markdown(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            src = Path(td) / "paper.tex"
            src.write_text(
                "\\begin{abstract}\n"
                "This is the abstract.\n"
                "\\end{abstract}\n"
                "\\section{Introduction}\n"
                "This is the introduction with $x+y$.\n",
                encoding="utf-8",
            )

            init_profile("demo", root=root)
            dst = add_file("demo", src, bucket="exemplars", root=root)

            self.assertEqual(dst.suffix, ".md")
            text = dst.read_text(encoding="utf-8")
            self.assertIn("This is the abstract.", text)
            self.assertIn("This is the introduction", text)
            self.assertNotIn("\\section", text)


class ProfileDiagnosticsTests(unittest.TestCase):
    def test_diagnose_profile_flags_outlier(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            prof = init_profile("demo", root=root)
            for i in range(6):
                (prof.exemplars_dir / f"doc{i}.md").write_text(f"sample text {i}", encoding="utf-8")

            vecs = {
                "sample text 0": (1.0, 0.0),
                "sample text 1": (1.0, 0.1),
                "sample text 2": (0.9, 0.0),
                "sample text 3": (0.95, 0.05),
                "sample text 4": (1.0, -0.1),
                "sample text 5": (-1.0, 0.0),
            }

            def fake_style_vec(text: str):
                return vecs[text]

            with patch("timbro.profiles._style_vec", side_effect=fake_style_vec):
                result = diagnose_profile("demo", root=root)

            self.assertEqual(result["exemplars"], 6)
            self.assertIn("doc5.md", result["outliers"])
            self.assertTrue(result["warning"])


class ProfileRootResolutionTests(unittest.TestCase):
    def test_xdg_data_home_default_when_no_legacy_dir(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as xdg:
            with patch.dict(
                os.environ,
                {"XDG_DATA_HOME": xdg, "HOME": home},
                clear=False,
            ):
                os.environ.pop("TIMBRO_PROFILE_ROOT", None)
                with patch.object(Path, "home", return_value=Path(home)):
                    result = profile_root()
            self.assertEqual(result, (Path(xdg) / "timbro" / "profiles").resolve())

    def test_legacy_dir_wins_when_present(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as xdg:
            legacy = Path(home) / ".timbro" / "profiles"
            legacy.mkdir(parents=True)
            with patch.dict(os.environ, {"XDG_DATA_HOME": xdg}, clear=False):
                os.environ.pop("TIMBRO_PROFILE_ROOT", None)
                with patch.object(Path, "home", return_value=Path(home)):
                    result = profile_root()
            self.assertEqual(result, legacy.resolve())

    def test_env_var_overrides_legacy_and_xdg(self):
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as override:
            legacy = Path(home) / ".timbro" / "profiles"
            legacy.mkdir(parents=True)
            with patch.dict(os.environ, {"TIMBRO_PROFILE_ROOT": override}, clear=False):
                with patch.object(Path, "home", return_value=Path(home)):
                    result = profile_root()
            self.assertEqual(result, Path(override).resolve())


if __name__ == "__main__":
    unittest.main()
