"""Hedge/booster stance axis (#44): lexicon match, rate math, registry, blend fallback."""
from __future__ import annotations

import unittest

from timbro.hedge import (
    HEDGE_BOOSTER_METRIC,
    HEDGE_BOOSTER_REFERENCE,
    hedge_booster_rates,
)
from timbro.metric import REGISTRY, Reference
from timbro.model import HEDGE_AXES, VoiceModel


class SelfCheckTest(unittest.TestCase):
    def test_hedge_heavy_scores_higher_hedge_rate(self):
        hedgy = "I think this might work. It could possibly help, and it seems fine."
        blunt = "This works. It helps, and it is fine."
        h, _ = hedge_booster_rates(hedgy)
        b, _ = hedge_booster_rates(blunt)
        self.assertGreater(h, b)

    def test_booster_heavy_scores_higher_booster_rate(self):
        boosty = "This clearly works. It obviously helps and must be fine."
        blunt = "This works. It helps, and it is fine."
        _, b1 = hedge_booster_rates(boosty)
        _, b2 = hedge_booster_rates(blunt)
        self.assertGreater(b1, b2)

    def test_multi_word_phrases_match(self):
        h, _ = hedge_booster_rates("I think it works.")
        self.assertGreater(h, 0)
        _, b = hedge_booster_rates("Of course it works. In fact it always does, without doubt.")
        self.assertGreater(b, 0)

    def test_pos_gate_disambiguates_might_noun_from_modal(self):
        # "might" the noun (military might) is not a hedge; "might" the modal is.
        h_noun, _ = hedge_booster_rates("The army showed its might.")
        h_modal, _ = hedge_booster_rates("It might work.")
        self.assertEqual(h_noun, 0)
        self.assertGreater(h_modal, 0)

    def test_pos_gate_disambiguates_must_noun_from_modal(self):
        _, boost_noun = hedge_booster_rates("She is a must for the team.")
        _, boost_modal = hedge_booster_rates("It must work.")
        self.assertEqual(boost_noun, 0)
        self.assertGreater(boost_modal, 0)


class RateMathTest(unittest.TestCase):
    def test_exact_rate_on_hand_built_string(self):
        # 10 words, exactly one hedge lemma ("might") -> 1000 * 1 / 10 = 100.0
        text = "It might be true that this small plan will work out fine."
        # recount words the same way the module does
        import re

        n = len(re.findall(r"\b\w+\b", text))
        h, b = hedge_booster_rates(text)
        self.assertAlmostEqual(h, 1000 * 1 / n)
        self.assertEqual(b, 0.0)

    def test_axes_order(self):
        rates = HEDGE_BOOSTER_METRIC.extract("It might work. This is clearly true.")
        self.assertEqual(len(rates), 2)
        self.assertEqual(HEDGE_BOOSTER_METRIC.axes, ("hedge_rate", "booster_rate"))
        h, b = rates
        self.assertGreater(h, 0)
        self.assertGreater(b, 0)


class RegistryTest(unittest.TestCase):
    def test_registered_exactly_once(self):
        from timbro.hedge import _HedgeBoosterMetric
        from timbro.metric import register

        before = sum(1 for m in REGISTRY if m.name == "hedge")
        self.assertEqual(before, 1)
        register(_HedgeBoosterMetric())
        register(_HedgeBoosterMetric())
        after = sum(1 for m in REGISTRY if m.name == "hedge")
        self.assertEqual(after, 1)


class BlendFallbackTest(unittest.TestCase):
    def test_blend_n_zero_passes_prior_through(self):
        mean, spread = HEDGE_BOOSTER_REFERENCE.blend([999.0, 999.0], [999.0, 999.0], 0)
        self.assertEqual(mean, HEDGE_BOOSTER_REFERENCE.mean)
        self.assertEqual(spread, HEDGE_BOOSTER_REFERENCE.spread)

    def test_blend_large_n_favors_corpus(self):
        mean, _ = HEDGE_BOOSTER_REFERENCE.blend([50.0, 50.0], [10.0, 10.0], 10_000)
        self.assertAlmostEqual(mean[0], 50.0, delta=1.0)


class VoiceModelHedgeReportTest(unittest.TestCase):
    _CORPUS = [
        "I think this might work, though it could possibly fail. It seems fine.",
        "This clearly works. It is obviously correct and must succeed. Of course.",
        "The cat sat by the door. It was small and grey outside today.",
    ]

    def test_profiled_model_reports_hedge_axes(self):
        model = VoiceModel.fit(self._CORPUS)
        self.assertGreater(model.hn, 0)
        axes = {a.axis: a for a in model.hedge_report("It might work, perhaps.")}
        self.assertEqual(set(axes), {axis for axis, _, _ in HEDGE_AXES})
        for a in axes.values():
            self.assertTrue(a.axis)

    def test_no_profile_still_reports_via_prior(self):
        # A model with hn=0 falls back to the declared prior alone (n=0 blend passthrough).
        model = VoiceModel.fit(self._CORPUS)
        model.hn = 0
        axes = {a.axis: a for a in model.hedge_report("It might work.")}
        self.assertAlmostEqual(axes["hedge_rate"].reference_mean, HEDGE_BOOSTER_REFERENCE.mean[0])
        self.assertAlmostEqual(axes["booster_rate"].reference_mean, HEDGE_BOOSTER_REFERENCE.mean[1])


if __name__ == "__main__":
    unittest.main()
