"""#223: the pos_SYM direction hint carries a gloss -- SYM counts %, +, € (currency
and math symbols), not punctuation -- while every other label renders unchanged."""

from __future__ import annotations

import unittest

import numpy as np

from timbro.model import VoiceModel
from timbro.report import _label


class SymGlossTests(unittest.TestCase):
    """The SYM gloss rides in the label (report.POS_LABEL), so it must appear in
    both directions and leave every other hint's wording untouched."""

    def _model(self, name: str, z: float) -> VoiceModel:
        model = VoiceModel(
            [name],
            np.array([0.0]),
            np.array([1.0]),
            np.zeros((1, 1)),
            np.array([0.81]),
            np.zeros(1),
            np.ones(1),
            np.zeros((1, 1)),
            6,
            1,
            3,
            0,
            3000,
            20,
            "ok",
            None,
            1.0,
            0.5,
            None,
        )
        model.feature_vector = lambda text: np.array([z])
        model._dist = lambda text: 1.23
        return model

    def test_sym_hint_carries_the_gloss(self):
        # Below the corpus mean the hint says "more", above it "fewer" -- the gloss
        # rides in the label, so both directions carry it (direction logic untouched).
        self.assertEqual(
            self._model("pos_SYM", -1.0).score("ignored").direction[0].hint,
            "more symbols (%, +, €: currency and math symbols; punctuation does not count)",
        )
        self.assertEqual(
            self._model("pos_SYM", 1.0).score("ignored").direction[0].hint,
            "fewer symbols (%, +, €: currency and math symbols; punctuation does not count)",
        )

    def test_non_sym_labels_render_unchanged(self):
        self.assertEqual(
            self._model("pos_NOUN", 1.0).score("ignored").direction[0].hint,
            "fewer nouns",
        )
        # PUNCT is the tag a reader confuses with SYM; it stays a bare label.
        self.assertEqual(_label("pos_PUNCT"), "punctuation")


if __name__ == "__main__":
    unittest.main()
