"""One shared parse and one shared encode per `check_text` call (#192).

Before #192, every rubric built its own `DocumentView`, so the spaCy parser ran
over every paragraph twice (schimel + density), and `paragraph_internal_similarity`
encoded each paragraph's sentences in its own MiniLM call. `check_text` now builds
one view per call, `DocumentView` parses paragraphs in one batched `nlp.pipe`
call, and the sentence encodes are batched once and split back per paragraph.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import numpy as np

from timbro.rubrics import check_text
from timbro.rubrics import features
from timbro.rubrics.density import DensityRubric
from timbro.rubrics.features import DocumentView
from timbro.rubrics.schimel import SchimelRubric
from timbro.text import cosine

_TEXT = (
    "We frame the problem: writing checks fail quietly on real prose, and users "
    "stop trusting the report. The parser runs over every paragraph once per "
    "rubric today, which doubles the cost of the whole command.\n\n"
    "We ask whether a semantic check earns its first-class tier, and the question "
    "remains unclear without a labelled corpus. Dumb baselines sit next to it so "
    "the decision becomes a measurement instead of a taste call.\n\n"
    "The benchmark showed a thin but repeatable margin. The resolution states the "
    "result, and the rule keeps its tier only while the corpus still backs it."
)


class _CountingPipeline:
    """Forwards to the real rubric pipeline, counting parse invocations.

    Counts per document, whether the parse arrives through `__call__` (one
    paragraph at a time) or through `pipe` (one batched call), so the test pins
    work per paragraph, not a particular spaCy calling convention.
    """

    def __init__(self, inner):
        self._inner = inner
        self.parse_count = 0

    def __call__(self, text: str):
        self.parse_count += 1
        return self._inner(text)

    def pipe(self, texts, **kwargs):
        texts = list(texts)
        self.parse_count += len(texts)
        return self._inner.pipe(texts, **kwargs)


class _FakeEncoder:
    """Deterministic stand-in for the MiniLM wrapper: one fixed 2-D vector per text."""

    def __init__(self):
        self.encode_calls: list[list[str]] = []

    def encode(self, texts, normalize_embeddings=False):
        texts = list(texts)
        self.encode_calls.append(texts)
        return np.asarray([_fake_vector(t) for t in texts], dtype=np.float64)


def _fake_vector(text: str) -> np.ndarray:
    return np.asarray([len(text) % 5 + 1.0, text.count("a") % 3 + 1.0])


class SpacyParsesOncePerParagraphTests(unittest.TestCase):
    """The spaCy pipeline runs once per paragraph per check_text call (#192)."""

    def test_check_text_parses_each_paragraph_once_across_all_rubrics(self):
        real_pipeline = features._rubric_nlp()
        counter = _CountingPipeline(real_pipeline)
        with patch.object(features, "_rubric_nlp", return_value=counter):
            check_text(_TEXT, rubrics=["schimel", "density"])
        n_paragraphs = len(DocumentView(_TEXT).paragraphs)
        self.assertEqual(counter.parse_count, n_paragraphs)


class BatchedSentenceEncodeTests(unittest.TestCase):
    """All sentence encodes for paragraph_internal_similarity happen in one call (#192)."""

    def test_internal_similarities_encode_once_and_split_back_in_order(self):
        encoder = _FakeEncoder()
        doc = DocumentView(_TEXT)
        with patch.object(features, "_embed_model", return_value=encoder):
            values = [
                doc.paragraph_internal_similarity(i)
                for i in range(len(doc.paragraphs))
            ]

        multi = [sents for sents in doc.sentences if len(sents) >= 2]
        self.assertEqual(len(encoder.encode_calls), 1)
        self.assertEqual(encoder.encode_calls[0], [s for sents in multi for s in sents])

        for i, sents in enumerate(doc.sentences):
            if len(sents) < 2:
                expected = 1.0
            else:
                emb = [_fake_vector(s) for s in sents]
                sims = [cosine(emb[j], emb[j + 1]) for j in range(len(emb) - 1)]
                expected = float(np.mean(sims))
            self.assertEqual(values[i], expected)


class RubricEntryPointKeepsWorkingTests(unittest.TestCase):
    """Direct callers may pass a shared view or none; both give the same result (#192)."""

    def test_schimel_check_without_doc_matches_shared_view_result(self):
        doc = DocumentView(_TEXT)
        with_view = SchimelRubric().check(_TEXT, doc)
        without_view = SchimelRubric().check(_TEXT)
        self.assertEqual(with_view.to_dict(), without_view.to_dict())

    def test_density_check_without_doc_matches_shared_view_result(self):
        doc = DocumentView(_TEXT)
        with_view = DensityRubric().check(_TEXT, doc)
        without_view = DensityRubric().check(_TEXT)
        self.assertEqual(with_view.to_dict(), without_view.to_dict())


if __name__ == "__main__":
    unittest.main()
