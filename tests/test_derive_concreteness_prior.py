"""Derivation script math (#58): weighted mean/spread, TSV parsing, lemma-set join."""
from __future__ import annotations

import math
import statistics
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from derive_concreteness_prior import (
    chunk_words,
    derive,
    derive_document_spread,
    load_vendored_lemmas,
    parse_original_tsv,
    strip_gutenberg_boilerplate,
    weighted_mean_spread,
)


class WeightedMeanSpreadTest(unittest.TestCase):
    def test_equal_weights_matches_plain_mean_and_pstdev(self):
        values = [1.0, 2.0, 3.0]
        weights = [1.0, 1.0, 1.0]
        mean, spread = weighted_mean_spread(values, weights)
        self.assertAlmostEqual(mean, 2.0)
        self.assertAlmostEqual(spread, math.sqrt(2 / 3))

    def test_high_frequency_value_dominates_mean(self):
        # One value weighted far heavier than the other should pull the mean toward it.
        values = [1.0, 5.0]
        weights = [1.0, 999.0]
        mean, _ = weighted_mean_spread(values, weights)
        self.assertGreater(mean, 4.9)

    def test_uniform_values_give_zero_spread(self):
        mean, spread = weighted_mean_spread([3.0, 3.0, 3.0], [1.0, 10.0, 100.0])
        self.assertAlmostEqual(mean, 3.0)
        self.assertAlmostEqual(spread, 0.0)


class ParseOriginalTsvTest(unittest.TestCase):
    _HEADER = "Word\tBigram\tConc.M\tConc.SD\tUnknown\tTotal\tPercent_known\tSUBTLEX\tDom_Pos"

    def test_keeps_only_single_word_rows(self):
        text = "\n".join([
            self._HEADER,
            "hammer\t0\t4.81\t0.4\t0\t25\t1.0\t120\tNoun",
            "roller coaster\t1\t4.5\t0.5\t0\t25\t1.0\t5\tNoun",
        ])
        rows = parse_original_tsv(text)
        self.assertEqual(rows, [("hammer", 4.81, 120.0)])


class DeriveTest(unittest.TestCase):
    def test_restricts_to_vendored_lemma_set(self):
        rows = [
            ("hammer", 4.81, 100.0),
            ("idea", 1.5, 50.0),
            ("notinvendored", 3.0, 99999.0),  # excluded: high freq should NOT skew result
        ]
        vendored_lemmas = {"hammer", "idea"}
        mean, spread = derive(rows, vendored_lemmas)
        expected_mean, expected_spread = weighted_mean_spread([4.81, 1.5], [100.0, 50.0])
        self.assertAlmostEqual(mean, expected_mean)
        self.assertAlmostEqual(spread, expected_spread)


class VendoredLemmaJoinTest(unittest.TestCase):
    def test_vendored_lemma_set_is_full_37058_row_table(self):
        # Sanity check on the shipped norms file this script joins against -- catches
        # accidental norms-file swaps that would silently change the derived prior.
        lemmas = load_vendored_lemmas()
        self.assertEqual(len(lemmas), 37058)
        self.assertIn("hammer", lemmas)


class DeriveDocumentSpreadTest(unittest.TestCase):
    def test_pstdev_of_per_chunk_means(self):
        chunks = ["a", "b", "c"]
        fn = {"a": 1.0, "b": 2.0, "c": 3.0}.get
        spread = derive_document_spread(chunks, fn)
        self.assertAlmostEqual(spread, statistics.pstdev([1.0, 2.0, 3.0]))

    def test_identical_chunk_means_give_zero_spread(self):
        chunks = ["x", "y"]
        spread = derive_document_spread(chunks, lambda _: 2.5)
        self.assertAlmostEqual(spread, 0.0)


class ChunkingAndBoilerplateTest(unittest.TestCase):
    def test_strip_gutenberg_boilerplate_keeps_only_body(self):
        raw = (
            "Header junk\n"
            "*** START OF THE PROJECT GUTENBERG EBOOK FOO ***\n"
            "the actual book text\n"
            "*** END OF THE PROJECT GUTENBERG EBOOK FOO ***\n"
            "License footer junk"
        )
        body = strip_gutenberg_boilerplate(raw)
        self.assertIn("the actual book text", body)
        self.assertNotIn("Header junk", body)
        self.assertNotIn("License footer junk", body)

    def test_chunk_words_drops_trailing_partial_chunk(self):
        text = " ".join(f"w{i}" for i in range(25))
        chunks = chunk_words(text, chunk_words=10)
        self.assertEqual(len(chunks), 2)
        self.assertEqual(len(chunks[0].split()), 10)
        self.assertEqual(len(chunks[1].split()), 10)


class SpreadUnitRegressionTest(unittest.TestCase):
    def test_document_level_spread_is_far_below_lemma_level_spread(self):
        # Regression guard for the #58 verifier finding: document-level mean
        # concreteness varies far less than individual lemma concreteness ratings
        # (a document averages many words together), so the two spreads must not be
        # interchangeable. The lemma-level weighted spread over the full norms table
        # is ~1.05; the config's document-level spread must stay well under half of
        # that, or CONCRETENESS_REFERENCE.spread has silently been fed the wrong unit
        # again (model.py's z-score divides by it directly).
        from timbro.config import CONCRETENESS_REFERENCE

        self.assertLess(CONCRETENESS_REFERENCE.spread[0], 0.5)


if __name__ == "__main__":
    unittest.main()
