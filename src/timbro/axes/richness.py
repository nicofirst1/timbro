"""Readability / lexical richness / entropy axis (#88): three cheap, group-level
"how the prose reads" signals, reported standalone.

Source, per the issue's decision record: reuse the two NLP libraries already
installed (`textdescriptives`, `lexical_diversity`) instead of
adding `elfen` (rejected -- drags a second spaCy/torch stack for three formulas).
Shannon entropy is new code, but it's a few stdlib lines over lemma counts, not
worth a dependency either. Since #123 HD-D is local code too, mirroring
lexical_diversity's hdd formula: the library's `list(set(text))` iteration order
varies per process, so the float sum moved ~1 ULP run to run.

One signal per family, gate-picked: a throwaway script ran all 8 textdescriptives
readability formulas and both lexical_diversity richness formulas (mtld, hdd)
against DEFAULT_EXEMPLARS vs DEFAULT_CONTRAST and kept the best separator per
family by Cohen's d (see the #88 PR body for the full table). Winners:
coleman_liau_index (readability, |d|=7.84) and hdd (richness, |d|=3.19) -- neither
was a near-tie with the runner-up, so the "ties break to the most interpretable
(FK grade; mtld)" fallback in the decision record doesn't apply. Shannon entropy
(hand-rolled) also separates (|d|=4.47), so the full 3-tuple ships.

Tier B/C per docs/adr/0005-benchmark-gated-check-development.md (group-level
separation on 4 vs 3 packaged docs, not a labelled per-draft benchmark): this axis
is reported for information, standalone, same as hedge.py/fw.py/concreteness.py --
it does not feed the scored POS/embedding direction or `_WEIGHTS`.
"""

from __future__ import annotations

import math
from collections import Counter
from functools import lru_cache

from timbro.metric import register
from timbro.priors import RICHNESS_REFERENCE

_CONTENT_POS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}

# hdd's fixed sample size: the random sample is 42 tokens (lexical_diversity's
# choice, mirrored exactly so values stay comparable); below it hdd is 0.0.
_HDD_SAMPLE = 42


def _choose(n: int, k: int) -> int:
    """Binomial coefficient, 0 outside 0 <= k <= n: Andrew Dalke's integer
    loop, mirroring lexical_diversity's hdd."""
    if 0 <= k <= n:
        ntok = 1
        ktok = 1
        for t in range(1, min(k, n - k) + 1):
            ntok *= n
            ktok *= t
            n -= 1
        return ntok // ktok
    return 0


def _hdd(tokens: list[str]) -> float:
    """HD-D (hypergeometric distribution diversity, McCarthy & Jarvis 2010),
    0-1: the chance a type appears at least once in a 42-token sample, summed
    over types. Mirrors lexical_diversity.lex_div.hdd term for term; the only
    changes are the summation (math.fsum) and the type order (sorted), so the
    value no longer depends on PYTHONHASHSEED (#123)."""
    ntokens = len(tokens)
    counts = Counter(tokens)
    terms = []
    for t in sorted(counts):
        try:
            term = (1.0 - (_choose(counts[t], 0) * _choose(ntokens - counts[t], _HDD_SAMPLE))
                    / _choose(ntokens, _HDD_SAMPLE)) * (1 / _HDD_SAMPLE)
        except ZeroDivisionError:
            term = 0.0
        terms.append(term)
    return math.fsum(terms)


def _nlp():
    # Separate config from metric.py's `_nlp()`: this axis needs the
    # textdescriptives/readability pipe, which the shared parsed_doc pipeline doesn't
    # carry. parser/ner disabled -- readability only needs the sentencizer's bounds.
    import textdescriptives as td  # noqa: F401  (registers the textdescriptives/* factories)

    from timbro.spacy_model import cached_pipeline

    return cached_pipeline(
        ("ner", "parser"), ("sentencizer", "textdescriptives/readability")
    )


@lru_cache(maxsize=512)
def _doc(text: str):
    return _nlp()(text[:100000])  # same cap parsed_doc/direction.py use


def _shannon_entropy(doc) -> float:
    """Shannon entropy (bits) of the lemma distribution over alphabetic tokens: how
    evenly a draft spreads its word choices vs repeating a small set. Higher = more
    lexical variety/unpredictability."""
    lemmas = [t.lemma_.lower() for t in doc if t.is_alpha]
    n = len(lemmas)
    if n == 0:
        return 0.0
    counts = Counter(lemmas)
    return -sum((c / n) * math.log2(c / n) for c in counts.values())


