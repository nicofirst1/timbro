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

import os
import re
from collections import Counter
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path

import numpy as np

from timbro.tells import tell_rates, TELL_LABEL, TELL_PRIOR

# Markdown-structure axes scored as a SEPARATE group from the embedding/POS composite
# (issue #28) -- these never feed the distance/direction above, they get their own
# z-score-vs-corpus report. Each axis carries an imperative revision phrase per
# direction, (raise, lower), matching the "fewer/more <label>" register of the POS
# direction. Only structural (`struct_*`) numeric axes a writer can actually move are
# listed; the frontmatter-description (`fm_desc_*`) and string fields are excluded.
MARKDOWN_AXES: tuple[tuple[str, str, str], ...] = (
    ("struct_heading_count", "add section headings", "merge section headings"),
    ("struct_max_heading_depth", "deepen sectioning", "flatten sectioning"),
    ("struct_code_char_ratio", "add code blocks", "reduce code blocks"),
    ("struct_inline_code_char_ratio", "add inline code", "reduce inline code"),
    ("struct_list_item_ratio", "add lists", "reduce list share"),
    ("struct_bullet_list_ratio", "add bullets", "reduce bullet share"),
    ("struct_ordered_list_ratio", "add numbered steps", "reduce numbered steps"),
    ("struct_table_count", "add tables", "remove tables"),
    ("struct_external_ref_count", "add external references", "trim external references"),
    ("struct_long_paragraph_ratio", "lengthen paragraphs", "break up long paragraphs"),
    ("struct_prose_ratio", "add prose", "reduce prose"),
)
STRUCT_AXIS_NAMES: tuple[str, ...] = tuple(name for name, _, _ in MARKDOWN_AXES)
# Within half a corpus std of the mean = on-target; no revision direction named for that
# axis. ponytail: fixed tolerance, promote to a knob only if a caller needs to tune it.
MARKDOWN_Z_TOL = 0.5

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
_WORD = re.compile(r"\b\w+\b")

# Packaged sample corpus -- makes the plugin run on install (override via env for a real voice).
_SAMPLE = Path(__file__).parent / "sample"
DEFAULT_EXEMPLARS = _SAMPLE / "exemplars"
DEFAULT_CONTRAST = _SAMPLE / "contrast"


@lru_cache(maxsize=1)
def _nlp():
    import spacy

    try:
        return spacy.load("en_core_web_sm", disable=["ner", "lemmatizer", "parser"])
    except OSError as e:  # model isn't a pip dep; spaCy ships it via a separate download
        raise OSError("Run: uv run python -m spacy download en_core_web_sm") from e


@lru_cache(maxsize=1)
def _style_model():
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    try:
        from transformers.utils import logging as tlog

        tlog.set_verbosity_error()
    except Exception:
        pass
    try:
        from huggingface_hub.utils import disable_progress_bars, logging as hlog

        disable_progress_bars()
        hlog.set_verbosity_error()
    except Exception:
        pass
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


@lru_cache(maxsize=512)
def _struct_vec(text: str) -> tuple[float, ...]:
    """Markdown-structure feature vector (MARKDOWN_AXES order) for one raw document.
    Reuses analyze._struct_features -- the same extractor `timbro analyze` emits, so
    scoring and analysis never drift. Ratio axes are None on empty input; coerce to 0.0
    (no structure == zero structure) so a draft with no markdown never breaks z-scoring.
    """
    from timbro.analyze import _struct_features  # lazy: analyze imports POS_TAGS from here

    struct, _ = _struct_features(text)
    return tuple(float(struct.get(name) or 0.0) for name in STRUCT_AXIS_NAMES)


def _label(name: str) -> str:
    """POS or tell label for a feature, so the hint reads as advice not a feature id."""
    return POS_LABEL[name[4:]] if name.startswith("pos_") else TELL_LABEL[name[5:]]


def features(text: str) -> dict[str, float]:
    """Named style features for one document. Every value traces to its name (NFR2)."""
    pos = {f"pos_{tag}": r for tag, r in zip(POS_TAGS, _pos_rates(text))}
    return pos | tell_rates(text)  # pos_* grammatical texture + tell_* lexical AI-markers


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
class MarkdownAxis:
    """One markdown-structure axis: where the draft sits vs the corpus (z-score) and the
    named direction back toward the corpus pole. Separate from FeatureMove -- struct is a
    standalone axis group, not part of the embedding/POS composite (issue #28)."""
    axis: str
    value: float        # the draft's raw feature value on this axis
    corpus_mean: float
    z: float            # draft's distance from corpus mean in corpus std units (0 = on-target)
    direction: str      # imperative phrase toward the corpus mean, "" once |z| is negligible

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


