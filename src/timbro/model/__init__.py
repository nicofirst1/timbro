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
fully named. fw/punct/PCA/LedoitWolf variants were dropped: all measured worse.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np

from timbro.axes.concreteness import (  # noqa: F401  (import registers the metric)
    CONCRETENESS_METRIC,
)
from timbro.axes.fw import (  # noqa: F401  (import registers the metric)
    FUNCTION_WORD_METRIC,
)
from timbro.axes.hedge import (  # noqa: F401  (import registers the metric)
    HEDGE_BOOSTER_METRIC,
)
from timbro.axes.markdown import (  # noqa: F401  (import registers the metric)
    MARKDOWN_METRIC,
)
from timbro.axes.richness import (  # noqa: F401  (import registers the metric)
    RICHNESS_METRIC,
)
from timbro.axes.tells import (  # noqa: F401  (import registers the tells metric)
    TELL_METRIC,
)
from timbro.metric import REGISTRY, Metric, _confidence, _knn
from timbro.model.direction import feature_matrix, features
from timbro.model.embedding import _style_vec, fit_embedding
from timbro.priors import (
    AXIS_Z_SATURATION,
    DEFAULT_CONTRAST,
    DEFAULT_EXEMPLARS,
    TELL_PRIOR,
)
from timbro.report import (  # dataclasses/labels: report.py formats for humans
    AxisReport,
    FeatureMove,
    ScoreResult,
    _label,
)
from timbro.text import (
    _PARA,  # shared raw-text plumbing (same regex text.py has always used)
)

_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_WORD = re.compile(r"\b\w+\b")


def read_corpus(directory: str | Path) -> list[str]:
    """All .md/.txt files in a dir, YAML frontmatter stripped."""
    d = Path(directory)
    files = sorted([*d.glob("*.md"), *d.glob("*.txt")])
    # Strip frontmatter only; code fences / blockquotes are left in as part of the
    # voice's texture. Strip them too if they prove to be topic noise, not style.
    return [_FRONTMATTER.sub("", f.read_text(encoding="utf-8")) for f in files]


def no_exemplars_error(exemplars: str | Path) -> FileNotFoundError:
    """The one wording for an empty/missing corpus, shared by every caller (#161):
    name the absolute path actually checked, and point at managed profiles for the
    fix (round 3: no env-var suggestion, direction #96)."""
    return FileNotFoundError(
        f"No .md/.txt exemplars found at {Path(exemplars).resolve()}. "
        "Add posts that define your voice with: timbro profiles add-file <profile> <file> --to exemplars"
    )


def _blend_metrics() -> list[Metric]:
    """The registered blend-style metrics (#108): those carrying `hint_axes` (excludes
    tells/politeness). One definition shared by fit() and axis_report() so metric
    discovery and lookup can't drift."""
    return [m for m in REGISTRY if hasattr(m, "hint_axes")]


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


