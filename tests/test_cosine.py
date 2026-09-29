"""Tests for the shared cosine helper (#115).

`timbro.text.cosine` is explicit-norm cosine: safe for non-unit inputs, 0.0 for
a zero vector. rubrics/features.py and flow.py must both use it instead of
computing cosine locally.
"""

from __future__ import annotations

import math
import unittest
from unittest import mock

import numpy as np

import timbro.rubrics.features as features
from timbro.flow import flow_report, novelty_curve


class CosineHelperTests(unittest.TestCase):
    def test_cosine_exists_in_text(self):
        from timbro.text import cosine

        self.assertTrue(callable(cosine))

    def test_identical_vectors_give_one(self):
        from timbro.text import cosine

        self.assertEqual(cosine(np.array([1.0, 2.0, 3.0]), np.array([1.0, 2.0, 3.0])), 1.0)

    def test_orthogonal_vectors_give_zero(self):
        from timbro.text import cosine

        self.assertEqual(cosine(np.array([1.0, 0.0]), np.array([0.0, 1.0])), 0.0)

    def test_zero_vector_gives_zero_without_nan(self):
        from timbro.text import cosine

        zero = np.zeros(2)
        self.assertEqual(cosine(zero, np.array([1.0, 2.0])), 0.0)
        self.assertEqual(cosine(zero, zero), 0.0)
        self.assertFalse(math.isnan(cosine(zero, np.array([1.0, 2.0]))))
        self.assertFalse(math.isnan(cosine(zero, zero)))

    def test_non_unit_inputs_are_normalized(self):
        from timbro.text import cosine

        self.assertEqual(cosine(np.array([3.0, 0.0]), np.array([5.0, 0.0])), 1.0)

    def test_matches_explicit_norm_formula_on_random_float32(self):
        from timbro.text import cosine

        rng = np.random.default_rng(115)
        for _ in range(50):
            a = rng.standard_normal(384).astype(np.float32)
            b = rng.standard_normal(384).astype(np.float32)
            expected = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
            self.assertAlmostEqual(cosine(a, b), expected, delta=1e-6)


class FeaturesUseSharedCosineTests(unittest.TestCase):
    def test_features_no_longer_defines_private_cos(self):
        self.assertFalse(hasattr(features, "_cos"))


class FlowUsesCosineTests(unittest.TestCase):
    """flow must produce cosine-based values on hand-built NON-UNIT embeddings.

    These fail on base, where flow uses raw dot products and never normalizes
    its inputs.
    """

    # Hand-built non-unit embedding matrix: norms 3, 6, sqrt(2), sqrt(5).
    EMB = np.array(
        [
            [3.0, 0.0],
            [6.0, 0.0],
            [1.0, 1.0],
            [1.0, 2.0],
        ]
    )

    def _report(self):
        with mock.patch("timbro.flow.embed", return_value=self.EMB):
            return flow_report("paragraph text is ignored; embed is patched")

    def test_coherence_is_mean_of_pairwise_cosines(self):
        from timbro.text import cosine

        emb = self.EMB
        expected = float(
            np.mean([cosine(emb[i], emb[i + 1]) for i in range(len(emb) - 1)])
        )
        self.assertAlmostEqual(self._report().coherence, expected, places=12)

    def test_novelty_curve_uses_cosine_not_raw_dot(self):
        from timbro.text import cosine

        emb = self.EMB
        expected = np.array(
            [1 - cosine(emb[i], emb[:i].mean(0)) for i in range(1, len(emb))]
        )
        np.testing.assert_allclose(novelty_curve(emb), expected, rtol=0, atol=1e-12)

    def test_circle_back_is_cosine_of_first_and_last(self):
        from timbro.text import cosine

        expected = cosine(self.EMB[0], self.EMB[-1])
        self.assertAlmostEqual(self._report().circle_back, expected, places=12)


if __name__ == "__main__":
    unittest.main()
