"""Tunable lexicons, declared priors, and corpus defaults, in one place.

What belongs here: hand-curated lexicons/phrase lists (hedge/booster, AI-tell
diction), declared `Reference` priors for each scalar axis (the "expected value"
a metric judges a draft against with no corpus), and the packaged-sample corpus
paths. All of it is relocated byte-identical from the modules that used to define
it inline (PR #57 review) -- this is a move, not a retune.

What does NOT belong here: detector/extractor code (regexes with matching logic,
POS predicates, the `_count_*`/`*_rates` functions), scoring weights (`_PENALTY`,
`_WEIGHTS`), verdict thresholds in `report.py`, or the structural zero-placeholder
references (`TELL_REFERENCE`, `MARKDOWN_REFERENCE`) -- those derive their length
from an axis-name tuple and live next to it, so the two can't drift apart.
"""

from __future__ import annotations

from pathlib import Path

from timbro.metric import Reference

# --- hedge.py: hedge / booster stance axis (#44) --------------------------------------

# Single-lemma items: lemma -> POS tags that disambiguate it, or None if the lemma has
# no ordinary-prose reading worth gating (most of them -- POS would only add a false
# negative). Curated from Hyland's published hedge/booster lists; kept short.
HEDGE_LEMMAS: dict[str, set[str] | None] = {
    "may": {"AUX"}, "might": {"AUX"}, "could": {"AUX"},
    "perhaps": None, "possibly": None, "seem": None, "appear": None, "suggest": None,
    "arguably": None, "somewhat": None, "fairly": None, "relatively": None,
    "likely": None, "presumably": None, "roughly": None,
}
# Multi-word hedges: lemma sequence of consecutive tokens.
HEDGE_PHRASES: tuple[tuple[str, ...], ...] = (
    ("I", "think"), ("I", "believe"),
)

BOOSTER_LEMMAS: dict[str, set[str] | None] = {
    "clearly": None, "obviously": None, "certainly": None, "definitely": None,
    "undoubtedly": None, "always": None, "never": None, "indeed": None,
    "must": {"AUX"},
}
BOOSTER_PHRASES: tuple[tuple[str, ...], ...] = (
    ("of", "course"), ("in", "fact"), ("without", "doubt"),
)

# Proposed prior, NOT copied from tells.py's "clean prose ~ 0" pattern -- hedges and
# boosters are a normal feature of English non-fiction prose, not an AI-slop marker.
# Order-of-magnitude reasoning: a few hedges/boosters per 1000 words is typical running
# prose (an occasional "might"/"clearly" per paragraph); dozens/1000 would read as
# either mealy-mouthed or bombastic. mean=6.0 hedge / 4.0 booster, spread=4.0 both,
# reflects hedges being slightly more common than boosters in careful prose (Hyland's
# corpora skew the same way). strength=2.0: a modest pseudo-count so a 5+ doc profile
# corpus dominates, but the axis still reports something sane with zero corpus.
# PROPOSED -- flagged in the PR body for maintainer confirmation.
HEDGE_BOOSTER_REFERENCE = Reference(
    mean=(6.0, 4.0),
    spread=(4.0, 4.0),
    strength=2.0,
)


# --- tells.py: AI-tell declared priors -------------------------------------------------

# Confidence floor in [0,1], seeded from the Reddit study's citation frequency:
# em-dash is "the single most reliable tell"; "not X but Y" is the named "AI accent".
TELL_PRIOR = {
    "dash": 0.70, "not_x_y": 0.55, "diction": 0.50, "sycophancy": 0.40,
    "signpost": 0.35, "hr_divider": 0.35, "conclusion": 0.30, "emoji": 0.30,
    "rhetorical_opener": 0.30, "bold_leadin": 0.25, "rule_of_three": 0.25,
    "filler": 0.25, "aphorism": 0.25, "curly_quote": 0.20,
    "dropped_subject": 0.35, "empty_punch": 0.30, "staccato_run": 0.30,
    "quote_punct": 0.25, "colon_list": 0.22,
}

# --- model.py: packaged-sample corpus defaults ------------------------------------------

# Packaged sample corpus -- makes the plugin run on install (override via env for a real voice).
_SAMPLE = Path(__file__).parent / "sample"
DEFAULT_EXEMPLARS = _SAMPLE / "exemplars"
DEFAULT_CONTRAST = _SAMPLE / "contrast"


# --- concreteness.py: concreteness axis prior (#46) -------------------------------------

# Proposed prior, derived (not copied) from the packaged sample voice (src/timbro/sample/
# exemplars/ + contrast/, 7 short posts covering both a plain-spoken voice and its
# corporate-jargon contrast -- the closest thing in-repo to a general English-prose
# baseline). Per-doc mean_concreteness across all 7: 2.69-3.02, mean=2.85, stdev=0.099
# (see PR body for the exact numbers). spread=0.30 here widens that empirical stdev --
# 7 docs is too few to trust a tight 0.10 as the population spread, and hedge.py's own
# prior derivation reasons the same way (round toward a plausible order of magnitude
# rather than overfit a small-n empirical std). strength=2.0, matching hedge's modest
# pseudo-count: enough for a 5+ doc profile corpus to dominate, while still reporting
# something sane with zero corpus. PROPOSED -- flagged in the PR body for maintainer
# confirmation.
CONCRETENESS_REFERENCE = Reference(
    mean=(2.85,),
    spread=(0.30,),
    strength=2.0,
)


# --- fw.py: function-word axis prior (#45) ----------------------------------------------

# Empirically derived (unlike hedge.py's #44 hand-reasoned prior): function-word POS
# rates are high-frequency grammatical categories -- many occurrences per document even
# in a small corpus -- unlike hedge.py's sparse lexical-choice counts, where a 7-doc
# sample is too noisy to trust a mean over (that's exactly why hedge.py used
# order-of-magnitude reasoning instead of a corpus mean). So this prior IS computed from
# the packaged sample corpus, matching hedge.py's convention in spirit (propose numbers,
# flag for review, modest strength) but not its literal derivation mechanism.
#
# Dataset: src/timbro/sample/exemplars/ (3 docs) + src/timbro/sample/contrast/ (4 docs),
# combined, N=7. Statistic: mean (and population stdev for spread) of the per-doc rate,
# computed via `function_word_rates` itself (same word-count denominator as the shipped
# extractor, punctuation excluded).
#   first_person_sg:   mean=35.30   pstdev=36.01
#   article_rate:      mean=104.85  pstdev=29.15
#   preposition_rate:  mean=72.30   pstdev=22.69
#   conjunction_rate:  mean=50.24   pstdev=20.16
#   pronoun_rate:      mean=113.21  pstdev=26.22
# strength=2.0: reuses hedge.py's literal value -- same "modest pseudo-count" role, no
# documented reason found to pick a different number for this axis.
# PROPOSED -- flagged in the PR body for maintainer confirmation.
FUNCTION_WORD_REFERENCE = Reference(
    mean=(35.30, 104.85, 72.30, 50.24, 113.21),
    spread=(36.01, 29.15, 22.69, 20.16, 26.22),
    strength=2.0,
)
