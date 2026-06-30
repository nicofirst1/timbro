from __future__ import annotations

import unittest
from unittest.mock import patch

from timbro.rubrics import check_text
from timbro.rubrics.features import DocumentView


class AuditCheckTests(unittest.TestCase):
    """Deterministic checks added from the Klartext paper-writing audit + skill bans.
    Helper-level so they need no embedding model — pure regex over the DocumentView."""

    def test_caveat_closing_flagged_only_when_resolution_ends_on_a_hedge(self):
        crying = "We frame the problem.\n\nWe ask the question.\n\nWe ran the study.\n\nThe metric works, however we make no claim that it beats a reference-based score."
        clean = "We frame the problem.\n\nWe ask the question.\n\nWe ran the study.\n\nThe metric recovers the graded ordering and names which rule drives each case."
        self.assertTrue(DocumentView(crying).resolution_caveat_span())
        self.assertEqual(DocumentView(clean).resolution_caveat_span(), "")

    def test_overloaded_sentence_flags_comma_lists_and_long_runs(self):
        doc = DocumentView(
            "The metric is reference-free, German, plain-language, rule-diagnostic, and interpretable, "
            "and it tracks ordinal levels, agrees with formulas, names rules, and needs no parallel corpus."
        )
        longs = doc.long_sentences()
        self.assertTrue(longs)
        self.assertGreaterEqual(longs[0][2], 4)  # >= 4 commas

    def test_coy_predicate_detected(self):
        self.assertTrue(DocumentView("The key is that no reference text is required.").coy_predicates())
        self.assertFalse(DocumentView("No reference text is required.").coy_predicates())

    def test_number_ladder_flags_a_stats_dense_paragraph(self):
        ladder = "Per band the means were 0.81, 0.74, 0.68, 0.61, 0.55, and 0.49 with a 12% spread."
        prose = "The score separates simplified text from its source across every band we tested."
        self.assertIsNotNone(DocumentView(ladder).number_dense_paragraph())
        self.assertIsNone(DocumentView(prose).number_dense_paragraph())

    def test_appositive_colon_splice_detected(self):
        self.assertTrue(DocumentView("The rule engine does more than grade: it also drives the generator.").appositive_colon_spans())
        self.assertFalse(DocumentView("We test three corpora: APA, capito, and DEplain.").appositive_colon_spans())

    def test_orphan_pronoun_opener_detected(self):
        self.assertTrue(DocumentView("This shows the metric works across registers.").orphan_pronoun_spans())
        self.assertFalse(DocumentView("This measurement shows the metric works across registers.").orphan_pronoun_spans())

    def test_overclaim_words_surfaced_but_not_polysemous_ones(self):
        self.assertTrue(DocumentView("Our metric proves that it outperforms every baseline.").overclaim_words())
        self.assertFalse(DocumentView("This is the first sentence and the result is significant in context.").overclaim_words())

    def test_deadwood_detected(self):
        self.assertTrue(DocumentView("It is important to note that the score may possibly help.").deadwood_spans())

    def test_latinate_diction_suggests_plain_word(self):
        out = DocumentView("We utilize the methodology to obtain numerous results.").latinate_words()
        self.assertTrue(out)
        self.assertTrue(any("→ use" in s for s in out))
        self.assertFalse(DocumentView("We use the method to get many results.").latinate_words())

    def test_passive_voice_counted(self):
        self.assertGreater(DocumentView("The results were analyzed by the team.").passive_clauses(), 0)
        self.assertEqual(DocumentView("The team analyzed the results.").passive_clauses(), 0)

    def test_latinate_is_a_rule_not_just_a_list(self):
        # a long Latinate word absent from the suggestion map is still caught (generative)
        self.assertTrue(DocumentView("The phenomenon was incomprehensible.").latinate_words())
        # nominalizations are the nominalization check's job, not double-flagged here
        self.assertFalse(any("evaluation" in s for s in DocumentView("The evaluation succeeded.").latinate_words()))

    def test_comma_splice_detected(self):
        self.assertTrue(DocumentView("The metric separates simplified text from its source, no single signal wins everywhere.").comma_splice_spans())
        # a subordinate clause after the comma is legal, not a splice
        self.assertFalse(DocumentView("The metric separates the text, although no single signal wins.").comma_splice_spans())
        # a comma list is not a splice
        self.assertFalse(DocumentView("We test three corpora, two registers, and one baseline.").comma_splice_spans())


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
