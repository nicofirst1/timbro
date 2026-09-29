"""The "which way" lens: POS-unigram rates, confidence-weighted, white-box (one of
the two lenses; the orchestrator lives in `timbro.model`)."""

from __future__ import annotations

from collections import Counter
from functools import lru_cache

import numpy as np

from timbro.axes.tells import tell_rates

# Universal POS tags (spaCy `pos_`). Rates over these 17 are length-normalized,
# so the doc-length confound that plagued raw counts can't arise here.
POS_TAGS = ("ADJ", "ADP", "ADV", "AUX", "CCONJ", "DET", "INTJ", "NOUN", "NUM",
            "PART", "PRON", "PROPN", "PUNCT", "SCONJ", "SYM", "VERB", "X")


def _nlp():
    from timbro.spacy_model import cached_pipeline

    return cached_pipeline(("ner", "lemmatizer", "parser"), ())


@lru_cache(maxsize=512)
def _pos_rates(text: str) -> tuple[float, ...]:
    # cached: the LOO harness re-scores the same docs across folds, so each doc is
    # tagged once. text[:100000] caps spaCy work on the longest posts.
    pos = [t.pos_ for t in _nlp()(text[:100000]) if not t.is_space]
    n = len(pos) or 1
    c = Counter(pos)
    return tuple(c.get(tag, 0) / n for tag in POS_TAGS)


def features(text: str) -> dict[str, float]:
    """Named style features for one document. Every value traces to its name (NFR2)."""
    pos = {f"pos_{tag}": r for tag, r in zip(POS_TAGS, _pos_rates(text))}
    return pos | tell_rates(text)  # pos_* grammatical texture + tell_* lexical AI-markers


def feature_matrix(texts: list[str]) -> tuple[np.ndarray, list[str]]:
    rows = [features(t) for t in texts]
    names = list(rows[0])
    X = np.array([[r[k] for k in names] for r in rows], dtype=float)
    return X, names
