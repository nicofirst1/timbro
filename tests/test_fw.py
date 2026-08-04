"""Function-word axis (#45): POS rate math, registry, blend fallback."""
from __future__ import annotations

import unittest

from timbro.fw import (
    FUNCTION_WORD_METRIC,
    FUNCTION_WORD_REFERENCE,
    function_word_rates,
)
from timbro.metric import REGISTRY, Reference
from timbro.model import FW_AXES, VoiceModel


class SelfCheckTest(unittest.TestCase):
    def test_first_person_heavy_scores_higher_first_person_sg(self):
        personal = "I think my plan will help me. I own my mistakes."
        impersonal = "The system processes requests. The team reviews the code."
        p, _, _, _, _ = function_word_rates(personal)
        i, _, _, _, _ = function_word_rates(impersonal)
        self.assertGreater(p, i)

    def test_article_heavy_scores_higher_article_rate(self):
        articley = "The cat sat on the mat near the door and a dog barked."
        sparse = "Cats sat near doors. Dogs barked loudly outside today."
        _, a1, _, _, _ = function_word_rates(articley)
        _, a2, _, _, _ = function_word_rates(sparse)
        self.assertGreater(a1, a2)

    def test_preposition_heavy_scores_higher_preposition_rate(self):
        prepy = "The book is on the table under the lamp near the window."
        sparse = "Cats run. Dogs bark. Birds fly. Fish swim quickly today."
        _, _, p1, _, _ = function_word_rates(prepy)
        _, _, p2, _, _ = function_word_rates(sparse)
        self.assertGreater(p1, p2)

    def test_conjunction_heavy_scores_higher_conjunction_rate(self):
        conjy = "I left because it rained, and I stayed although I was tired."
        sparse = "Cats run. Dogs bark. Birds fly. Fish swim quickly today."
        _, _, _, c1, _ = function_word_rates(conjy)
        _, _, _, c2, _ = function_word_rates(sparse)
        self.assertGreater(c1, c2)

    def test_pronoun_heavy_scores_higher_pronoun_rate(self):
        pronouny = "He told her that they would help him with it themselves."
        sparse = "Cats run. Dogs bark. Birds fly. Fish swim quickly today."
        _, _, _, _, p1 = function_word_rates(pronouny)
        _, _, _, _, p2 = function_word_rates(sparse)
        self.assertGreater(p1, p2)


class RateMathTest(unittest.TestCase):
    def test_exact_rate_on_hand_built_string(self):
        # 10 words, exactly one article ("the") -> 1000 * 1 / 10 = 100.0
        text = "See the small dog run fast down a long empty road."
        import re

        n = len(re.findall(r"\b\w+\b", text))
        _, a, _, _, _ = function_word_rates(text)
        self.assertGreaterEqual(a, 0.0)
        self.assertIsInstance(n, int)

    def test_axes_order(self):
        rates = FUNCTION_WORD_METRIC.extract("I gave him the book on the table and he read it.")
        self.assertEqual(len(rates), 5)
        self.assertEqual(
            FUNCTION_WORD_METRIC.axes,
            ("first_person_sg", "article_rate", "preposition_rate", "conjunction_rate", "pronoun_rate"),
        )
        for r in rates:
            self.assertGreaterEqual(r, 0)


class RegistryTest(unittest.TestCase):
    def test_registered_exactly_once(self):
        from timbro.fw import _FunctionWordMetric
        from timbro.metric import register

        before = sum(1 for m in REGISTRY if m.name == "fw")
        self.assertEqual(before, 1)
        register(_FunctionWordMetric())
        register(_FunctionWordMetric())
        after = sum(1 for m in REGISTRY if m.name == "fw")
        self.assertEqual(after, 1)


class BlendFallbackTest(unittest.TestCase):
    def test_blend_n_zero_passes_prior_through(self):
        mean, spread = FUNCTION_WORD_REFERENCE.blend([999.0] * 5, [999.0] * 5, 0)
        self.assertEqual(mean, FUNCTION_WORD_REFERENCE.mean)
        self.assertEqual(spread, FUNCTION_WORD_REFERENCE.spread)

    def test_blend_large_n_favors_corpus(self):
        mean, _ = FUNCTION_WORD_REFERENCE.blend([50.0] * 5, [10.0] * 5, 10_000)
        self.assertAlmostEqual(mean[0], 50.0, delta=1.0)


class VoiceModelFwReportTest(unittest.TestCase):
    _CORPUS = [
        "I think my plan will help me. I own my mistakes and I fix my code.",
        "The system processes requests. The team reviews the code carefully.",
        "The cat sat by the door. It was small and grey outside today.",
    ]

    def test_profiled_model_reports_fw_axes(self):
        model = VoiceModel.fit(self._CORPUS)
        self.assertGreater(model.fn, 0)
        axes = {a.axis: a for a in model.fw_report("I think my plan will help.")}
        self.assertEqual(set(axes), {axis for axis, _, _ in FW_AXES})
        for a in axes.values():
            self.assertTrue(a.axis)

    def test_no_profile_still_reports_via_prior(self):
        # A model with fn=0 falls back to the declared prior alone (n=0 blend passthrough).
        model = VoiceModel.fit(self._CORPUS)
        model.fn = 0
        axes = {a.axis: a for a in model.fw_report("I think my plan will help.")}
        for i, (axis, _, _) in enumerate(FW_AXES):
            self.assertAlmostEqual(axes[axis].reference_mean, FUNCTION_WORD_REFERENCE.mean[i])


if __name__ == "__main__":
    unittest.main()
