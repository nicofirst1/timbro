"""Politeness strategies axis (#94): Danescu-Niculescu-Mizil et al. 2013's 20 politeness
markers, hand-rolled as lemma/POS/pattern matches over the shared cached spaCy `Doc`.

The paper ("A computational approach to politeness with application to social factors")
scores a single utterance against 20 lexical/syntactic strategies -- no dialogue pair
required. ConvoKit ships the same 20 features but drags in matplotlib/pandas/nltk/
pymongo/h5py/datasets/sentence-transformers for one 20-feature scorer (rejected, issue
#94 decision record 2026-08-25); hand-rolling at `hedge.py` scale needs none of that.

Request/address-oriented strategies (greetings, gratitude, deference, hedges, direct/
indirect framing) are correspondence signal (email, professional messaging) with little
reason to fire in narrative or expository prose -- a blog post rarely says "thanks" or
"could you". So this axis reports STANDALONE (never feeds the embedding distance or POS
direction, same as hedge.py/fw.py) and ships Tier C (manual/reporting-only, ADR-0005):
no declared prior, no z-score, no separation claim. When zero of the 20 strategies fire
on a draft, `politeness_report` returns None -- "not applicable" beats a confident
number computed from nothing. The gate is a bare feature count, not a new threshold.

Matching is lemma + POS over the shared Doc, not regex, for the same reason hedge.py
gives: a few lemmas need POS to disambiguate ("thanks" the plural noun vs "Thanks" the
interjection use both read the same lemma) and capitalized clause-initial words can
mis-tag under the pinned tagger -- lemma-on-lowered-text is the robust axis, POS only
where a lemma is genuinely ambiguous.
"""

from __future__ import annotations

from functools import lru_cache

from timbro.metric import Reference, parsed_doc, register

# --- lexicons --------------------------------------------------------------------------
# Small, hand-curated sets per DNM's Table 3 categories. Kept short like hedge.py's
# HEDGE_LEMMAS -- these are marker words, not an exhaustive sentiment lexicon.

_GRATITUDE = {"thank", "thanks", "appreciate", "grateful"}
_DEFERENCE = {"great", "awesome", "good", "nice", "excellent", "impressive", "cool"}
_GREETING = {"hi", "hello", "hey", "greetings"}
_POSITIVE = {"good", "great", "glad", "happy", "pleased", "wonderful", "excellent", "love", "like"}
_NEGATIVE = {"bad", "wrong", "sorry", "problem", "issue", "fail", "unfortunately", "hate", "terrible"}
_APOLOGY = {"sorry", "apologize", "apologise", "excuse", "forgive"}
_FACTUALITY = {"actually", "fact", "really", "truth"}
_HEDGE = {"maybe", "perhaps", "possibly", "probably", "might", "could", "seem", "suggest"}
_1P_PLURAL = {"we", "us", "our", "ours", "ourselves"}
_1P = {"i", "me", "my", "mine", "myself"}
_2P = {"you", "your", "yours", "yourself", "yourselves"}
_INDIRECTION_PHRASES = (("by", "the", "way"), ("incidentally",))
_DIRECT_STARTERS = {"so", "now", "look", "listen"}
_WH_WORDS = {"what", "when", "where", "why", "how", "who", "which"}


def _sent_tokens(sent):
    return [t for t in sent if not t.is_space and not t.is_punct]


@lru_cache(maxsize=512)
def politeness_counts(text: str) -> dict[str, int]:
    """Count of each of DNM's 20 strategies firing in `text`. Keys are the strategy names
    used in the report; values are raw occurrence counts (not rate-normalised -- these
    are sparse binary-ish markers, a per-1000-word rate would be noise at draft length)."""
    doc = parsed_doc(text)
    counts = dict.fromkeys(
        (
            "gratitude", "deference", "greeting", "positive_lexicon", "negative_lexicon",
            "apologizing", "please", "please_start", "indirect_btw", "direct_question",
            "direct_start", "counterfactual_modal", "indicative_modal", "first_person_start",
            "first_person_plural", "first_person", "second_person", "second_person_start",
            "hedges", "factuality",
        ),
        0,
    )

    lemmas_all = [t.lemma_.lower() for t in doc if not t.is_space]
    for i in range(len(lemmas_all)):
        for phrase in _INDIRECTION_PHRASES:
            if tuple(lemmas_all[i : i + len(phrase)]) == phrase:
                counts["indirect_btw"] += 1

    for sent in doc.sents:
        toks = _sent_tokens(sent)
        if not toks:
            continue
        lemmas = [t.lemma_.lower() for t in toks]
        first = toks[0]
        first_lemma = first.lemma_.lower()
        is_question = sent.text.strip().endswith("?")

        for lemma in lemmas:
            if lemma in _GRATITUDE:
                counts["gratitude"] += 1
            if lemma in _DEFERENCE:
                counts["deference"] += 1
            if lemma in _GREETING:
                counts["greeting"] += 1
            if lemma in _POSITIVE:
                counts["positive_lexicon"] += 1
            if lemma in _NEGATIVE:
                counts["negative_lexicon"] += 1
            if lemma in _APOLOGY:
                counts["apologizing"] += 1
            if lemma == "please":
                counts["please"] += 1
            if lemma in _FACTUALITY:
                counts["factuality"] += 1
            if lemma in _HEDGE:
                counts["hedges"] += 1
            if lemma in _1P_PLURAL:
                counts["first_person_plural"] += 1
            if lemma in _1P:
                counts["first_person"] += 1
            if lemma in _2P:
                counts["second_person"] += 1

        if first_lemma == "please":
            counts["please_start"] += 1
        if first_lemma in _DIRECT_STARTERS or (first.pos_ == "VERB" and first.tag_ == "VB"):
            counts["direct_start"] += 1  # imperative or blunt discourse-marker opener
        if first_lemma == "i":
            counts["first_person_start"] += 1
        if first_lemma in {"you", "your"}:
            counts["second_person_start"] += 1
        if is_question and first_lemma in _WH_WORDS:
            counts["direct_question"] += 1
        if is_question and first.pos_ == "AUX":
            if first_lemma in {"could", "would"}:
                counts["counterfactual_modal"] += 1
            elif first_lemma in {"can", "will"}:
                counts["indicative_modal"] += 1

    return counts


