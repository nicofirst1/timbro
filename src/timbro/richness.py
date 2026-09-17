"""Readability / lexical richness / entropy axis (#88): three cheap, group-level
"how the prose reads" signals, reported standalone.

Source, per the issue's decision record: reuse the two NLP libraries already
installed for `timbro analyze` (`textdescriptives`, `lexical_diversity`) instead of
adding `elfen` (rejected -- drags a second spaCy/torch stack for three formulas).
Shannon entropy is new code, but it's a few stdlib lines over lemma counts, not
worth a dependency either.

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

from timbro.config import RICHNESS_REFERENCE
from timbro.metric import register

_CONTENT_POS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}  # same set analyze.py uses for lex_mtld/lex_hdd


@lru_cache(maxsize=1)
def _nlp():
    # Separate loader from metric.py's `_nlp()`: this axis needs the
    # textdescriptives/readability pipe, which the shared parsed_doc pipeline doesn't
    # carry. parser/ner disabled -- readability only needs the sentencizer's bounds.
    import textdescriptives as td  # noqa: F401  (registers the textdescriptives/* factories)

    from timbro.spacy_model import load_spacy

    nlp = load_spacy(disable=["ner", "parser"])
    nlp.add_pipe("sentencizer")
    nlp.add_pipe("textdescriptives/readability")
    return nlp


@lru_cache(maxsize=512)
def _doc(text: str):
    return _nlp()(text[:100000])  # same cap parsed_doc/model.py use


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
    from lexical_diversity import lex_div

    doc = _doc(text)
    readability = float(doc._.readability.get("coleman_liau_index") or 0.0)
    content_lemmas = [t.lemma_.lower() for t in doc if t.is_alpha and t.pos_ in _CONTENT_POS]
    richness = float(lex_div.hdd(content_lemmas)) if len(content_lemmas) >= 2 else 0.0
    entropy = _shannon_entropy(doc)
    return readability, richness, entropy


# --- Metric (#88) ----------------------------------------------------------------------


class _RichnessMetric:
    """Readability/richness/entropy axis as a `Metric`. `extract` returns
    (coleman_liau_index, hdd, shannon_entropy) for one raw document."""

    name = "richness"
    axes = ("readability", "richness", "entropy")
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
