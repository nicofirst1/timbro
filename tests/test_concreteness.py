"""Concreteness axis (#46): norms lookup, lazy load, registry, blend fallback."""
from __future__ import annotations

import unittest

from timbro.concreteness import (
    CONCRETENESS_METRIC,
    CONCRETENESS_REFERENCE,
    _norms,
    concreteness_stats,
)
from timbro.metric import REGISTRY, Reference
from timbro.model import CONCRETENESS_AXES, VoiceModel


class LookupTest(unittest.TestCase):
    def test_concrete_scores_higher_than_abstract(self):
        concrete = "The rusty hammer hit the oak table."
        abstract = "The underlying framework enables systemic value."
        c_mean, _ = concreteness_stats(concrete)
        a_mean, _ = concreteness_stats(abstract)
        self.assertGreater(c_mean, a_mean)

    def test_coverage_reported(self):
        _, cov = concreteness_stats("The rusty hammer hit the oak table.")
        self.assertGreater(cov, 0.0)
        self.assertLessEqual(cov, 1.0)

    def test_axes_order(self):
        rates = CONCRETENESS_METRIC.extract("The rusty hammer hit the oak table.")
        self.assertEqual(len(rates), 1)
        self.assertEqual(CONCRETENESS_METRIC.axes, ("mean_concreteness",))
        self.assertGreater(rates[0], 0)


class MissingWordTest(unittest.TestCase):
    def test_out_of_vocabulary_tokens_skipped_not_imputed(self):
        # Nonsense/invented tokens have no norms entry; mean falls back to 0.0 and
        # coverage to 0.0 rather than imputing some default score.
        mean, cov = concreteness_stats("Zxqvlorp fnorbulate xyloplasmatic.")
        self.assertEqual(mean, 0.0)
        self.assertEqual(cov, 0.0)

    def test_function_words_excluded_from_lookup(self):
        # A string of only function words (no NOUN/VERB/ADJ/ADV) has no content tokens.
        mean, cov = concreteness_stats("The of and but with.")
        self.assertEqual(mean, 0.0)
        self.assertEqual(cov, 0.0)


class LazyLoadTest(unittest.TestCase):
    def test_norms_load_lazily_and_cache(self):
        _norms.cache_clear()
        norms = _norms()
        self.assertGreater(len(norms), 30_000)
        self.assertIs(norms, _norms())  # lru_cache: same dict object, loaded once

    def test_known_lemma_present(self):
        norms = _norms()
        self.assertIn("hammer", norms)
        self.assertGreater(norms["hammer"], 4.0)  # highly concrete


class RegistryTest(unittest.TestCase):
    def test_registered_exactly_once(self):
        from timbro.concreteness import _ConcretenessMetric
        from timbro.metric import register

        before = sum(1 for m in REGISTRY if m.name == "concreteness")
        self.assertEqual(before, 1)
        register(_ConcretenessMetric())
        register(_ConcretenessMetric())
        after = sum(1 for m in REGISTRY if m.name == "concreteness")
        self.assertEqual(after, 1)


class BlendFallbackTest(unittest.TestCase):
    def test_blend_n_zero_passes_prior_through(self):
        mean, spread = CONCRETENESS_REFERENCE.blend([9.0], [9.0], 0)
        self.assertEqual(mean, CONCRETENESS_REFERENCE.mean)
        self.assertEqual(spread, CONCRETENESS_REFERENCE.spread)

    def test_blend_large_n_favors_corpus(self):
        mean, _ = CONCRETENESS_REFERENCE.blend([4.0], [0.5], 10_000)
        self.assertAlmostEqual(mean[0], 4.0, delta=0.05)


class VoiceModelConcretenessReportTest(unittest.TestCase):
    _CORPUS = [
        "The rusty hammer hit the oak table. The dog ran across the wet grass.",
        "This clearly works. It is obviously correct and must succeed eventually.",
        "The cat sat by the door. It was small and grey outside today.",
    ]

    def test_profiled_model_reports_concreteness_axis(self):
        model = VoiceModel.fit(self._CORPUS)
        self.assertGreater(model.cn, 0)
        axes = {a.axis: a for a in model.concreteness_report("The hammer hit the table.")}
        self.assertEqual(set(axes), {axis for axis, _, _ in CONCRETENESS_AXES})
        for a in axes.values():
            self.assertTrue(a.axis)

    def test_no_profile_still_reports_via_prior(self):
        model = VoiceModel.fit(self._CORPUS)
        model.cn = 0
        axes = {a.axis: a for a in model.concreteness_report("The hammer hit the table.")}
        self.assertAlmostEqual(
            axes["mean_concreteness"].reference_mean, CONCRETENESS_REFERENCE.mean[0]
        )


if __name__ == "__main__":
    unittest.main()
