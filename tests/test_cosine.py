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

from timbro.flow import flow_report, novelty_curve
from timbro.rubrics import features


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

    Expected values are hand-computed literals from an integer matrix, NOT
    values computed with cosine itself, so the tests stay valid even if the
    helper's internals mutate (P1). They fail on base, where flow uses raw
    dot products and never normalizes its inputs.
    """

    # Integer non-unit matrix; vector norms 3, 4, 5 (two 3-4-5 triangles).
    EMB = np.array(
        [
            [3.0, 0.0],
            [0.0, 4.0],
            [3.0, 4.0],
        ]
    )

    def _report(self):
        with mock.patch("timbro.flow.embed", return_value=self.EMB):
            return flow_report("paragraph text is ignored; embed is patched")

    def test_coherence_is_mean_of_pairwise_cosines(self):
        # cos(e0, e1) = (3*0 + 0*4) / (3*4)   =  0/12 = 0.0
        # cos(e1, e2) = (0*3 + 4*4) / (4*5)   = 16/20 = 0.8
        # coherence   = (0.0 + 0.8) / 2       = 0.4
        self.assertAlmostEqual(self._report().coherence, 0.4, places=12)

    def test_novelty_curve_uses_cosine_not_raw_dot(self):
        # i=1: centroid is e0 = [3, 0]; cos(e1, [3, 0]) = (0*3 + 4*0) / (4*3) = 0.0
        #      -> 1 - 0.0 = 1.0
        # i=2: centroid is (e0 + e1) / 2 = [1.5, 2.0], norm sqrt(6.25) = 2.5;
        #      cos(e2, [1.5, 2.0]) = (3*1.5 + 4*2) / (5*2.5) = 12.5 / 12.5 = 1.0
        #      -> 1 - 1.0 = 0.0  ([3, 4] is exactly 2x its running centroid)
        np.testing.assert_allclose(novelty_curve(self.EMB), [1.0, 0.0], rtol=0, atol=1e-12)

    def test_circle_back_is_cosine_of_first_and_last(self):
        # cos(e0, e2) = (3*3 + 0*4) / (3*5) = 9/15 = 0.6
        self.assertAlmostEqual(self._report().circle_back, 0.6, places=12)


if __name__ == "__main__":
    unittest.main()
