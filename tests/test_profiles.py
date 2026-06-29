from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from timbro.cleanup.latex import has_detex
from timbro.profiles import add_file, diagnose_profile, init_profile


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


if __name__ == "__main__":
    unittest.main()
