"""Politeness strategies axis (#94): strategy matching, N/A gate, registry, report wiring."""
from __future__ import annotations

import unittest

from timbro.metric import REGISTRY
from timbro.politeness import (
    POLITENESS_METRIC,
    politeness_counts,
    politeness_report,
    politeness_total,
)


class StrategyMatchTest(unittest.TestCase):
    def test_polite_request_fires_several_strategies(self):
        text = (
            "Hi Sam, thanks so much for your help yesterday. Could you please send "
            "over the updated file when you get a chance? I really appreciate it, "
            "and sorry for the short notice."
        )
        counts = politeness_counts(text)
        self.assertGreater(counts["gratitude"], 0)
        self.assertGreater(counts["greeting"], 0)
        self.assertGreater(counts["please"], 0)
        self.assertGreater(counts["counterfactual_modal"], 0)
        self.assertGreater(counts["apologizing"], 0)
        self.assertGreater(counts["first_person"], 0)
        self.assertGreater(politeness_total(text), 5)

    def test_please_start_fires_only_when_sentence_initial(self):
        start = politeness_counts("Please send the file.")
        mid = politeness_counts("Could you please send the file?")
        self.assertGreater(start["please_start"], 0)
        self.assertGreater(start["please"], 0)
        self.assertEqual(mid["please_start"], 0)
        self.assertGreater(mid["please"], 0)

    def test_indicative_vs_counterfactual_modal_distinguished(self):
        counts_can = politeness_counts("Can you send the file?")
        counts_could = politeness_counts("Could you send the file?")
        self.assertGreater(counts_can["indicative_modal"], 0)
        self.assertEqual(counts_can["counterfactual_modal"], 0)
        self.assertGreater(counts_could["counterfactual_modal"], 0)
        self.assertEqual(counts_could["indicative_modal"], 0)

    def test_direct_wh_question_detected(self):
        counts = politeness_counts("What time works for you?")
        self.assertGreater(counts["direct_question"], 0)

    def test_by_the_way_detected_as_indirection(self):
        counts = politeness_counts("By the way, the report is ready.")
        self.assertGreater(counts["indirect_btw"], 0)

    def test_first_vs_second_person_plural_distinguished(self):
        counts = politeness_counts("We value your feedback. You should let us know.")
        self.assertGreater(counts["first_person_plural"], 0)
        self.assertGreater(counts["second_person"], 0)
        self.assertGreater(counts["second_person_start"], 0)


class NotApplicableGateTest(unittest.TestCase):
    def test_zero_fire_narrative_prose_reports_none(self):
        narrative = "The cat sat by the door. It was small and grey outside today."
        self.assertEqual(politeness_total(narrative), 0)
        self.assertIsNone(politeness_report(narrative))

    def test_any_fire_reports_a_dict(self):
        text = "Thanks for your help."
        self.assertGreater(politeness_total(text), 0)
        report = politeness_report(text)
        self.assertIsNotNone(report)
        self.assertIn("total", report)
        self.assertIn("strategies", report)
        self.assertGreater(report["total"], 0)
        self.assertTrue(all(v > 0 for v in report["strategies"].values()))


class MetricTest(unittest.TestCase):
    def test_axes_order_and_length(self):
        self.assertEqual(len(POLITENESS_METRIC.axes), 20)
        rates = POLITENESS_METRIC.extract("Thanks so much, could you please help?")
        self.assertEqual(len(rates), 20)

    def test_extract_matches_politeness_counts(self):
        text = "Hi there, thanks for your help. Could you please confirm?"
        counts = politeness_counts(text)
        rates = POLITENESS_METRIC.extract(text)
        for name, value in zip(POLITENESS_METRIC.axes, rates):
            self.assertEqual(value, float(counts[name]))


class RegistryTest(unittest.TestCase):
    def test_registered_exactly_once(self):
        from timbro.metric import register
        from timbro.politeness import _PolitenessMetric

        before = sum(1 for m in REGISTRY if m.name == "politeness")
        self.assertEqual(before, 1)
        register(_PolitenessMetric())
        register(_PolitenessMetric())
        after = sum(1 for m in REGISTRY if m.name == "politeness")
        self.assertEqual(after, 1)


class VoiceReportWiringTest(unittest.TestCase):
    def test_voice_report_includes_politeness_key(self):
        from timbro.model import VoiceModel
        from timbro.report import voice_report

        model = VoiceModel.fit([
            "The cat sat by the door. It was small and grey outside today.",
            "We went to the shop. The shop was shut, so we walked home.",
        ])
        out = voice_report(model, "The cat sat by the door.")
        self.assertIn("politeness", out)
        self.assertIsNone(out["politeness"])  # narrative draft: N/A

        out_polite = voice_report(model, "Hi, thanks so much for your help!")
        self.assertIsNotNone(out_polite["politeness"])
        self.assertGreater(out_polite["politeness"]["total"], 0)


if __name__ == "__main__":
    unittest.main()
