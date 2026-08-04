"""Pure-computation tests for scripts/derive_fw_reference.py (#59): boilerplate
stripping, chunking, and mean/spread derivation -- no network, no spaCy."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from derive_fw_reference import chunk_words, derive_reference, strip_gutenberg_boilerplate  # noqa: E402


class StripBoilerplateTest(unittest.TestCase):
    def test_strips_header_and_footer(self):
        raw = (
            "Junk before.\n"
            "*** START OF THE PROJECT GUTENBERG EBOOK FOO ***\n"
            "The actual book text goes here.\n"
            "*** END OF THE PROJECT GUTENBERG EBOOK FOO ***\n"
            "Junk after."
        )
        body = strip_gutenberg_boilerplate(raw)
        self.assertIn("The actual book text goes here.", body)
        self.assertNotIn("Junk before", body)
        self.assertNotIn("Junk after", body)

    def test_passes_through_when_markers_absent(self):
        raw = "No Gutenberg markers here at all."
        self.assertEqual(strip_gutenberg_boilerplate(raw), raw)


class ChunkWordsTest(unittest.TestCase):
    def test_splits_into_fixed_size_chunks_dropping_remainder(self):
        text = " ".join(f"w{i}" for i in range(2500))
        chunks = chunk_words(text, chunk_words=1000)
        self.assertEqual(len(chunks), 2)
        for c in chunks:
            self.assertEqual(len(c.split()), 1000)

    def test_short_text_yields_no_chunks(self):
        text = " ".join(f"w{i}" for i in range(10))
        self.assertEqual(chunk_words(text, chunk_words=1000), [])


class DeriveReferenceTest(unittest.TestCase):
    def test_mean_and_pstdev_per_axis(self):
        chunks = ["a", "b", "c"]
        rates = {"a": (10.0, 20.0), "b": (20.0, 20.0), "c": (30.0, 20.0)}
        means, spreads, n = derive_reference(chunks, lambda c: rates[c])
        self.assertEqual(n, 3)
        self.assertAlmostEqual(means[0], 20.0)
        self.assertAlmostEqual(means[1], 20.0)
        self.assertGreater(spreads[0], 0.0)
        self.assertAlmostEqual(spreads[1], 0.0)


if __name__ == "__main__":
    unittest.main()
