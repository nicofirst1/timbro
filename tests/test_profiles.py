from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from timbro.cleanup.latex import has_detex
from timbro.profiles import add_file, diagnose_profile, init_profile, learn, profile_root


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


FINAL_TEXT = (
    "The committee reviewed the annual budget with care. Members raised concerns about "
    "research funding and asked for a revised proposal. After careful deliberation, the "
    "board approved the plan and scheduled a follow-up meeting for next quarter. Staff "
    "will circulate the finalized figures before the next session begins."
)

DRAFT_TEXT = (
    "The committee reviewed the annual budget. Members raised concerns about research "
    "funding and asked for a revised proposal. After a lot of back and forth, the board "
    "agreed to the plan and scheduled a follow-up meeting for next quarter. Staff will "
    "send out the finalized figures before the next session begins."
)


class ProfileLearnTests(unittest.TestCase):
    def _seed(self, root: Path, name: str = "demo") -> None:
        init_profile(name, root=root)
        exemplars_dir = root / name / "exemplars"
        for i in range(3):
            (exemplars_dir / f"seed{i}.md").write_text(FINAL_TEXT, encoding="utf-8")

    def test_learn_saves_when_final_is_closer_and_content_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            self._seed(root)

            draft_path = Path(td) / "draft.md"
            final_path = Path(td) / "final.md"
            draft_path.write_text(DRAFT_TEXT, encoding="utf-8")
            final_path.write_text(FINAL_TEXT, encoding="utf-8")

            result = learn("demo", draft_path, final_path, title="budget-memo", root=root)

            self.assertTrue(result["saved"])
            exemplar_path = root / "demo" / "exemplars" / "budget-memo.md"
            contrast_path = root / "demo" / "contrast" / "budget-memo.md"
            self.assertTrue(exemplar_path.exists())
            self.assertTrue(contrast_path.exists())
            self.assertEqual(exemplar_path.read_text(encoding="utf-8"), FINAL_TEXT)
            self.assertEqual(contrast_path.read_text(encoding="utf-8"), DRAFT_TEXT)

    def test_learn_refuses_when_not_improved_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            self._seed(root)

            draft_path = Path(td) / "draft.md"
            final_path = Path(td) / "final.md"
            draft_path.write_text(FINAL_TEXT, encoding="utf-8")
            final_path.write_text(FINAL_TEXT, encoding="utf-8")

            result = learn("demo", draft_path, final_path, title="identical", root=root)

            self.assertFalse(result["saved"])
            self.assertIn("distance", result["reason"])
            self.assertFalse((root / "demo" / "exemplars" / "identical.md").exists())
            self.assertFalse((root / "demo" / "contrast" / "identical.md").exists())

    def test_learn_force_overrides_refusal(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            self._seed(root)

            draft_path = Path(td) / "draft.md"
            final_path = Path(td) / "final.md"
            draft_path.write_text(FINAL_TEXT, encoding="utf-8")
            final_path.write_text(FINAL_TEXT, encoding="utf-8")

            result = learn("demo", draft_path, final_path, title="forced", force=True, root=root)

            self.assertTrue(result["saved"])
            self.assertTrue((root / "demo" / "exemplars" / "forced.md").exists())
            self.assertTrue((root / "demo" / "contrast" / "forced.md").exists())

    def test_learn_refuses_atomically_on_partial_title_collision(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            self._seed(root)

            # Pre-existing contrast file for the title, but no exemplar file yet --
            # the collision must block BOTH writes, not just the second one.
            contrast_path = root / "demo" / "contrast" / "budget-memo.md"
            contrast_path.parent.mkdir(parents=True, exist_ok=True)
            stale_contrast = "pre-existing contrast content"
            contrast_path.write_text(stale_contrast, encoding="utf-8")

            draft_path = Path(td) / "draft.md"
            final_path = Path(td) / "final.md"
            draft_path.write_text(DRAFT_TEXT, encoding="utf-8")
            final_path.write_text(FINAL_TEXT, encoding="utf-8")

            with self.assertRaises(FileExistsError):
                learn("demo", draft_path, final_path, title="budget-memo", root=root)

            exemplar_path = root / "demo" / "exemplars" / "budget-memo.md"
            self.assertFalse(exemplar_path.exists())
            self.assertEqual(contrast_path.read_text(encoding="utf-8"), stale_contrast)

    def test_learn_cold_start_requires_force(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            init_profile("empty", root=root)

            draft_path = Path(td) / "draft.md"
            final_path = Path(td) / "final.md"
            draft_path.write_text(DRAFT_TEXT, encoding="utf-8")
            final_path.write_text(FINAL_TEXT, encoding="utf-8")

            with self.assertRaises(ValueError):
                learn("empty", draft_path, final_path, root=root)

            result = learn("empty", draft_path, final_path, force=True, root=root)
            self.assertTrue(result["saved"])
            self.assertIsNone(result["accepted"])
            self.assertTrue((root / "empty" / "exemplars" / "final.md").exists())
            self.assertTrue((root / "empty" / "contrast" / "final.md").exists())


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
