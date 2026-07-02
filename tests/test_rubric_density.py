from __future__ import annotations

import unittest

from timbro.rubrics import check_text
from timbro.rubrics.density.checks import density_findings
from timbro.rubrics.features import DocumentView

# Neutral filler with no repeated content lemmas of its own, used to pad paragraphs past
# the leading-word detector's 300-alphabetic-token document-length floor (mirrors
# tests/test_leading_words.py's fixture so leading_words behaves the same way here).
_FILLER = (
    "The quiet river carried old stories past distant hills while travelers gathered "
    "near the market discussing harvest plans and forgotten songs from earlier winters."
)


def _paragraph(min_words: int = 30) -> str:
    words: list[str] = []
    while len(words) < min_words:
        words.extend(_FILLER.split())
    return " ".join(words)


def _insert_mid(paragraph: str, insertion: str) -> str:
    words = paragraph.split()
    mid = len(words) // 2
    return " ".join(words[:mid] + insertion.split() + words[mid:])


class PaddingParagraphTests(unittest.TestCase):
    """padding_paragraph (#5): paragraph content-word ratio trailing the document mean."""

    def test_filler_heavy_paragraph_is_flagged(self):
        content_rich = (
            "Researchers measured soil carbon, tracked microbial diversity, mapped root "
            "density, and compared drought resistance across twelve distinct field plots "
            "planted with native perennial grasses under controlled irrigation schedules "
            "while recording detailed seasonal temperature and rainfall patterns."
        )
        # Function-word heavy: pronouns/auxiliaries/prepositions dominate, almost no
        # NOUN/PROPN/VERB/ADJ/ADV tokens survive the content-POS filter.
        padding = (
            "It is that it was, and so it is that it was there, and so it is that it "
            "will be so, and thus it is what it is, and so it goes, and it was that way."
        )
        doc = DocumentView(f"{content_rich}\n\n{content_rich}\n\n{padding}")

        findings = density_findings(doc)
        padding_findings = [f for f in findings if f.rule == "padding_paragraph"]
        self.assertTrue(padding_findings)
        self.assertEqual(padding_findings[0].paragraph, 3)  # 1-based
        self.assertEqual(padding_findings[0].dimension, "density")
        self.assertEqual(padding_findings[0].severity, "low")

    def test_uniformly_dense_document_is_not_flagged(self):
        content_rich = (
            "Researchers measured soil carbon, tracked microbial diversity, mapped root "
            "density, and compared drought resistance across twelve distinct field plots "
            "planted with native perennial grasses under controlled irrigation schedules "
            "while recording detailed seasonal temperature and rainfall patterns."
        )
        doc = DocumentView(f"{content_rich}\n\n{content_rich}\n\n{content_rich}")

        findings = density_findings(doc)
        self.assertFalse([f for f in findings if f.rule == "padding_paragraph"])


class JargonClusterTests(unittest.TestCase):
    """jargon_cluster (#5): rare (low-zipf, non-PROPN, non-leading-word, non-acronym)
    terms clustered >= 3-deep in one sentence."""

    def test_sentence_with_three_rare_terms_is_flagged(self):
        paragraphs = [_paragraph(30) for _ in range(20)]
        paragraphs.append(
            "The quorbin flarnix worbash proposal combined several distinct approaches "
            "for the broader analysis of the site."
        )
        doc = DocumentView("\n\n".join(paragraphs))

        findings = density_findings(doc)
        jargon = [f for f in findings if f.rule == "jargon_cluster"]
        self.assertTrue(jargon)
        self.assertEqual(jargon[0].dimension, "jargon")
        self.assertEqual(jargon[0].severity, "medium")
        for w in ("quorbin", "flarnix", "worbash"):
            self.assertIn(w, jargon[0].span)

    def test_leading_word_is_exempted_from_the_rare_word_count(self):
        # Cluster "isotherm" into two adjacent paragraphs (9, 10) exactly like
        # tests/test_leading_words.py does, so it qualifies as a leading word (#4). Real,
        # dictionary-rare words (not invented strings) so spaCy's POS tagger sees the same
        # context it was trained on and doesn't mistag a run of OOV tokens as a name.
        paragraphs = [_paragraph(30) for _ in range(20)]
        paragraphs[9] = _insert_mid(paragraphs[9], "isotherm isotherm isotherm isotherm")
        paragraphs[10] = _insert_mid(
            paragraphs[10], "isotherm isotherm isotherm isotherm"
        )
        # One more occurrence, in its own sentence alongside two other rare terms. Without
        # the leading-word exemption this sentence has 3 rare terms (still fires); with
        # the exemption "isotherm" itself must not appear in the reported span, leaving
        # only 2 rare terms — below the >= 3 threshold, so no jargon_cluster finding at all
        # for this sentence.
        paragraphs.append(
            "The analysis combined isotherm mapping, phloem sampling, and peduncle "
            "measurements across the broader site survey."
        )
        doc = DocumentView("\n\n".join(paragraphs))

        self.assertIn("isotherm", {w["lemma"] for w in doc.leading_words})

        findings = density_findings(doc)
        jargon = [f for f in findings if f.rule == "jargon_cluster"]
        matches = [f for f in jargon if "phloem" in f.span]
        self.assertFalse(matches, "leading word exemption should drop this below the >= 3 threshold")


class DensityRubricTests(unittest.TestCase):
    def test_check_text_routes_to_density_rubric_and_leaves_schimel_unchanged(self):
        text = "The quiet river carried old stories past distant hills.\n\nTravelers gathered near the market."
        result = check_text(text, rubric="density")
        self.assertEqual(result.rubric, "density")
        self.assertEqual(set(result.dimensions), {"density", "jargon"})
        self.assertIn(result.verdict, {"pass", "warn", "fail"})

        schimel_result = check_text(text, rubric="schimel")
        self.assertEqual(schimel_result.rubric, "schimel")


if __name__ == "__main__":
    unittest.main()
