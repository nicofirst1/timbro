"""flow_report must reject short input with ValueError, not numpy crashes (#164).

flow_report is exported in timbro.__all__, but on short input it crashed with
raw numpy exceptions (RuntimeWarnings printed first):
  - one paragraph of 15+ words: IndexError, because novelty_curve is empty and
    nov[-1] fails on it;
  - under 15 words in total (paragraphs() returns []): numpy AxisError from
    norm(..., axis=1) on an empty embedding matrix.

The guard lives at the top of flow_report: fewer than 2 paragraphs of 15+ words
raises ValueError. The CLI's separate 4-paragraph gate in report.py is untouched
(it keeps emitting flow: null before flow_report is ever called).
"""
from __future__ import annotations

import math
import unittest
import warnings

from timbro.flow import flow_report


class FlowReportShortInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Warm the embedder outside the warnings scope below, so on the unfixed
        # base the guarded calls fail on the numpy crash, not on third-party
        # import-time warnings turned errors.
        from timbro.text import _model

        _model()

    def _assert_value_error(self, text: str, got: int):
        with warnings.catch_warnings():
            warnings.simplefilter("error")  # any RuntimeWarning must fail the test
            with self.assertRaises(ValueError) as cm:
                flow_report(text)
        self.assertEqual(
            str(cm.exception),
            f"flow_report needs at least 2 paragraphs of 15+ words, got {got}",
        )

    def test_one_paragraph_raises_value_error_without_runtime_warning(self):
        self._assert_value_error(
            "The quick brown fox jumps over the lazy dog near the river bank every single morning.",
            got=1,
        )

    def test_five_word_text_raises_value_error_without_runtime_warning(self):
        self._assert_value_error("one two three four five", got=0)

    def test_two_paragraphs_still_returns_finite_flow_report(self):
        text = (
            "The quick brown fox jumps over the lazy dog near the river bank every single morning.\n\n"
            "A quiet gray cat watches from the garden fence and never moves until the sun goes down."
        )
        fields = flow_report(text).to_dict()
        self.assertEqual(
            set(fields),
            {"speed", "volume", "circuitousness", "terminal_initial_ratio", "circle_back", "coherence"},
        )
        for name, value in fields.items():
            self.assertTrue(math.isfinite(value), f"{name} is not finite: {value!r}")


if __name__ == "__main__":
    unittest.main()
