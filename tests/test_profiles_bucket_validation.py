from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from timbro.profiles import add_file, add_text


class ProfileBucketValidationTests(unittest.TestCase):
    def test_add_text_rejects_unknown_bucket_without_creating_anything(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"

            with self.assertRaises(ValueError) as cm:
                add_text("demo", "some text", bucket="bogus", title="t", root=root)

            self.assertEqual(
                str(cm.exception),
                "bucket must be 'exemplars' or 'contrast', got 'bogus'",
            )
            # Nothing written: no profile dir scaffolded, no files at all.
            self.assertFalse((root / "demo").exists())
            self.assertEqual(list(root.rglob("*")) if root.exists() else [], [])

    def test_add_file_rejects_unknown_bucket_without_creating_anything(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            src = Path(td) / "note.md"
            src.write_text("source text", encoding="utf-8")

            with self.assertRaises(ValueError) as cm:
                add_file("demo", src, bucket="bogus", root=root)

            self.assertEqual(
                str(cm.exception),
                "bucket must be 'exemplars' or 'contrast', got 'bogus'",
            )
            # Nothing written: no profile dir scaffolded, no files at all.
            self.assertFalse((root / "demo").exists())
            self.assertEqual(list(root.rglob("*")) if root.exists() else [], [])

    def test_add_text_valid_buckets_land_in_the_right_dir(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"

            to_exemplars = add_text("demo", "toward text", bucket="exemplars", title="note", root=root)
            to_contrast = add_text("demo", "away text", bucket="contrast", title="other note", root=root)

            self.assertTrue((root / "demo" / "exemplars" / "note.md").exists())
            self.assertEqual((root / "demo" / "exemplars" / "note.md").read_text(encoding="utf-8"), "toward text")
            self.assertTrue((root / "demo" / "contrast" / "other-note.md").exists())
            self.assertEqual((root / "demo" / "contrast" / "other-note.md").read_text(encoding="utf-8"), "away text")
            self.assertEqual(to_exemplars.name, "note.md")
            self.assertEqual(to_contrast.name, "other-note.md")

    def test_add_file_valid_buckets_land_in_the_right_dir(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            src = Path(td) / "note.md"
            src.write_text("source text", encoding="utf-8")

            to_exemplars = add_file("demo", src, bucket="exemplars", root=root)
            to_contrast = add_file("demo", src, bucket="contrast", dest_name="other.md", root=root)

            self.assertTrue((root / "demo" / "exemplars" / "note.md").exists())
            self.assertEqual((root / "demo" / "exemplars" / "note.md").read_text(encoding="utf-8"), "source text")
            self.assertTrue((root / "demo" / "contrast" / "other.md").exists())
            self.assertEqual((root / "demo" / "contrast" / "other.md").read_text(encoding="utf-8"), "source text")
            self.assertEqual(to_exemplars.name, "note.md")
            self.assertEqual(to_contrast.name, "other.md")


if __name__ == "__main__":
    unittest.main()