def _profile_evidence(texts: list[str]) -> tuple[int, int, str, str | None]:
    total_words = sum(len(_WORD.findall(t)) for t in texts)
    total_paragraphs = sum(len([p for p in _PARA.split(t) if len(_WORD.findall(p)) >= 30]) for t in texts)
    if total_words < 1200 or total_paragraphs < 8:
        return total_words, total_paragraphs, "insufficient", (
            f"Insufficient profile evidence: {total_words} words / {total_paragraphs} substantive paragraphs. "
            "Distance is noisy and direction is suppressed."
        )
    if total_words < 2500 or total_paragraphs < 16:
        return total_words, total_paragraphs, "weak", (
            f"Weak profile evidence: {total_words} words / {total_paragraphs} substantive paragraphs. "
            "Distance is usable, but direction may be unstable."
        )
    return total_words, total_paragraphs, "ok", None


def _loo_exemplar_distances(train_ez: np.ndarray, knn_k: int) -> np.ndarray:
    if len(train_ez) < 2:
        return np.zeros(1)
    dists = []
    k = max(1, min(knn_k, len(train_ez) - 1))
    for i in range(len(train_ez)):
        rest = np.delete(train_ez, i, axis=0)
        dists.append(_knn(rest, train_ez[i], k))
    return np.array(dists, dtype=float)


