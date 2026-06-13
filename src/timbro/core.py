"""Timbro style layer: hybrid scalar (neural) + direction (white-box).

Two jobs, two tools, chosen empirically on the real corpus (15 exemplars vs 8
same-domain contrast):

- SCALAR "how far": StyleDistance embedding, mean-pooled over paragraphs, multi-modal
  kNN (k=1) -> LOO-AUC 0.859, clearing the 0.80 gate that classical features can't
  reach at n=15 (pre-trained style beats features you must *fit* from 15 docs).
- DIRECTION "which way": POS-unigram rates, confidence-weighted, white-box. NOUN/VERB
  density *is* nominalization advice. POS beat function words and every combination
  tried (added dims add noise faster than signal at this n).

The embedding scalar is opaque (relaxes NFR2 for the distance); the direction stays
fully named. # ponytail: dropped fw/punct/PCA/LedoitWolf -- all measured worse.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path

import numpy as np

# Universal POS tags (spaCy `pos_`). Rates over these 17 are length-normalized,
# so the doc-length confound that plagued raw counts can't arise here.
POS_TAGS = ("ADJ", "ADP", "ADV", "AUX", "CCONJ", "DET", "INTJ", "NOUN", "NUM",
            "PART", "PRON", "PROPN", "PUNCT", "SCONJ", "SYM", "VERB", "X")

# Plain-English labels so the direction reads as advice, not tag soup.
POS_LABEL = {
    "ADJ": "adjectives", "ADP": "prepositions", "ADV": "adverbs",
    "AUX": "auxiliary verbs", "CCONJ": "conjunctions", "DET": "determiners",
    "INTJ": "interjections", "NOUN": "nouns", "NUM": "numbers", "PART": "particles",
    "PRON": "pronouns", "PROPN": "proper nouns", "PUNCT": "punctuation",
    "SCONJ": "subordinating conjunctions", "SYM": "symbols", "VERB": "verbs", "X": "other tokens",
}

_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_PARA = re.compile(r"\n\s*\n")


@lru_cache(maxsize=1)
def _nlp():
    import spacy

    try:
        return spacy.load("en_core_web_sm", disable=["ner", "lemmatizer", "parser"])
    except OSError as e:  # model isn't a pip dep; spaCy ships it via a separate download
        raise OSError("Run: uv run python -m spacy download en_core_web_sm") from e


@lru_cache(maxsize=1)
def _style_model():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("StyleDistance/styledistance")  # content-invariant style


@lru_cache(maxsize=512)
def _style_vec(text: str) -> tuple[float, ...]:
    # one style vector per doc = mean of paragraph (chunk) style embeddings. cached
    # because the LOO harness re-scores the same docs across folds.
    chunks = [p.strip() for p in _PARA.split(text) if p.strip()] or [text[:2000]]
    return tuple(_style_model().encode(chunks, normalize_embeddings=True).mean(0))


def read_corpus(directory: str | Path) -> list[str]:
    """All .md/.txt files in a dir, YAML frontmatter stripped."""
    d = Path(directory)
    files = sorted([*d.glob("*.md"), *d.glob("*.txt")])
    # ponytail: strip frontmatter only; code fences / blockquotes left in as part
    # of his texture. Strip them too if they prove to be topic noise, not style.
    return [_FRONTMATTER.sub("", f.read_text(encoding="utf-8")) for f in files]


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
    return {f"pos_{tag}": r for tag, r in zip(POS_TAGS, _pos_rates(text))}


def feature_matrix(texts: list[str]) -> tuple[np.ndarray, list[str]]:
    rows = [features(t) for t in texts]
    names = list(rows[0])
    X = np.array([[r[k] for k in names] for r in rows], dtype=float)
    return X, names


def _confidence(exemplar_X: np.ndarray, contrast_X: np.ndarray) -> np.ndarray:
    """Per-feature R^2: squared point-biserial correlation with the voice label.
    1.0 = this feature perfectly separates you from contrast; ~0 = noise."""
    X = np.vstack([exemplar_X, contrast_X])
    y = np.r_[np.ones(len(exemplar_X)), np.zeros(len(contrast_X))]
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    ys = (y - y.mean()) / (y.std() + 1e-9)
    return ((Xs * ys[:, None]).mean(0)) ** 2


@dataclass
class FeatureMove:
    feature: str
    current_z: float
    delta: float        # signed move toward your corpus mean (target z = 0)
    confidence: float   # R^2: how reliably this feature marks your voice (0-1)
    hint: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScoreResult:
    distance: float           # StyleDistance embedding kNN distance to your voice cloud
    direction: list[FeatureMove]

    def to_dict(self) -> dict:
        return {"distance": self.distance, "direction": [m.to_dict() for m in self.direction]}


def _knn(train_z: np.ndarray, z: np.ndarray, k: int) -> float:
    """Mean distance to the k nearest standardized exemplars (multi-modal region)."""
    d = np.linalg.norm(train_z - z, axis=1)
    return float(np.sort(d)[:k].mean())


class VoiceModel:
    """Fit a multi-modal acceptance region from exemplars; score a draft against it.
    Scalar distance is the StyleDistance embedding kNN; direction is white-box POS."""

    def __init__(self, names, pmean, pstd, train_pz, confidence,
                 emean, estd, train_ez, top_k, knn_k):
        self.names = names            # POS feature names (direction is white-box)
        self.mean = pmean             # POS mean / std for z-scoring the direction
        self.std = pstd
        self.train_pz = train_pz      # standardized POS vectors -- POS-space distance (sign test)
        self.confidence = confidence  # per-feature R^2 vs contrast (1.0 if no contrast)
        self.emean = emean            # embedding mean / std + standardized train -- the scalar
        self.estd = estd
        self.train_ez = train_ez
        self.top_k = top_k
        self.knn_k = knn_k

    @classmethod
    def fit(cls, texts: list[str], contrast: list[str] | None = None,
            top_k: int = 6, knn_k: int = 1) -> "VoiceModel":
        # POS path (direction)
        X, names = feature_matrix(texts)
        pmean, pstd = X.mean(0), X.std(0)
        pstd[pstd == 0] = 1.0
        conf = _confidence(X, feature_matrix(contrast)[0]) if contrast else np.ones(len(names))
        # embedding path (scalar)
        E = np.array([_style_vec(t) for t in texts])
        emean, estd = E.mean(0), E.std(0)
        estd[estd == 0] = 1.0
        return cls(names, pmean, pstd, (X - pmean) / pstd, conf,
                   emean, estd, (E - emean) / estd, top_k, knn_k)

    @classmethod
    def from_dir(cls, exemplars: str | Path, contrast: str | Path | None = None,
                 top_k: int = 6, knn_k: int = 1) -> "VoiceModel":
        texts = read_corpus(exemplars)
        if not texts:  # plugin-friendly: a clear message beats an IndexError for agents
            raise FileNotFoundError(
                f"No .md/.txt exemplars in {exemplars!r}. Point TIMBRO_EXEMPLARS at a "
                f"folder of posts that define your voice.")
        co = read_corpus(contrast) if contrast else None
        return cls.fit(texts, co, top_k, knn_k)

    def feature_vector(self, text: str) -> np.ndarray:
        return np.array([features(text)[k] for k in self.names])

    def _dist(self, text: str) -> float:
        # public scalar: embedding kNN (the 0.859 lens)
        ez = (np.array(_style_vec(text)) - self.emean) / self.estd
        return _knn(self.train_ez, ez, self.knn_k)

    def _pos_dist(self, vec: np.ndarray) -> float:
        # POS-space distance -- the space the direction lives in (sign test only)
        return _knn(self.train_pz, (vec - self.mean) / self.std, self.knn_k)

    def score(self, text: str) -> ScoreResult:
        vec = self.feature_vector(text)
        z = (vec - self.mean) / self.std
        # Rank by confidence x distance: a feature is worth moving only if it both
        # reliably marks your voice (R^2) and is currently off (|z|).
        importance = self.confidence * np.abs(z)
        order = np.argsort(-importance)[: self.top_k]
        moves = [
            FeatureMove(self.names[i], float(z[i]), float(-z[i]), float(self.confidence[i]),
                        f"{'fewer' if z[i] > 0 else 'more'} {POS_LABEL[self.names[i][4:]]}")
            for i in order
        ]
        return ScoreResult(self._dist(text), moves)


if __name__ == "__main__":
    # Smoke test: a draft in the seed voice must score closer than an alien one.
    plain = [
        "The cat sat by the door. It was small and grey.",
        "We went to the shop. The shop was shut, so we walked home.",
        "He likes tea. She likes coffee. They share a pot all the same.",
        "Rain fell all day. The street was wet. The dog stayed in.",
        "I read the book twice. The first time was slow. The second was quick.",
        "The bread was warm. We ate it with butter and a bit of jam.",
        "She ran to the bus. It left without her. So she took the next one.",
        "The light was low. We lit a candle and sat and talked.",
    ]
    model = VoiceModel.fit(plain)
    near = model.score("The bird flew off. It was quick and small.").distance
    far = model.score(
        "Henceforth the dialectical synthesis necessitates rigorous deconstruction of ontological categories."
    ).distance
    assert near < far, f"voice region failed to separate: near={near} far={far}"
    print(f"ok: in-voice={near:.2f} < out-of-voice={far:.2f}")
