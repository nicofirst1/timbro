"""Function-word / analytical-thinking axis (#45): pronoun/article/preposition/
conjunction density as a voice fingerprint.

Function words (pronouns, articles, prepositions, conjunctions) are the classic style
discriminator from Chung & Pennebaker: harder to control deliberately than content
words, so they carry a strong voice signature. Article/preposition density correlates
with analytical thinking; first-person-singular correlates with status/self-focus
(Atlas Sec3.1). Pure POS predicates over the shared cached Doc (`metric.parsed_doc`) --
no lexicon, no new dependency -- reported standalone, the same way `hedge.py`/
`MARKDOWN_METRIC` axes are (see model.py): it does not feed the embedding distance or
POS direction/`_WEIGHTS`.

Five sub-axes, each a rate per 1000 word-tokens (same convention as hedge.py/tells.py):
first_person_sg, article_rate, preposition_rate, conjunction_rate, pronoun_rate. No
composite "analytical thinking" score is invented -- the direction ranking surfaces
which sub-axis is off, same principle as the hedge/booster axis staying two numbers
instead of one.
"""

from __future__ import annotations

import re
from functools import lru_cache

from timbro.config import FUNCTION_WORD_REFERENCE
from timbro.metric import parsed_doc, register

_WORD = re.compile(r"\b\w+\b")

_ARTICLES = {"a", "an", "the"}


@lru_cache(maxsize=512)
def function_word_rates(text: str) -> tuple[float, float, float, float, float]:
    """(first_person_sg, article_rate, preposition_rate, conjunction_rate, pronoun_rate),
    each occurrences per 1000 word-tokens."""
    doc = parsed_doc(text)
    n = len(_WORD.findall(text)) or 1
    first_person_sg = article = preposition = conjunction = pronoun = 0
    for tok in doc:
        if tok.pos_ == "PRON":
            pronoun += 1
            if tok.morph.get("Person") == ["1"] and tok.morph.get("Number") == ["Sing"]:
                first_person_sg += 1
        elif tok.pos_ == "DET" and tok.lower_ in _ARTICLES:
            article += 1
        elif tok.pos_ == "ADP":
            preposition += 1
        elif tok.pos_ in {"CCONJ", "SCONJ"}:
            conjunction += 1
    return (
        1000 * first_person_sg / n,
        1000 * article / n,
        1000 * preposition / n,
        1000 * conjunction / n,
        1000 * pronoun / n,
    )


# --- Metric (#43/#45) ----------------------------------------------------------------
# FUNCTION_WORD_REFERENCE lives in config.py now (PR #57 review); re-imported above.


class _FunctionWordMetric:
    """Function-word axis as a `Metric`. `extract` returns (first_person_sg,
    article_rate, preposition_rate, conjunction_rate, pronoun_rate) per-1000-words for
    one raw document."""

    name = "fw"
    axes = ("first_person_sg", "article_rate", "preposition_rate", "conjunction_rate", "pronoun_rate")
    prior = FUNCTION_WORD_REFERENCE

    def extract(self, text: str) -> tuple[float, ...]:
        return function_word_rates(text)


FUNCTION_WORD_METRIC = register(_FunctionWordMetric())


if __name__ == "__main__":
    # Self-check: a first-person-heavy string scores higher first_person_sg than an
    # impersonal one.
    personal = "I think my plan will help me. I own my mistakes and I fix my code."
    impersonal = "The system processes requests. The team reviews the code carefully."
    p_personal = function_word_rates(personal)
    p_impersonal = function_word_rates(impersonal)
    assert p_personal[0] > p_impersonal[0], (p_personal[0], p_impersonal[0])
    print(f"ok: personal first_person_sg={p_personal[0]:.1f} > impersonal={p_impersonal[0]:.1f}")
