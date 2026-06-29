from __future__ import annotations

import unittest

import numpy as np

from timbro.core import VoiceModel


class ScoringPolicyTests(unittest.TestCase):
    def _model(self, *, health: str = "ok", conf_pos: float = 0.3) -> VoiceModel:
        model = VoiceModel(
            ["tell_diction", "pos_NOUN"],
            np.array([1.0, 1.0]),
            np.array([1.0, 1.0]),
            np.zeros((2, 2)),
            np.array([0.81, conf_pos]),
            np.zeros(1),
            np.ones(1),
            np.zeros((2, 1)),
            6,
            1,
            3,
            0,
            3000,
            20,
            health,
            None if health == "ok" else "warning",
            1.0,
            0.5,
            None,
        )
        model.feature_vector = lambda text: np.array([0.5, 2.0])  # tell below mean, nouns above mean
        model._dist = lambda text: 1.23
        return model

    def test_ai_tells_never_suggest_more(self):
        result = self._model().score("ignored")
        hints = [move.hint for move in result.direction]
        self.assertEqual(hints, ["fewer nouns"])

    def test_low_confidence_hints_are_hidden(self):
        result = self._model(conf_pos=0.10).score("ignored")
        self.assertEqual(result.direction, [])

    def test_insufficient_profiles_suppress_direction(self):
        result = self._model(health="insufficient").score("ignored")
        self.assertEqual(result.direction, [])


if __name__ == "__main__":
    unittest.main()
