"""Readability/richness/entropy axis (#88): extractor math, registry, blend fallback."""
from __future__ import annotations

import unittest

from timbro.metric import REGISTRY, Reference
from timbro.model import RICHNESS_AXES, VoiceModel
from timbro.richness import (
    RICHNESS_METRIC,
    RICHNESS_REFERENCE,
    richness_stats,
)

# >42 content-word tokens each -- lexical_diversity's hdd() samples a fixed 42-token
# window and degenerates to 0.0 below that (see richness.py's __main__ self-check).
_PLAIN = ("The cat sat on the mat. The cat was happy. The cat liked the mat. "
          "The cat sat there all day. The mat was soft and the cat liked it. "
          "The dog ran in the yard. The dog was happy. The dog liked the yard. "
          "The dog ran there all day. The yard was big and the dog liked it. "
          "The cat and the dog were friends. They sat in the yard on the mat. "
          "They liked the sun and the soft grass. The day was long and warm.")
_DENSE = ("Epistemological frameworks underpinning contemporary jurisprudence "
          "necessitate a multifaceted reconsideration of adjudicative precedent, "
          "particularly where constitutional ambiguity intersects procedural "
          "heterodoxy across divergent federalist jurisdictions. Subsequent "
          "scholarship interrogates these entrenched assumptions, proposing "
          "alternative taxonomies that destabilize orthodox categorization "
          "while foregrounding marginalized interpretive traditions. Critics "
          "counter that such revisionism, however illuminating, risks eroding "
          "the doctrinal coherence upon which adjudicative legitimacy depends.")


class SelfCheckTest(unittest.TestCase):
    def test_dense_scores_higher_readability_richness_entropy_than_plain(self):
        r_plain, v_plain, e_plain = richness_stats(_PLAIN)
        r_dense, v_dense, e_dense = richness_stats(_DENSE)
        self.assertGreater(r_dense, r_plain)
        self.assertGreater(v_dense, v_plain)
        self.assertGreater(e_dense, e_plain)

    def test_short_text_hdd_degenerates_to_zero_not_imputed(self):
        # Below the 42-content-token window lexical_diversity's hdd() needs, richness
        # is reported as 0.0 rather than some imputed default -- same "don't impute"
        # convention as concreteness.py's out-of-vocabulary handling.
        _, richness, _ = richness_stats("The cat sat on the mat.")
        self.assertEqual(richness, 0.0)

    def test_empty_text_returns_zeros(self):
        readability, richness, entropy = richness_stats("")
        self.assertEqual(richness, 0.0)
        self.assertEqual(entropy, 0.0)


class ExtractorTest(unittest.TestCase):
    def test_axes_order(self):
        rates = RICHNESS_METRIC.extract(_DENSE)
        self.assertEqual(len(rates), 3)
        self.assertEqual(RICHNESS_METRIC.axes, ("readability", "richness", "entropy"))


class RegistryTest(unittest.TestCase):
    def test_registered_exactly_once(self):
        from timbro.metric import register
        from timbro.richness import _RichnessMetric

        before = sum(1 for m in REGISTRY if m.name == "richness")
        self.assertEqual(before, 1)
        register(_RichnessMetric())
        register(_RichnessMetric())
        after = sum(1 for m in REGISTRY if m.name == "richness")
        self.assertEqual(after, 1)


class BlendFallbackTest(unittest.TestCase):
    def test_blend_n_zero_passes_prior_through(self):
        mean, spread = RICHNESS_REFERENCE.blend([999.0, 999.0, 999.0], [999.0, 999.0, 999.0], 0)
        self.assertEqual(mean, RICHNESS_REFERENCE.mean)
        self.assertEqual(spread, RICHNESS_REFERENCE.spread)

    def test_blend_large_n_favors_corpus(self):
        mean, _ = RICHNESS_REFERENCE.blend([20.0, 0.5, 5.0], [1.0, 0.05, 0.3], 10_000)
        self.assertAlmostEqual(mean[0], 20.0, delta=0.5)


class VoiceModelRichnessReportTest(unittest.TestCase):
    _CORPUS = [_PLAIN, _DENSE]

    def test_profiled_model_reports_richness_axes(self):
        model = VoiceModel.fit(self._CORPUS)
        self.assertGreater(model.rn, 0)
        axes = {a.axis: a for a in model.richness_report(_DENSE)}
        self.assertEqual(set(axes), {axis for axis, _, _ in RICHNESS_AXES})
        for a in axes.values():
            self.assertTrue(a.axis)

    def test_no_profile_still_reports_via_prior(self):
        model = VoiceModel.fit(self._CORPUS)
        model.rn = 0
        axes = {a.axis: a for a in model.richness_report(_DENSE)}
        self.assertAlmostEqual(axes["readability"].reference_mean, RICHNESS_REFERENCE.mean[0])
        self.assertAlmostEqual(axes["richness"].reference_mean, RICHNESS_REFERENCE.mean[1])
        self.assertAlmostEqual(axes["entropy"].reference_mean, RICHNESS_REFERENCE.mean[2])


if __name__ == "__main__":
    unittest.main()