@lru_cache(maxsize=512)
def richness_stats(text: str) -> tuple[float, float, float]:
    """(readability, richness, entropy) for one draft:
    - readability: Coleman-Liau index (US grade level; higher = harder to read)
    - richness: HDD, hypergeometric distribution diversity (0-1; higher = more varied
      vocabulary, length-robust unlike raw type-token ratio)
    - entropy: Shannon entropy (bits) of the lemma distribution
    """
    doc = _doc(text)
    # textdescriptives returns NaN (0/0) for a doc with no words (#177), and NaN is
    # truthy, so the old `or 0.0` never fired -- screen missing/non-finite explicitly.
    index = doc._.readability.get("coleman_liau_index")
    readability = float(index) if index is not None and math.isfinite(index) else 0.0
    content_lemmas = [t.lemma_.lower() for t in doc if t.is_alpha and t.pos_ in _CONTENT_POS]
    richness = _hdd(content_lemmas) if len(content_lemmas) >= 2 else 0.0
    entropy = _shannon_entropy(doc)
    return readability, richness, entropy


# --- Metric (#88) ----------------------------------------------------------------------


class _RichnessMetric:
    """Readability/richness/entropy axis as a `Metric`. `extract` returns
    (coleman_liau_index, hdd, shannon_entropy) for one raw document."""

    # (axis, raise_hint, lower_hint): "raise" fires when the draft sits below the
    # reference (needs more of the marker); "lower" fires above it.
    hint_axes: tuple[tuple[str, str, str], ...] = (
        ("readability", "simplify sentences and word choice", "add more complex sentences and vocabulary"),
        ("richness", "vary word choice more", "use a narrower, more repeated vocabulary"),
        ("entropy", "vary word choice more", "use a narrower, more repeated vocabulary"),
    )
    # Fixed tolerance; promote to a knob only if a caller needs to tune it.
    z_tol: float = 0.5

    name = "richness"
    axes = tuple(a for a, _, _ in hint_axes)
    prior = RICHNESS_REFERENCE

    def extract(self, text: str) -> tuple[float, ...]:
        return richness_stats(text)


RICHNESS_METRIC = register(_RichnessMetric())


if __name__ == "__main__":
    # Self-check: a plain-worded, repetitive string reads easier, less varied, and lower
    # entropy than a dense, varied one. >42 content-word tokens each -- lexical_diversity's
    # hdd() samples a fixed 42-token window and degenerates to 0.0 below that.
    plain = ("The cat sat on the mat. The cat was happy. The cat liked the mat. "
              "The cat sat there all day. The mat was soft and the cat liked it. "
              "The dog ran in the yard. The dog was happy. The dog liked the yard. "
              "The dog ran there all day. The yard was big and the dog liked it. "
              "The cat and the dog were friends. They sat in the yard on the mat. "
              "They liked the sun and the soft grass. The day was long and warm.")
    dense = ("Epistemological frameworks underpinning contemporary jurisprudence "
              "necessitate a multifaceted reconsideration of adjudicative precedent, "
              "particularly where constitutional ambiguity intersects procedural "
              "heterodoxy across divergent federalist jurisdictions. Subsequent "
              "scholarship interrogates these entrenched assumptions, proposing "
              "alternative taxonomies that destabilize orthodox categorization "
              "while foregrounding marginalized interpretive traditions. Critics "
              "counter that such revisionism, however illuminating, risks eroding "
              "the doctrinal coherence upon which adjudicative legitimacy depends.")
    r_plain, v_plain, e_plain = richness_stats(plain)
    r_dense, v_dense, e_dense = richness_stats(dense)
    assert r_dense > r_plain, (r_dense, r_plain)
    assert v_dense > v_plain, (v_dense, v_plain)
    assert e_dense > e_plain, (e_dense, e_plain)
    print(f"ok: dense readability={r_dense:.1f} > plain={r_plain:.1f}; "
          f"dense richness={v_dense:.2f} > plain={v_plain:.2f}; "
          f"dense entropy={e_dense:.2f} > plain={e_plain:.2f}")
