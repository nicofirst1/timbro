from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from timbro.cleanup import preprocess_runtime_text
from timbro.cleanup.latex import has_detex, looks_like_latex
from timbro.report import voice_report
from timbro.rewrite import evaluate_rewrite


class LatexDetectionTests(unittest.TestCase):
    def test_detects_latex_markers(self):
        self.assertTrue(looks_like_latex(r"\section{Intro}\cite{a}"))
        self.assertFalse(looks_like_latex("Plain text without TeX commands."))


@unittest.skipUnless(has_detex(), "detex is required for runtime LaTeX preprocessing tests")
class RuntimeLatexPreprocessingTests(unittest.TestCase):
    def test_preprocess_runtime_text_strips_latex(self):
        text = (
            r"\section{Introduction}" "\n"
            r"This is a short introduction.\cite{smith2020}" "\n\n"
            r"\subsection{Method}" "\n"
            r"We evaluate the approach with $x+y$."
        )
        out = preprocess_runtime_text(text)
        self.assertIn("This is a short introduction.", out)
        self.assertIn("We evaluate the approach", out)
        self.assertNotIn(r"\section", out)
        self.assertNotIn("citesmith2020", out)

    def test_preprocess_runtime_text_drops_tikz_and_label_noise(self):
        text = (
            r"\section{Framework}\label{sec:framework}" "\n"
            r"This paragraph explains the framework." "\n"
            r"\begin{tikzpicture}\node[draw] {fake figure};\end{tikzpicture}" "\n"
            r"\begin{itemize}\item First real point.\item Second real point.\end{itemize}" "\n"
            r"See Figure~\ref{fig:dimensions}."
        )
        out = preprocess_runtime_text(text)
        self.assertIn("This paragraph explains the framework.", out)
        self.assertIn("First real point.", out)
        self.assertIn("Second real point.", out)
        self.assertNotIn("tikzpicture", out)
        self.assertNotIn("sec:framework", out)
        self.assertNotIn("fig:dimensions", out)
        self.assertNotIn("itemize", out)

    def test_voice_report_scores_preprocessed_text(self):
        seen = {}

        class DummyModel:
            def score(self, text: str):
                seen["text"] = text
                return SimpleNamespace(to_dict=lambda: {"distance": 1.0, "direction": []})

            def normalized_distance(self, text: str):
                return 0.5

            def on_voice(self, text: str):
                return True

            def profile_report(self):
                return {
                    "health": "ok",
                    "warning": None,
                    "exemplars": 10,
                    "contrast": 0,
                    "words": 5000,
                    "paragraphs": 20,
                    "exemplar_floor": 1.0,
                    "exemplar_spread": 0.5,
                    "contrast_ceiling": None,
                }

            def _dist(self, text: str):
                return 1.0

        with patch("timbro.report.paragraphs", return_value=[]):
            payload = voice_report(DummyModel(), r"\section{Introduction}\nHello \cite{x}")

        self.assertEqual(payload["flow"], None)
        self.assertNotIn(r"\section", seen["text"])
        self.assertEqual(payload["distance_z"], 0.5)

    def test_evaluate_rewrite_scores_preprocessed_text(self):
        calls = []

        class DummyModel:
            def score(self, text: str):
                calls.append(text)
                return SimpleNamespace(distance=float(len(calls)))

        with patch("timbro.rewrite.preserves_content", return_value=(True, 0.99)):
            evaluate_rewrite(
                DummyModel(),
                r"\section{Introduction}\nOriginal text",
                r"\section{Introduction}\nRevised text",
            )

        self.assertEqual(len(calls), 2)
        self.assertNotIn(r"\section", calls[0])
        self.assertNotIn(r"\section", calls[1])


if __name__ == "__main__":
    unittest.main()
