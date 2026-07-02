from __future__ import annotations

import unittest
from unittest.mock import patch

from timbro.rubrics import check_text
from timbro.rubrics.base import RubricFinding
from timbro.rubrics.features import DocumentView
from timbro.rubrics.report import build_result
from timbro.rubrics.rules import MAX_FINDINGS_PER_RULE, schimel_findings


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
        self.assertTrue(
            DocumentView(
                "The key is that no reference text is required."
            ).coy_predicates()
        )
        self.assertFalse(
            DocumentView("No reference text is required.").coy_predicates()
        )

    def test_number_ladder_flags_a_stats_dense_paragraph(self):
        ladder = "Per band the means were 0.81, 0.74, 0.68, 0.61, 0.55, and 0.49 with a 12% spread."
        prose = "The score separates simplified text from its source across every band we tested."
        self.assertTrue(DocumentView(ladder).number_dense_paragraph())
        self.assertFalse(DocumentView(prose).number_dense_paragraph())

    def test_appositive_colon_splice_detected(self):
        self.assertTrue(
            DocumentView(
                "The rule engine does more than grade: it also drives the generator."
            ).appositive_colon_spans()
        )
        self.assertFalse(
            DocumentView(
                "We test three corpora: APA, capito, and DEplain."
            ).appositive_colon_spans()
        )

    def test_orphan_pronoun_opener_detected(self):
        self.assertTrue(
            DocumentView(
                "This shows the metric works across registers."
            ).orphan_pronoun_spans()
        )
        self.assertFalse(
            DocumentView(
                "This measurement shows the metric works across registers."
            ).orphan_pronoun_spans()
        )

    def test_overclaim_words_surfaced_but_not_polysemous_ones(self):
        self.assertTrue(
            DocumentView(
                "Our metric proves that it outperforms every baseline."
            ).overclaim_words()
        )
        self.assertFalse(
            DocumentView(
                "This is the first sentence and the result is significant in context."
            ).overclaim_words()
        )

    def test_deadwood_detected(self):
        self.assertTrue(
            DocumentView(
                "It is important to note that the score may possibly help."
            ).deadwood_spans()
        )

    def test_latinate_diction_suggests_plain_word(self):
        out = DocumentView(
            "We utilize the methodology to obtain numerous results."
        ).latinate_words()
        self.assertTrue(out)
        self.assertTrue(any("→ use" in span for _, _, span in out))
        self.assertFalse(
            DocumentView("We use the method to get many results.").latinate_words()
        )

    def test_passive_voice_counted(self):
        self.assertGreater(
            DocumentView("The results were analyzed by the team.").passive_clauses(), 0
        )
        self.assertEqual(
            DocumentView("The team analyzed the results.").passive_clauses(), 0
        )

    def test_latinate_is_a_rule_not_just_a_list(self):
        # a long Latinate word absent from the suggestion map is still caught (generative)
        self.assertTrue(
            DocumentView("The phenomenon was incomprehensible.").latinate_words()
        )
        # nominalizations are the nominalization check's job, not double-flagged here
        self.assertFalse(
            any(
                "evaluation" in span
                for _, _, span in DocumentView("The evaluation succeeded.").latinate_words()
            )
        )

    def test_comma_splice_detected(self):
        self.assertTrue(
            DocumentView(
                "The metric separates simplified text from its source, no single signal wins everywhere."
            ).comma_splice_spans()
        )
        # a subordinate clause after the comma is legal, not a splice
        self.assertFalse(
            DocumentView(
                "The metric separates the text, although no single signal wins."
            ).comma_splice_spans()
        )
        # a comma list is not a splice
        self.assertFalse(
            DocumentView(
                "We test three corpora, two registers, and one baseline."
            ).comma_splice_spans()
        )

    def test_repetition_burst_detected(self):
        # "reference" echoed three times in one span -> caught; generalizes over lemmas
        echo = DocumentView(
            "The axes are reference-free readability, reference-based overlap, and reference-free meaning."
        )
        self.assertTrue(echo.repetition_bursts())
        clean = DocumentView(
            "The axes are readability, lexical overlap, and preserved meaning."
        )
        self.assertFalse(clean.repetition_bursts())

    def test_repetition_burst_is_lemma_based_not_a_word_list(self):
        # plural/singular collapse to one lemma, so the echo still trips (no hard-coded word)
        self.assertTrue(
            DocumentView(
                "Each rule scores a rule, and the rule set aggregates every rule score."
            ).repetition_bursts()
        )

    def test_defensive_claim_detected(self):
        self.assertTrue(
            DocumentView(
                "We do not claim the rules exhaustively span simplicity."
            ).defensive_claims()
        )
        self.assertTrue(
            DocumentView(
                "We make no meaning-superiority claim here."
            ).defensive_claims()
        )
        self.assertFalse(
            DocumentView(
                "The rules recover the graded ordering and name each broken rule."
            ).defensive_claims()
        )

    def test_verbless_sentence_detected(self):
        self.assertTrue(
            DocumentView(
                "A reference-free simplicity score across more German corpora than prior work."
            ).verbless_sentences()
        )
        self.assertFalse(
            DocumentView(
                "The score generalises across more German corpora than prior work."
            ).verbless_sentences()
        )

    def test_buried_verb_core_detected(self):
        buried = DocumentView(
            "The score, which aggregates twenty calibrated rules weighted by how much of the document each rule sees, is reference-free."
        ).buried_verb_spans()
        self.assertTrue(buried)
        self.assertFalse(
            DocumentView("The score is reference-free.").buried_verb_spans()
        )

    def test_citation_as_subject_detected(self):
        self.assertTrue(
            DocumentView(
                "Smith (2003) found that scores rose."
            ).citation_subject_spans()
        )
        self.assertTrue(
            DocumentView(
                r"\citet{smith2003} showed the effect."
            ).citation_subject_spans()
        )
        # parenthetical citation is fine — not a subject
        self.assertFalse(
            DocumentView(
                "Scores rose after simplification (Smith 2003)."
            ).citation_subject_spans()
        )

    def test_expletive_opening_detected(self):
        self.assertTrue(
            DocumentView("There is a clear effect on readability.").expletive_openings()
        )
        self.assertFalse(
            DocumentView("The effect on readability is clear.").expletive_openings()
        )

    def test_significance_without_magnitude_detected(self):
        self.assertTrue(
            DocumentView(
                "The rules significantly separated the registers."
            ).significance_without_magnitude()
        )
        # a magnitude in view clears it
        self.assertFalse(
            DocumentView(
                "The rules raised the score by 18% (significantly)."
            ).significance_without_magnitude()
        )

    def test_preposition_chain_detected(self):
        self.assertTrue(
            DocumentView(
                "It is the mean of the weights of the rules of the corpus."
            ).preposition_chains()
        )
        self.assertFalse(
            DocumentView(
                "It is the weighted mean over the calibrated rules."
            ).preposition_chains()
        )

    def test_metadiscourse_frame_detected(self):
        self.assertTrue(
            DocumentView(
                "We found that the metric tracks difficulty."
            ).metadiscourse_frames()
        )
        self.assertFalse(
            DocumentView("The metric tracks difficulty.").metadiscourse_frames()
        )

    def test_inconsistent_terminology_needs_the_model(self):
        # E is the one audit check that uses the semantic embedder; skip if it is unavailable.
        try:
            out = DocumentView(
                "The composite score aggregates the rules. The composite is calibrated. "
                "We report the combined score per band. The combined number is calibrated too. "
                "The combined score and the composite score both track difficulty."
            ).inconsistent_terms(min_count=2)
        except OSError as e:  # pragma: no cover
            self.skipTest(f"embedding model unavailable: {e}")
        self.assertIsInstance(out, list)


