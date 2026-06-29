from __future__ import annotations

import unittest
from unittest.mock import patch

from timbro.rubrics import check_text


class SchimelRubricTests(unittest.TestCase):
    def test_objective_only_challenge_is_flagged(self):
        text = (
            "Climate change affects forests in many regions. This is an important problem for ecology.\n\n"
            "Our objective was to evaluate tree growth under drought treatments in potted seedlings.\n\n"
            "We measured height, mass, and leaf area over six weeks.\n\n"
            "More research is needed to understand the broader implications."
        )
        with patch("timbro.rubrics.features.DocumentView.challenge_resolution_similarity", return_value=0.1), patch(
            "timbro.rubrics.features.DocumentView.opening_resolution_similarity", return_value=0.1
        ):
            result = check_text(text)
        rules = {f.rule for f in result.findings}
        self.assertIn("objective_only_challenge", rules)
        self.assertIn("weak_resolution", rules)
        self.assertEqual(result.rubric, "schimel")

    def test_good_structure_can_pass_without_high_severity(self):
        text = (
            "Arctic soils store enough carbon to shape climate feedbacks, yet winter fluxes remain a critical problem because they are poorly constrained.\n\n"
            "We ask whether winter microbial respiration is large enough to alter annual carbon budgets.\n\n"
            "We measured winter fluxes across a temperature gradient and compared them with growing-season fluxes.\n\n"
            "These results show that winter respiration is substantial and must be included in annual Arctic carbon budgets."
        )
        with patch("timbro.rubrics.features.DocumentView.challenge_resolution_similarity", return_value=0.9), patch(
            "timbro.rubrics.features.DocumentView.opening_resolution_similarity", return_value=0.8
        ), patch("timbro.rubrics.features.DocumentView.fuzzy_verb_density", return_value=0.0), patch(
            "timbro.rubrics.features.DocumentView.nominalization_density", return_value=0.0
        ), patch("timbro.rubrics.features.DocumentView.noun_trains", return_value=0), patch(
            "timbro.rubrics.features.DocumentView.adjacent_paragraph_similarity", return_value=[0.9, 0.9, 0.9]
        ), patch("timbro.rubrics.features.DocumentView.paragraph_internal_similarity", return_value=0.9):
            result = check_text(text)
        highs = [f for f in result.findings if f.severity == "high"]
        self.assertFalse(highs)


if __name__ == "__main__":
    unittest.main()
