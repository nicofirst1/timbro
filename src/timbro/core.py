"""Timbro Phase 1 MVP: corpus -> named style features -> Mahalanobis region.

One feature backbone (function-word frequencies + readability). No spaCy, no
embeddings, no feature selection -- a ~20-feature vector doesn't overfit at n=15,
so selection (and its own overfitting) is skipped until a second backbone lands.
# ponytail: single backbone, stack BiberPlus/Gram2Vec only if the LOO gate fails.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path

import numpy as np
import textstat
from sklearn.covariance import LedoitWolf
from sklearn.decomposition import PCA

# Most-frequent English function words -- the classical stylometric backbone
# (Burrows Delta uses exactly this kind of list). Relative frequencies of these
# are ~topic-invariant, which is the whole point of the style layer.
FUNCTION_WORDS = (
    "the be to of and a in that have i it for not on with he as you do at this but his "
    "by from they we say her she or an will my one all would there their what so up out "
    "if about who get which go me when make can like time no just him know take people "
    "into year your good some could them see other than then now look only come its over "
    "think also back after use two how our work first well way even new want because any "
    "these give day most us is are was were been has had did"
).split()

# Optional callable(name)->bool to restrict the feature set. The confound guard
# sets it to fw_-only to prove voice separates without length features.
# ponytail: module global is the smallest seam; thread a param if a 2nd caller appears.
FEATURE_FILTER = None

_WORD = re.compile(r"[a-z]+(?:'[a-z]+)?")
_SENT = re.compile(r"[.!?]+(?:\s|$)")
_PARA = re.compile(r"\n\s*\n")


_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)


def read_corpus(directory: str | Path) -> list[str]:
    """All .md/.txt files in a dir, YAML frontmatter stripped."""
    d = Path(directory)
    files = sorted([*d.glob("*.md"), *d.glob("*.txt")])
    # ponytail: strip frontmatter only; code fences / blockquotes left in as part
    # of his texture. Strip them too if they prove to be topic noise, not style.
    return [_FRONTMATTER.sub("", f.read_text(encoding="utf-8")) for f in files]


def features(text: str) -> dict[str, float]:
    """Named style features for one document. Every value traces to its name (NFR2)."""
    words = _WORD.findall(text.lower())
    n = len(words) or 1
    sents = [s for s in _SENT.split(text) if s.strip()]
    sent_lens = [len(_WORD.findall(s)) for s in sents] or [0]

    feats = {f"fw_{w}": words.count(w) / n for w in FUNCTION_WORDS}
    feats["mean_sentence_length"] = float(np.mean(sent_lens))
    feats["std_sentence_length"] = float(np.std(sent_lens))
    feats["mean_word_length"] = sum(len(w) for w in words) / n
    feats["type_token_ratio"] = len(set(words)) / n
    feats["comma_rate"] = text.count(",") / n
    feats["flesch_reading_ease"] = textstat.flesch_reading_ease(text)
    if FEATURE_FILTER is not None:
        feats = {k: v for k, v in feats.items() if FEATURE_FILTER(k)}
    return feats


def feature_matrix(texts: list[str]) -> tuple[np.ndarray, list[str]]:
    rows = [features(t) for t in texts]
    names = list(rows[0])
    X = np.array([[r[k] for k in names] for r in rows], dtype=float)
    return X, names


def _confidence(exemplar_X: np.ndarray, contrast_X: np.ndarray) -> np.ndarray:
    """Per-feature R^2: squared point-biserial correlation with the voice label.
    1.0 = this feature perfectly separates you from contrast; ~0 = noise (rare
    function words land here, which is the point)."""
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
    distance: float           # Mahalanobis distance from your voice region
    direction: list[FeatureMove]

    def to_dict(self) -> dict:
        return {"distance": self.distance, "direction": [m.to_dict() for m in self.direction]}


class VoiceModel:
    """Fit an acceptance region from exemplars; score a draft against it."""

    def __init__(self, names, mean, std, pca, cov, confidence, top_k):
        self.names = names
        self.mean = mean          # feature-space mean / std for z-scoring + direction
        self.std = std
        self.pca = pca
        self.cov = cov            # LedoitWolf in PCA space
        self.confidence = confidence  # per-feature R^2 vs contrast (1.0 if no contrast)
        self.top_k = top_k

    @classmethod
    def fit(cls, texts: list[str], contrast: list[str] | None = None,
            top_k: int = 6) -> "VoiceModel":
        X, names = feature_matrix(texts)
        mean, std = X.mean(0), X.std(0)
        std[std == 0] = 1.0
        Z = (X - mean) / std
        # PCA caps dims at n-1; LedoitWolf shrinkage is critical at n~=15 (raw cov singular).
        pca = PCA(n_components=min(Z.shape[0] - 1, Z.shape[1])).fit(Z)
        cov = LedoitWolf().fit(pca.transform(Z))
        conf = _confidence(X, feature_matrix(contrast)[0]) if contrast else np.ones(len(names))
        return cls(names, mean, std, pca, cov, conf, top_k)

    @classmethod
    def from_dir(cls, exemplars: str | Path, contrast: str | Path | None = None,
                 top_k: int = 6) -> "VoiceModel":
        co = read_corpus(contrast) if contrast else None
        return cls.fit(read_corpus(exemplars), co, top_k)

    def feature_vector(self, text: str) -> np.ndarray:
        return np.array([features(text)[k] for k in self.names])

    def _dist(self, vec: np.ndarray) -> float:
        z = (vec - self.mean) / self.std
        return float(np.sqrt(self.cov.mahalanobis(self.pca.transform(z[None]))[0]))

    def score(self, text: str) -> ScoreResult:
        vec = self.feature_vector(text)
        z = (vec - self.mean) / self.std
        # Rank by confidence x distance: a feature is worth moving only if it both
        # reliably marks your voice (R^2) and is currently off (|z|). This is what
        # demotes the rare-function-word noise that dominated raw |z|.
        importance = self.confidence * np.abs(z)
        order = np.argsort(-importance)[: self.top_k]
        moves = [
            FeatureMove(self.names[i], float(z[i]), float(-z[i]), float(self.confidence[i]),
                        f"{'lower' if z[i] > 0 else 'raise'} {self.names[i]}")
            for i in order
        ]
        return ScoreResult(self._dist(vec), moves)


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
