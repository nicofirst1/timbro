from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from timbro.cleanup import has_detex
from timbro.profiles import add_file, init_profile


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


if __name__ == "__main__":
    unittest.main()