class VoiceModel:
    """Fit a multi-modal acceptance region from exemplars; score a draft against it.
    Scalar distance is the StyleDistance embedding kNN; direction is white-box POS."""

    def __init__(self, names, pmean, pstd, train_pz, confidence,
                 emean, estd, train_ez, top_k, knn_k,
                 exemplar_count, contrast_count, total_words, total_paragraphs,
                 health, warning, exemplar_floor, exemplar_spread, contrast_ceiling,
                 smean=None, sstd=None):
        self.smean = smean            # struct axis mean / std over the exemplar corpus (#28)
        self.sstd = sstd              # -- separate group, z-scored independently of the composite
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
        self.exemplar_count = exemplar_count
        self.contrast_count = contrast_count
        self.total_words = total_words
        self.total_paragraphs = total_paragraphs
        self.health = health
        self.warning = warning
        self.exemplar_floor = exemplar_floor
        self.exemplar_spread = exemplar_spread
        self.contrast_ceiling = contrast_ceiling

    @classmethod
    def fit(cls, texts: list[str], contrast: list[str] | None = None,
            top_k: int = 6, knn_k: int = 1) -> "VoiceModel":
        total_words, total_paragraphs, health, warning = _profile_evidence(texts)
        # POS path (direction)
        X, names = feature_matrix(texts)
        pmean, pstd = X.mean(0), X.std(0)
        pstd[pstd == 0] = 1.0
        conf = _confidence(X, feature_matrix(contrast)[0]) if contrast else np.ones(len(names))
        # tells get an empirical floor (Reddit frequency ranks) so they surface even
        # when the contrast set is clean -- no separate AI-slop corpus needed.
        for i, nm in enumerate(names):
            if nm.startswith("tell_"):
                conf[i] = max(conf[i], TELL_PRIOR[nm[5:]])
        # struct path (separate axis group #28): same z-score machinery as the POS path --
        # mean/std over the exemplar corpus, zero-variance axes guarded to std=1 so a
        # degenerate corpus yields z=0 (on-target) instead of inf/NaN.
        S = np.array([_struct_vec(t) for t in texts], dtype=float)
        smean, sstd = S.mean(0), S.std(0)
        sstd[sstd == 0] = 1.0
        # embedding path (scalar)
        E = np.array([_style_vec(t) for t in texts])
        emean, estd = E.mean(0), E.std(0)
        estd[estd == 0] = 1.0
        train_ez = (E - emean) / estd
        exemplar_dists = _loo_exemplar_distances(train_ez, knn_k)
        exemplar_floor = float(np.median(exemplar_dists))
        exemplar_spread = float(np.std(exemplar_dists) or 1.0)
        contrast_ceiling = None
        if contrast:
            C = np.array([_style_vec(t) for t in contrast])
            if len(C):
                contrast_ez = (C - emean) / estd
                contrast_ceiling = float(np.mean([_knn(train_ez, z, knn_k) for z in contrast_ez]))
        return cls(names, pmean, pstd, (X - pmean) / pstd, conf,
                   emean, estd, train_ez, top_k, knn_k,
                   len(texts), len(contrast or []), total_words, total_paragraphs,
                   health, warning, exemplar_floor, exemplar_spread, contrast_ceiling,
                   smean=smean, sstd=sstd)

    @classmethod
    def from_dir(cls, exemplars: str | Path, contrast: str | Path | None = None,
                 top_k: int = 6, knn_k: int = 1) -> "VoiceModel":
        texts = read_corpus(exemplars)
        if not texts:  # plugin-friendly: name the env var AND the absolute path actually checked
            raise FileNotFoundError(
                f"No .md/.txt exemplars found at {Path(exemplars).resolve()}. "
                f"Set TIMBRO_EXEMPLARS to a folder of posts that define your voice.")
        co = read_corpus(contrast) if contrast else None
        return cls.fit(texts, co, top_k, knn_k)

    def feature_vector(self, text: str) -> np.ndarray:
        return np.array([features(text)[k] for k in self.names])

    def _dist(self, text: str) -> float:
        # public scalar: embedding kNN (the 0.859 lens)
        ez = (np.array(_style_vec(text)) - self.emean) / self.estd
        return _knn(self.train_ez, ez, self.knn_k)

    def normalized_distance(self, text: str) -> float | None:
        if self.health != "ok":
            return None
        return (self._dist(text) - self.exemplar_floor) / (self.exemplar_spread or 1.0)

    def on_voice(self, text: str) -> bool | None:
        if self.health != "ok":
            return None
        return self._dist(text) <= self.exemplar_floor + self.exemplar_spread

    def profile_report(self) -> dict:
        warning = self.warning
        if getattr(self, "sample_fallback", False):
            sample_warning = "Using packaged sample voice, not a user profile. Set TIMBRO_EXEMPLARS/TIMBRO_CONTRAST or use --profile."
            warning = f"{warning} {sample_warning}".strip() if warning else sample_warning
        return {
            "health": self.health,
            "warning": warning,
            "exemplars": self.exemplar_count,
            "contrast": self.contrast_count,
            "words": self.total_words,
            "paragraphs": self.total_paragraphs,
            "exemplar_floor": self.exemplar_floor,
            "exemplar_spread": self.exemplar_spread,
            "contrast_ceiling": self.contrast_ceiling,
            "sample_fallback": getattr(self, "sample_fallback", False),
        }

    def _pos_dist(self, vec: np.ndarray) -> float:
        # POS-space distance -- the space the direction lives in (sign test only)
        return _knn(self.train_pz, (vec - self.mean) / self.std, self.knn_k)

    def score(self, text: str) -> ScoreResult:
        vec = self.feature_vector(text)
        z = (vec - self.mean) / self.std
        # Rank by confidence x distance: a feature is worth moving only if it both
        # reliably marks your voice (R^2) and is currently off (|z|).
        importance = self.confidence * np.abs(z)
        for i, nm in enumerate(self.names):
            if nm.startswith("tell_") and z[i] <= 0:
                importance[i] = 0.0
        order = np.argsort(-importance)[: self.top_k]
        moves = []
        if self.health != "insufficient":
            for i in order:
                if importance[i] <= 0 or self.confidence[i] < 0.20:
                    continue
                fewer = z[i] > 0 or self.names[i].startswith("tell_")
                moves.append(
                    FeatureMove(
                        self.names[i],
                        float(z[i]),
                        float(-z[i]),
                        float(self.confidence[i]),
                        f"{'fewer' if fewer else 'more'} {_label(self.names[i])}",
                    )
                )
        return ScoreResult(self._dist(text), moves)

    def markdown_report(self, text: str) -> list[MarkdownAxis]:
        """Per-axis markdown-structure distance from the corpus (issue #28).

        z-scores the draft's struct features against the exemplar-corpus mean/std
        (computed at fit time, same machinery as the POS path), and names the direction
        back toward the corpus pole. Separate from score() -- struct never touches the
        embedding distance or POS direction. A near-target axis (|z| < MARKDOWN_Z_TOL) gets
        an empty direction string. Returns [] if the model was built without struct stats.
        """
        if self.smean is None or self.sstd is None:
            return []
        vec = np.array(_struct_vec(text), dtype=float)
        z = (vec - self.smean) / self.sstd
        out = []
        for i, (axis, raise_hint, lower_hint) in enumerate(MARKDOWN_AXES):
            zi = float(z[i])
            if abs(zi) < MARKDOWN_Z_TOL:
                direction = ""
            else:
                direction = lower_hint if zi > 0 else raise_hint  # move back toward corpus mean
            out.append(MarkdownAxis(axis, float(vec[i]), float(self.smean[i]), zi, direction))
        return out


def default_model() -> "VoiceModel":
    """Env-overridable corpus, falling back to the packaged sample. Shared by CLI + MCP."""
    exemplars = os.environ.get("TIMBRO_EXEMPLARS") or DEFAULT_EXEMPLARS
    contrast = os.environ.get("TIMBRO_CONTRAST") or DEFAULT_CONTRAST
    model = VoiceModel.from_dir(
        exemplars,
        contrast=contrast,
    )
    model.sample_fallback = not os.environ.get("TIMBRO_EXEMPLARS") and not os.environ.get("TIMBRO_CONTRAST")
    return model


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