class VoiceModel:
    """Fit a multi-modal acceptance region from exemplars; score a draft against it.
    Scalar distance is the StyleDistance embedding kNN; direction is white-box POS."""

    def __init__(self, names, pmean, pstd, train_pz, confidence,
                 emean, estd, train_ez, top_k, knn_k,
                 exemplar_count, contrast_count, total_words, total_paragraphs,
                 health, warning, exemplar_floor, exemplar_spread, contrast_ceiling,
                 axis_stats: dict | None = None):
        # One corpus-stats dict for every blend-style axis (#108), replacing the 14
        # Xmean/Xstd/Xn attributes: metric name -> (per-axis mean, per-axis std, corpus
        # doc count). Raw std -- the zero-std guard lives in axis_report (`spread or
        # 1.0`), not here.
        self._axis_stats: dict[str, tuple[tuple[float, ...], tuple[float, ...], int]] = dict(axis_stats or {})
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
            top_k: int = 6, knn_k: int = 1) -> VoiceModel:
        total_words, total_paragraphs, health, warning = _profile_evidence(texts)
        # POS path (direction)
        X, names = feature_matrix(texts)
        pmean, pstd = X.mean(0), X.std(0)
        # POS and tell rates live in [0, 1], so a std below 1e-9 is float rounding, not spread.
        pstd[pstd < 1e-9] = 1.0
        conf = _confidence(X, feature_matrix(contrast)[0]) if contrast else np.ones(len(names))
        # tells get an empirical floor (Reddit frequency ranks) so they surface even
        # when the contrast set is clean -- no separate AI-slop corpus needed.
        for i, nm in enumerate(names):
            if nm.startswith("tell_"):
                conf[i] = max(conf[i], TELL_PRIOR[nm[5:]])
        # One corpus-stats pass over every registered blend-style metric (#108): raw
        # std -- the report's `spread or 1.0` guards zero-variance axes. A new axis
        # costs zero lines here: its import registers it; `hint_axes` selects it.
        axis_stats: dict[str, tuple[tuple[float, ...], tuple[float, ...], int]] = {}
        for m in _blend_metrics():
            M = np.array([m.extract(t) for t in texts], dtype=float)
            axis_stats[m.name] = (tuple(M.mean(0)), tuple(M.std(0)), len(texts))
        emean, estd, train_ez, exemplar_floor, exemplar_spread, contrast_ceiling = fit_embedding(texts, contrast, knn_k)
        return cls(names, pmean, pstd, (X - pmean) / pstd, conf,
                   emean, estd, train_ez, top_k, knn_k,
                   len(texts), len(contrast or []), total_words, total_paragraphs,
                   health, warning, exemplar_floor, exemplar_spread, contrast_ceiling,
                   axis_stats=axis_stats)

    @classmethod
    def from_dir(cls, exemplars: str | Path, contrast: str | Path | None = None,
                 top_k: int = 6, knn_k: int = 1) -> VoiceModel:
        texts = read_corpus(exemplars)
        if not texts:
            raise no_exemplars_error(exemplars)
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
            sample_warning = (
                "Using packaged sample voice, not a user profile. "
                "Use --profile <name> (create one with: timbro profiles init <name>)."
            )
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

    def axis_report(self, metric_name: str, text: str) -> list[AxisReport]:
        """Per-axis distance from the reference for any registered blend-style metric
        (#108): one implementation for markdown/hedge/fw/concreteness/richness, whose
        named wrappers below are one-liners over this.

        z-scores the draft's metric values against a reference that is always defined:
        the metric's declared prior blended with the corpus mean/std via
        `Reference.blend`, weighted by the corpus doc count against the prior's
        `strength`. With no corpus stats, a strength>0 prior still reports (blend
        passes it through at n=0, so a `check`-style no-profile call gets usable
        advice); a strength==0 metric like markdown is corpus-only and returns [].
        A near-target axis (|z| < metric.z_tol) gets an empty direction string; the
        direction names the way back toward the reference in the metric's own
        `hint_axes` vocabulary. Zero-variance axes get spread forced to 1.0, so a
        degenerate corpus yields z=0 (on-target), never inf/NaN. Axis z is capped
        at ±AXIS_Z_SATURATION (#178): a row whose raw |z| exceeds the cap is marked
        saturated, and the direction consumes the clamped z. Never touches the
        embedding distance or POS direction -- standalone axis group. Raises KeyError
        for a name that is not a registered blend-style metric.
        """
        metric = next((m for m in _blend_metrics() if m.name == metric_name), None)
        if metric is None:
            raise KeyError(
                f"no blend-style metric named {metric_name!r}; "
                f"blend-style registered: {[m.name for m in _blend_metrics()]}"
            )
        stats = self._axis_stats.get(metric_name)
        if stats is None:
            if metric.prior.strength == 0:  # corpus-only axis (markdown): nothing to z-score against
                return []
            mean, std, n = metric.prior.mean, metric.prior.spread, 0
        else:
            mean, std, n = stats
        ref_mean, ref_spread = metric.prior.blend(mean, std, n)
        vec = metric.extract(text)
        out = []
        for i, (axis, raise_hint, lower_hint) in enumerate(metric.hint_axes):
            spread = ref_spread[i] or 1.0  # zero-std guard: degenerate axis is on-target
            raw_z = float((vec[i] - ref_mean[i]) / spread)
            z = max(-AXIS_Z_SATURATION, min(AXIS_Z_SATURATION, raw_z))
            saturated = abs(raw_z) > AXIS_Z_SATURATION
            direction = "" if abs(z) < metric.z_tol else (lower_hint if z > 0 else raise_hint)
            out.append(AxisReport(axis, float(vec[i]), float(ref_mean[i]), z, direction, saturated))
        return out

    # Backward-compat wrappers: the five named methods stay as one-liners over
    # axis_report -- same names, same return types; report.py/cli.py/tests keep calling
    # these. The per-axis detail lives in axis_report's docstring, not repeated here.

    def markdown_report(self, text: str) -> list[AxisReport]:
        """Markdown-structure report (#28); see `axis_report`."""
        return self.axis_report("markdown", text)

    def hedge_report(self, text: str) -> list[AxisReport]:
        """Hedge/booster stance report (#44); see `axis_report`."""
        return self.axis_report("hedge", text)

    def fw_report(self, text: str) -> list[AxisReport]:
        """Function-word report (#45); see `axis_report`."""
        return self.axis_report("fw", text)

    def concreteness_report(self, text: str) -> list[AxisReport]:
        """Concreteness report (#46); see `axis_report`."""
        return self.axis_report("concreteness", text)

    def richness_report(self, text: str) -> list[AxisReport]:
        """Readability/richness/entropy report (#88); see `axis_report`."""
        return self.axis_report("richness", text)


def default_model() -> VoiceModel:
    """Env-overridable corpus, falling back to the packaged sample."""
    exemplars = os.environ.get("TIMBRO_EXEMPLARS") or DEFAULT_EXEMPLARS
    contrast = os.environ.get("TIMBRO_CONTRAST") or DEFAULT_CONTRAST
    model = VoiceModel.from_dir(
        exemplars,
        contrast=contrast,
    )
    model.sample_fallback = not os.environ.get("TIMBRO_EXEMPLARS") and not os.environ.get("TIMBRO_CONTRAST")
    return model

