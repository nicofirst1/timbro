"""Hedge / booster stance axis (#44): how much a draft softens vs sharpens its claims.

Hyland's metadiscourse taxonomy names two opposed families of stance marker: hedges
("might", "perhaps", "seems") soften a claim's certainty; boosters ("clearly",
"must", "in fact") sharpen it. Neither is good or bad prose -- they are a dial a
writer sets on purpose, and a voice has a resting position on that dial. This axis
measures where a draft sits, per-1000-words, the same length-normalised way
`tells.py::tell_rates` does, and reports it standalone (it does not feed the
embedding distance or POS direction -- see `metric.MARKDOWN`-style axes in model.py
for the precedent).

Matching is lemma + POS over the shared cached Doc (`metric.parsed_doc`), not regex:
a few lemmas have a genuine non-hedge/non-booster reading in ordinary prose ("might"
the noun vs "might" the modal, "must" the noun vs the modal, "may" the month), and
POS is the only reliable disambiguator for those. Every other lemma matches on the
lemma alone -- gating POS on every token would just reintroduce the tagger's
clause-initial-capitalization fragility (a known spaCy weak spot) as a false
negative source.
"""

from __future__ import annotations

import re
from functools import lru_cache

from timbro.metric import Reference, parsed_doc, register

_WORD = re.compile(r"\b\w+\b")

# Single-lemma items: lemma -> POS tags that disambiguate it, or None if the lemma has
# no ordinary-prose reading worth gating (most of them -- POS would only add a false
# negative). Curated from Hyland's published hedge/booster lists; kept short.
_HEDGE_LEMMAS: dict[str, set[str] | None] = {
    "may": {"AUX"}, "might": {"AUX"}, "could": {"AUX"},
    "perhaps": None, "possibly": None, "seem": None, "appear": None, "suggest": None,
    "arguably": None, "somewhat": None, "fairly": None, "relatively": None,
    "likely": None, "presumably": None, "roughly": None,
}
# Multi-word hedges: lemma sequence of consecutive tokens.
_HEDGE_PHRASES: tuple[tuple[str, ...], ...] = (
    ("I", "think"), ("I", "believe"),
)

_BOOSTER_LEMMAS: dict[str, set[str] | None] = {
    "clearly": None, "obviously": None, "certainly": None, "definitely": None,
    "undoubtedly": None, "always": None, "never": None, "indeed": None,
    "must": {"AUX"},
}
_BOOSTER_PHRASES: tuple[tuple[str, ...], ...] = (
    ("of", "course"), ("in", "fact"), ("without", "doubt"),
)


def _count_lemmas(doc, lemmas: dict[str, set[str] | None]) -> int:
    n = 0
    for tok in doc:
        lemma = tok.lemma_.lower()
        if lemma not in lemmas:
            continue
        gate = lemmas[lemma]
        if gate and tok.pos_ not in gate:
            continue
        n += 1
    return n


def _count_phrases(doc, phrases: tuple[tuple[str, ...], ...]) -> int:
    lemmas = [tok.lemma_.lower() for tok in doc if not tok.is_space]
    n = 0
    for phrase in phrases:
        plen = len(phrase)
        target = [p.lower() for p in phrase]
        for i in range(len(lemmas) - plen + 1):
            if lemmas[i : i + plen] == target:
                n += 1
    return n


@lru_cache(maxsize=512)
def hedge_booster_rates(text: str) -> tuple[float, float]:
    """(hedge_rate, booster_rate), each occurrences per 1000 word-tokens."""
    doc = parsed_doc(text)
    n = len(_WORD.findall(text)) or 1
    hedges = _count_lemmas(doc, _HEDGE_LEMMAS) + _count_phrases(doc, _HEDGE_PHRASES)
    boosters = _count_lemmas(doc, _BOOSTER_LEMMAS) + _count_phrases(doc, _BOOSTER_PHRASES)
    return 1000 * hedges / n, 1000 * boosters / n


# --- Metric (#43/#44) ----------------------------------------------------------------
# Proposed prior, NOT copied from tells.py's "clean prose ~ 0" pattern -- hedges and
# boosters are a normal feature of English non-fiction prose, not an AI-slop marker.
# Order-of-magnitude reasoning: a few hedges/boosters per 1000 words is typical running
# prose (an occasional "might"/"clearly" per paragraph); dozens/1000 would read as
# either mealy-mouthed or bombastic. mean=6.0 hedge / 4.0 booster, spread=4.0 both,
# reflects hedges being slightly more common than boosters in careful prose (Hyland's
# corpora skew the same way). strength=2.0: a modest pseudo-count so a 5+ doc profile
# corpus dominates, but the axis still reports something sane with zero corpus.
# PROPOSED -- flagged in the PR for @nicofirst1 to confirm or adjust.
HEDGE_BOOSTER_REFERENCE = Reference(
    mean=(6.0, 4.0),
    spread=(4.0, 4.0),
    strength=2.0,
)


class _HedgeBoosterMetric:
    """Hedge/booster stance axis as a `Metric`. `extract` returns (hedge_rate,
    booster_rate) per-1000-words for one raw document."""

    name = "hedge"
    axes = ("hedge_rate", "booster_rate")
    prior = HEDGE_BOOSTER_REFERENCE

    def extract(self, text: str) -> tuple[float, ...]:
        return hedge_booster_rates(text)


HEDGE_BOOSTER_METRIC = register(_HedgeBoosterMetric())


if __name__ == "__main__":
    # Self-check: a hedge-heavy string scores higher hedge_rate than a blunt one, and
    # the blunt one scores higher booster_rate.
    hedgy = ("I think this might work, though it could possibly fail. It seems fine "
             "and perhaps arguably fair; the data suggests a somewhat likely outcome.")
    blunt = ("This clearly works. It is obviously correct and must succeed. Of course "
             "it is certain -- in fact, without doubt, it always does.")
    h_hedgy, b_hedgy = hedge_booster_rates(hedgy)
    h_blunt, b_blunt = hedge_booster_rates(blunt)
    assert h_hedgy > h_blunt, (h_hedgy, h_blunt)
    assert b_blunt > b_hedgy, (b_blunt, b_hedgy)
    print(f"ok: hedgy hedge_rate={h_hedgy:.1f} > blunt={h_blunt:.1f}; "
          f"blunt booster_rate={b_blunt:.1f} > hedgy={b_hedgy:.1f}")
