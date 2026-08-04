"""Derivation script math (#58): weighted mean/spread, TSV parsing, lemma-set join."""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from derive_concreteness_prior import derive, load_vendored_lemmas, parse_original_tsv, weighted_mean_spread


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


if __name__ == "__main__":
    unittest.main()
