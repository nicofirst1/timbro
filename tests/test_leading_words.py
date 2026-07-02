from __future__ import annotations

import unittest

from timbro.rubrics.features import DocumentView

# Neutral filler with no repeated content lemmas of its own, used to pad paragraphs past
# the detector's 300-alphabetic-token document-length floor.
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


class LeadingWordsTests(unittest.TestCase):
    """Leitwort detector (#4): gap-burstiness (CV of inter-occurrence gaps) over a
    single document, no reference corpus."""

    def test_short_document_returns_empty(self):
        self.assertEqual(DocumentView("Too short to count.").leading_words, [])

    def test_word_clustered_in_two_adjacent_paragraphs_is_detected(self):
        # 20-paragraph doc; "beacon" appears 8x, bunched in the middle of paragraphs
        # 9 and 10 (adjacent) with a long stretch of unrelated filler between the two
        # bunches — small intra-bunch gaps + one large inter-bunch gap => high CV.
        paragraphs = [_paragraph(30) for _ in range(20)]
        paragraphs[9] = _insert_mid(paragraphs[9], "beacon beacon beacon beacon")
        paragraphs[10] = _insert_mid(paragraphs[10], "beacon beacon beacon beacon")
        doc = DocumentView("\n\n".join(paragraphs))

        results = {r["lemma"]: r for r in doc.leading_words}
        self.assertIn("beacon", results)
        beacon = results["beacon"]
        self.assertEqual(beacon["count"], 8)
        self.assertGreaterEqual(beacon["score"], 1.3)
        self.assertEqual(beacon["paragraphs"], [9, 10])

    def test_word_spread_evenly_across_document_is_not_detected(self):
        # Same total count (8), but one occurrence per paragraph at the same relative
        # offset across 8 evenly-spaced paragraphs of equal length => near-zero CV.
        paragraphs = [_paragraph(30) for _ in range(20)]
        for i in (0, 2, 4, 6, 8, 10, 12, 14):
            paragraphs[i] = _insert_mid(paragraphs[i], "lantern")
        doc = DocumentView("\n\n".join(paragraphs))

        lemmas = {r["lemma"] for r in doc.leading_words}
        self.assertNotIn("lantern", lemmas)

    def test_results_sorted_desc_and_capped_at_ten(self):
        paragraphs = [_paragraph(40) for _ in range(20)]
        # 15 distinct nonsense words, each clustered into two adjacent paragraphs like
        # "beacon" above, to push well past the 10-result cap.
        nonsense_words = [
            "zelverin",
            "quorbin",
            "flarnix",
            "brentol",
            "shovane",
            "grintel",
            "worbash",
            "clenvor",
            "dravost",
            "meltune",
            "trebond",
            "yulmark",
            "prasine",
            "nokvane",
            "sildrup",
        ]
        for n, word in enumerate(nonsense_words):
            a = (2 * n) % 18
            paragraphs[a] = _insert_mid(paragraphs[a], " ".join([word] * 4))
            paragraphs[a + 1] = _insert_mid(paragraphs[a + 1], " ".join([word] * 4))
        doc = DocumentView("\n\n".join(paragraphs))

        results = doc.leading_words
        self.assertLessEqual(len(results), 10)
        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))


if __name__ == "__main__":
    unittest.main()