def politeness_total(text: str) -> int:
    """Total strategy firings across the 20 categories -- the N/A gate is `== 0`."""
    return sum(politeness_counts(text).values())


def politeness_report(text: str) -> dict | None:
    """Reporting-only view of the axis for one draft: `None` ("not applicable") when zero
    of the 20 strategies fire, otherwise which strategies fired and how often. The gate is
    a bare count (`total == 0`), not a new tuned threshold -- correspondence-flavored text
    fires several strategies, narrative/expository prose typically fires none (issue #94
    decision record). No z-score, no reference, no distance: this axis makes no scored
    claim (Tier C, ADR-0005) until a correspondence-flavored corpus exists to validate on.
    """
    counts = politeness_counts(text)
    total = sum(counts.values())
    if total == 0:
        return None
    return {"total": total, "strategies": {k: v for k, v in counts.items() if v > 0}}


# --- Metric (#94) ------------------------------------------------------------------------
# No declared prior: Tier C reporting-only per the issue's decision record -- a Reference
# mean/spread would assert a separation claim the mini-validation doesn't support. Zero
# strength, zero mean/spread (same "structural neutral placeholder" shape model.py's
# MARKDOWN_REFERENCE uses) so this never contributes a scored claim if something upstream
# ever blends it; the report path (politeness_report, added by the caller) uses the N/A
# gate instead of this reference.
POLITENESS_REFERENCE = Reference(
    mean=tuple(0.0 for _ in range(20)),
    spread=tuple(1.0 for _ in range(20)),
    strength=0.0,
)

class _PolitenessMetric:
    """Politeness-strategies axis as a `Metric`. `extract` returns the 20 raw strategy
    counts for one raw document, in a fixed order. Standalone reported axis -- never feeds
    the embedding distance or POS direction (see module docstring)."""

    name = "politeness"
    axes = (
        "gratitude", "deference", "greeting", "positive_lexicon", "negative_lexicon",
        "apologizing", "please", "please_start", "indirect_btw", "direct_question",
        "direct_start", "counterfactual_modal", "indicative_modal", "first_person_start",
        "first_person_plural", "first_person", "second_person", "second_person_start",
        "hedges", "factuality",
    )
    prior = POLITENESS_REFERENCE

    def extract(self, text: str) -> tuple[float, ...]:
        counts = politeness_counts(text)
        return tuple(float(counts[name]) for name in self.axes)


POLITENESS_METRIC = register(_PolitenessMetric())


if __name__ == "__main__":
    # Self-check: a polite request fires several strategies; a narrative sentence with no
    # request/address content fires none -- that's the N/A gate (total == 0), not a blunt
    # imperative (which correctly fires direct_start -- DNM's impolite pole, not silence).
    polite = (
        "Hi Sam, thanks so much for your help yesterday. Could you please send over "
        "the updated file when you get a chance? I really appreciate it, and sorry "
        "for the short notice. Let me know if you need anything from me."
    )
    narrative = "The cat sat by the door. It was small and grey outside today."
    p_counts = politeness_counts(polite)
    p_total = sum(p_counts.values())
    assert p_total > 5, p_counts
    assert p_counts["gratitude"] > 0, p_counts
    assert p_counts["please"] > 0, p_counts
    assert p_counts["counterfactual_modal"] > 0, p_counts
    assert politeness_report(narrative) is None, politeness_counts(narrative)
    print(f"ok: polite fires {p_total} strategies ({sum(1 for v in p_counts.values() if v)} distinct); "
          f"narrative prose fires 0 -> politeness_report returns None (N/A)")
