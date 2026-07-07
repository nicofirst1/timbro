from __future__ import annotations

import unittest
from types import SimpleNamespace

from timbro.model import FeatureMove
from timbro.report import voice_report


class ReportAttributionTests(unittest.TestCase):
    def test_spans_include_local_direction_and_top_sentence(self):
        class DummyModel:
            def score(self, text: str):
                hint = "fewer pronouns" if "we" in text.lower() else "more nouns"
                move = FeatureMove("pos_PRON", 1.0, -1.0, 0.9, hint)
                return SimpleNamespace(to_dict=lambda: {"distance": 2.0, "direction": [move.to_dict()]}, direction=[move])

            def normalized_distance(self, text: str):
                return 0.5 if "we" in text.lower() else 0.2

            def on_voice(self, text: str):
                return False

            def profile_report(self):
                return {
                    "health": "ok",
                    "warning": None,
                    "exemplars": 10,
                    "contrast": 3,
                    "words": 5000,
                    "paragraphs": 20,
                    "exemplar_floor": 1.0,
                    "exemplar_spread": 0.5,
                    "contrast_ceiling": 4.0,
                }

            def _dist(self, text: str):
                return 4.0 if "we" in text.lower() else 1.0

        text = (
            "We explain the approach in detail for the broader evaluation setting. We also mention why it is limited for several realistic deployment cases.\n\n"
            "The method section is compact and concrete for the target audience. It names the variables clearly and avoids unnecessary jargon throughout."
        )
        payload = voice_report(DummyModel(), text)
        self.assertTrue(payload["spans"])
        top = payload["spans"][0]
        self.assertEqual(top["index"], 1)
        self.assertEqual(top["direction"][0]["hint"], "fewer pronouns")
        self.assertIsNotNone(top["sentence"])
        self.assertEqual(top["sentence"]["direction"][0]["hint"], "fewer pronouns")


if __name__ == "__main__":
    unittest.main()
