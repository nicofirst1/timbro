"""One interface for every scalar style axis: an extractor plus a declared prior (#43).

A metric is the same two-part machine everywhere: an `extract` pulls raw scalars off
*one* draft (hedge rate, sentence length, tell rate), and a `Reference` says what those
scalars are expected to be. "Absolute vs contrastive" stops being two code paths and
becomes one runtime question -- was a corpus supplied? No corpus: judge against the
declared `prior`. Corpus present: blend the prior with the corpus mean/std, weighted by
`strength`. `Reference` is `TELL_PRIOR` generalised.

The tells and the markdown-structure axes are ported onto this here to prove the shape
holds; new language axes (#44/#45/#46) implement `Metric` and register, nothing else.
This module moves structure, not numbers: the ported metrics resolve their reference
exactly as before (see model.py), so scores are unchanged. `Reference.blend` is the
prior->posterior formula the new axes use.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Reference:
    """The expected value of an extractor's axes, and how hard that expectation resists a
    corpus. `mean`/`spread` are per-axis (same length as the metric's `axes`); `strength`
    is a pseudo-count -- how many corpus documents the prior is worth."""

    mean: tuple[float, ...]
    spread: tuple[float, ...]
    strength: float

    def blend(self, corpus_mean, corpus_std, n: int) -> tuple[tuple[float, ...], tuple[float, ...]]:
        """Precision-weighted posterior of prior + corpus (open question #1, the confirmed
        formula): `strength` is the prior's pseudo-count, the corpus mean wins in proportion
        to how many documents it has. With `n == 0` the prior passes through unchanged; as
        `n` grows the corpus dominates. Returns (mean, spread) per axis. Used by the new
        axes (#44/#45/#46); the ported tells/markdown keep their existing reference path so
        this refactor changes no numbers.

        ponytail: pooled by document count, not inverse-variance -- `strength` IS the knob
        the spec asked for. A full inverse-variance pool is only worth it if a corpus needs
        per-axis precision the count can't express.
        """
        s = self.strength
        out_mean = []
        out_spread = []
        for i in range(len(self.mean)):
            cm = float(corpus_mean[i])
            cs = float(corpus_std[i])
            w = n / (n + s) if (n + s) else 0.0
            out_mean.append(w * cm + (1.0 - w) * self.mean[i])
            out_spread.append(w * cs + (1.0 - w) * self.spread[i])
        return tuple(out_mean), tuple(out_spread)


@runtime_checkable
class Metric(Protocol):
    """An extractor + a declared prior. `axes` names the scalars `extract` returns, in
    order; `prior` is the fallback `Reference` when no corpus is present."""

    name: str
    axes: tuple[str, ...]
    prior: Reference

    def extract(self, text: str) -> tuple[float, ...]:
        """Raw scalars on ONE draft, one per entry in `axes`. Cacheable: pure function of
        the text. Takes raw text, not a pre-parsed spaCy doc -- markdown axes need the raw
        markup and text is the common denominator; a metric that needs POS parses internally
        via the shared cached loader. (Interpretation note in the #43 PR.)"""
        ...


# The registry the CLI iterates. Ported metrics register at import of their home module
# (tells.py, model.py) to avoid an import cycle; new axes append here.
REGISTRY: list[Metric] = []


def register(metric: Metric) -> Metric:
    """Add a metric to the registry once (idempotent on `name`, so a re-import is safe)."""
    if not any(m.name == metric.name for m in REGISTRY):
        REGISTRY.append(metric)
    return metric


@lru_cache(maxsize=1)
def _nlp():
    # Shared lemma+POS pipeline for axes that need more than tells.py's tagger-only
    # parse (#44 hedge/booster; future #45/#46). Separate loader/cache from tells.py's
    # `_nlp()` (tagger only, no lemmatizer) and model.py's `_nlp()` (POS rates, no
    # lemmatizer/sentencizer) -- each caller enables only what it needs, and spaCy
    # doesn't let you re-enable a disabled component after load, so three call sites
    # want three pipelines. tagger + attribute_ruler + lemmatizer stay enabled (the
    # lemmatizer needs the tagger's output); ner/parser disabled for speed, same as
    # tells.py. sentencizer is added (cheap, rule-based, not the statistical parser) so
    # sentence-boundary axes (#45/#46 candidates) don't need a second parse.
    import spacy

    try:
        nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
    except OSError as e:  # model isn't a pip dep; spaCy ships it via a separate download
        raise OSError("Run: uv run python -m spacy download en_core_web_sm") from e
    nlp.add_pipe("sentencizer")
    return nlp


@lru_cache(maxsize=8)  # small: Docs are heavy, keep memory bounded
def parsed_doc(text: str):
    """Cached text->Doc for axes that need lemma+POS (and sentence bounds). One parse
    shared across every `Metric` that calls this, instead of each axis reparsing the
    same draft. text[:100000] caps spaCy work, same cap tells.py/model.py use."""
    return _nlp()(text[:100000])


if __name__ == "__main__":
    # Self-check: blend interpolates prior<->corpus by document count via `strength`.
    r = Reference(mean=(2.0,), spread=(1.0,), strength=4.0)
    assert r.blend([10.0], [3.0], 0) == ((2.0,), (1.0,)), "n=0 must pass the prior through"
    m, sp = r.blend([10.0], [3.0], 4)  # w = 4/(4+4) = 0.5 -> midpoints
    assert abs(m[0] - 6.0) < 1e-9 and abs(sp[0] - 2.0) < 1e-9, (m, sp)
    m, _ = r.blend([10.0], [3.0], 10_000)  # corpus swamps the prior
    assert abs(m[0] - 10.0) < 0.01, m
    # Registry stays idempotent on name.
    class _M:
        name, axes, prior = "x", ("a",), r
        def extract(self, text): return (0.0,)
    register(_M())
    register(_M())
    assert sum(1 for x in REGISTRY if x.name == "x") == 1
    print("ok: blend + registry")