class SchimelRubricTests(unittest.TestCase):
    def test_objective_only_challenge_is_flagged(self):
        text = (
            "Climate change affects forests in many regions. This is an important problem for ecology.\n\n"
            "Our objective was to evaluate tree growth under drought treatments in potted seedlings.\n\n"
            "We measured height, mass, and leaf area over six weeks.\n\n"
            "More research is needed to understand the broader implications."
        )
        with (
            patch(
                "timbro.rubrics.features.DocumentView.challenge_resolution_similarity",
                return_value=0.1,
            ),
            patch(
                "timbro.rubrics.features.DocumentView.opening_resolution_similarity",
                return_value=0.1,
            ),
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
        with (
            patch(
                "timbro.rubrics.features.DocumentView.challenge_resolution_similarity",
                return_value=0.9,
            ),
            patch(
                "timbro.rubrics.features.DocumentView.opening_resolution_similarity",
                return_value=0.8,
            ),
            patch(
                "timbro.rubrics.features.DocumentView.fuzzy_verb_density",
                return_value=0.0,
            ),
            patch(
                "timbro.rubrics.features.DocumentView.nominalization_density",
                return_value=0.0,
            ),
            patch("timbro.rubrics.features.DocumentView.noun_trains", return_value=0),
            patch(
                "timbro.rubrics.features.DocumentView.adjacent_paragraph_similarity",
                return_value=[0.9, 0.9, 0.9],
            ),
            patch(
                "timbro.rubrics.features.DocumentView.paragraph_internal_similarity",
                return_value=0.9,
            ),
        ):
            result = check_text(text)
        highs = [f for f in result.findings if f.severity == "high"]
        self.assertFalse(highs)


class RecallFirstFindingsTests(unittest.TestCase):
    """M1 (#1): every span-producing rule reports one finding per occurrence, capped at
    MAX_FINDINGS_PER_RULE, each locatable; the per-rule penalty stays flat regardless of
    occurrence count."""

    SPLICE = "The metric separates simplified text from its source, no single signal wins everywhere."

    def test_comma_splice_multiple_occurrences_capped_and_locatable(self):
        text = "\n\n".join([self.SPLICE] * (MAX_FINDINGS_PER_RULE + 2))
        findings = schimel_findings(DocumentView(text))
        splices = [f for f in findings if f.rule == "comma_splice"]
        self.assertEqual(len(splices), MAX_FINDINGS_PER_RULE)
        for f in splices:
            self.assertIsNotNone(f.paragraph)
            self.assertIsNotNone(f.sentence)

    def test_comma_splice_finding_count_matches_occurrence_count_below_cap(self):
        n = 3
        text = "\n\n".join([self.SPLICE] * n)
        findings = schimel_findings(DocumentView(text))
        splices = [f for f in findings if f.rule == "comma_splice"]
        self.assertEqual(len(splices), n)

    def test_penalty_applied_once_per_rule_not_per_occurrence(self):
        one = [
            RubricFinding("medium", "sentences", "comma_splice", 1, 1, "x", "msg"),
        ]
        many = [
            RubricFinding("medium", "sentences", "comma_splice", i, 1, "x", "msg")
            for i in range(1, 11)
        ]
        result_one = build_result(rubric="schimel", version="v3", sections={}, findings=one)
        result_many = build_result(rubric="schimel", version="v3", sections={}, findings=many)
        self.assertEqual(result_one.dimensions["sentences"], result_many.dimensions["sentences"])
        self.assertEqual(result_one.overall, result_many.overall)

    def test_point_nowhere_paragraph_no_break_reports_multiple(self):
        # Three independent, weakly-connected 3+ sentence paragraphs — the pre-fix code
        # `break`-ed after the first match; it must now report all of them.
        para = (
            "Solar flux varies by latitude. Coffee prices rose in March. "
            "The bridge needs new bolts."
        )
        text = "\n\n".join([para] * 3)
        with patch(
            "timbro.rubrics.features.DocumentView.paragraph_internal_similarity",
            return_value=0.0,
        ):
            findings = schimel_findings(DocumentView(text))
        nowhere = [f for f in findings if f.rule == "point_nowhere_paragraph"]
        self.assertEqual(len(nowhere), 3)


class LoosenedThresholdBandTests(unittest.TestCase):
    """M1 (#2): two-band thresholds — the newly opened band fires at low, the old band
    keeps its previous severity. Severity is the confidence signal, not the gate."""

    TEXT = "We frame the problem here.\n\nWe answer the question here."

    def _severities(self, text: str, rule: str) -> list[str]:
        return [f.severity for f in schimel_findings(DocumentView(text)) if f.rule == rule]

    def test_fuzzy_verb_density_low_band_above_4(self):
        with patch(
            "timbro.rubrics.features.DocumentView.fuzzy_verb_density", return_value=5.0
        ):
            self.assertEqual(self._severities(self.TEXT, "fuzzy_verb_density"), ["low"])

    def test_fuzzy_verb_density_medium_band_above_6(self):
        with patch(
            "timbro.rubrics.features.DocumentView.fuzzy_verb_density", return_value=7.0
        ):
            self.assertEqual(self._severities(self.TEXT, "fuzzy_verb_density"), ["medium"])

    def test_fuzzy_verb_density_silent_at_or_below_4(self):
        with patch(
            "timbro.rubrics.features.DocumentView.fuzzy_verb_density", return_value=4.0
        ):
            self.assertEqual(self._severities(self.TEXT, "fuzzy_verb_density"), [])

    def test_nominalization_density_low_band_above_25(self):
        with patch(
            "timbro.rubrics.features.DocumentView.nominalization_density",
            return_value=30.0,
        ):
            self.assertEqual(self._severities(self.TEXT, "nominalization_density"), ["low"])

    def test_nominalization_density_medium_band_above_35(self):
        with patch(
            "timbro.rubrics.features.DocumentView.nominalization_density",
            return_value=40.0,
        ):
            self.assertEqual(
                self._severities(self.TEXT, "nominalization_density"), ["medium"]
            )

    def test_nominalization_density_silent_at_or_below_25(self):
        with patch(
            "timbro.rubrics.features.DocumentView.nominalization_density",
            return_value=25.0,
        ):
            self.assertEqual(self._severities(self.TEXT, "nominalization_density"), [])

    def test_paragraph_drift_low_band_between_025_and_035(self):
        with patch(
            "timbro.rubrics.features.DocumentView.adjacent_paragraph_similarity",
            return_value=[0.30],
        ):
            self.assertEqual(self._severities(self.TEXT, "paragraph_drift"), ["low"])

    def test_paragraph_drift_medium_band_below_025(self):
        with patch(
            "timbro.rubrics.features.DocumentView.adjacent_paragraph_similarity",
            return_value=[0.20],
        ):
            self.assertEqual(self._severities(self.TEXT, "paragraph_drift"), ["medium"])

    def test_paragraph_drift_silent_at_or_above_035(self):
        with patch(
            "timbro.rubrics.features.DocumentView.adjacent_paragraph_similarity",
            return_value=[0.35],
        ):
            self.assertEqual(self._severities(self.TEXT, "paragraph_drift"), [])

    def test_passive_voice_fires_above_20_percent(self):
        # 10 sentences, 3 passives: 3 > max(2, 0.20 * 10) fires under the new band,
        # but 3 > max(2, 0.33 * 10) would not have fired under the old 33% gate.
        text = " ".join(["The team analyzed the results."] * 10)
        doc = DocumentView(text)
        self.assertEqual(sum(len(s) for s in doc.sentences), 10)
        with patch(
            "timbro.rubrics.features.DocumentView.passive_clauses", return_value=3
        ):
            severities = [
                f.severity
                for f in schimel_findings(DocumentView(text))
                if f.rule == "passive_voice"
            ]
        self.assertEqual(severities, ["low"])

    def test_passive_voice_silent_at_or_below_20_percent(self):
        text = " ".join(["The team analyzed the results."] * 10)
        with patch(
            "timbro.rubrics.features.DocumentView.passive_clauses", return_value=2
        ):
            severities = [
                f.severity
                for f in schimel_findings(DocumentView(text))
                if f.rule == "passive_voice"
            ]
        self.assertEqual(severities, [])


class LeadingWordAnnotationTests(unittest.TestCase):
    """#6: word_repetition / inconsistent_terminology findings get an extra note when the
    flagged word is also a detected leading word (#4). The flag still fires either way —
    annotate, never suppress."""

    _LEITWORT_NOTE = "possibly a deliberate leading word"

    REPETITION_TEXT = (
        "The axes are reference-free readability, reference-based overlap, "
        "and reference-free meaning."
    )
    TERMINOLOGY_TEXT = (
        "The composite score aggregates the rules. The composite is calibrated. "
        "We report the combined score per band. The combined number is calibrated too. "
        "The combined score and the composite score both track difficulty."
    )

    def test_word_repetition_annotated_when_flagged_word_is_a_leading_word(self):
        doc = DocumentView(self.REPETITION_TEXT)
        occurrences = doc.repetition_bursts()
        self.assertTrue(occurrences)
        flagged_lemma = occurrences[0][3]
        with patch.object(
            DocumentView,
            "leading_words",
            [{"lemma": flagged_lemma, "count": 8, "score": 2.0, "paragraphs": [0]}],
        ):
            findings = [
                f for f in schimel_findings(doc) if f.rule == "word_repetition"
            ]
        self.assertTrue(findings)
        self.assertIn(self._LEITWORT_NOTE, findings[0].message)

    def test_word_repetition_plain_message_when_not_a_leading_word(self):
        # Short document — leading_words() naturally returns [] (under the 300-token
        # floor), so the flagged word is never a leading word here.
        doc = DocumentView(self.REPETITION_TEXT)
        self.assertEqual(doc.leading_words, [])
        findings = [f for f in schimel_findings(doc) if f.rule == "word_repetition"]
        self.assertTrue(findings)
        for f in findings:
            self.assertNotIn(self._LEITWORT_NOTE, f.message)
            self.assertTrue(
                f.message.endswith(
                    "(Schimel: repetition should be deliberate, not accidental)."
                )
            )

    def test_inconsistent_terminology_annotated_when_a_term_is_a_leading_word(self):
        try:
            doc = DocumentView(self.TERMINOLOGY_TEXT)
            pairs = doc.inconsistent_terms(min_count=2)
        except OSError as e:  # pragma: no cover
            self.skipTest(f"embedding model unavailable: {e}")
        if not pairs:
            self.skipTest("no near-synonym pair found for this fixture")
        flagged_lemma = pairs[0][0]
        with patch.object(
            DocumentView,
            "leading_words",
            [{"lemma": flagged_lemma, "count": 8, "score": 2.0, "paragraphs": [0]}],
        ), patch.object(DocumentView, "inconsistent_terms", return_value=pairs):
            findings = [
                f
                for f in schimel_findings(doc)
                if f.rule == "inconsistent_terminology"
            ]
        self.assertTrue(findings)
        self.assertIn(self._LEITWORT_NOTE, findings[0].message)

    def test_inconsistent_terminology_plain_message_when_not_a_leading_word(self):
        try:
            doc = DocumentView(self.TERMINOLOGY_TEXT)
            self.assertEqual(doc.leading_words, [])
            findings = [
                f
                for f in schimel_findings(doc)
                if f.rule == "inconsistent_terminology"
            ]
        except OSError as e:  # pragma: no cover
            self.skipTest(f"embedding model unavailable: {e}")
        for f in findings:
            self.assertNotIn(self._LEITWORT_NOTE, f.message)
            self.assertTrue(
                f.message.endswith("propagate it through the whole manuscript.")
            )

    def test_no_finding_is_dropped_by_annotation(self):
        # Same occurrence counts as doc.repetition_bursts()/inconsistent_terms() report,
        # with or without a leading-word match — annotation only enriches the message.
        doc = DocumentView(self.REPETITION_TEXT)
        occurrences = doc.repetition_bursts()
        findings = [f for f in schimel_findings(doc) if f.rule == "word_repetition"]
        self.assertEqual(len(findings), len(occurrences[:MAX_FINDINGS_PER_RULE]))


if __name__ == "__main__":
    unittest.main()
