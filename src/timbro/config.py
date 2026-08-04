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
    "filler": 0.25, "aphorism": 0.25, "self_narration": 0.25, "apologetic": 0.25,
    "curly_quote": 0.20,
    "dropped_subject": 0.35, "empty_punch": 0.30, "staccato_run": 0.30,
    "quote_punct": 0.25, "colon_list": 0.22,
}

# --- model.py: packaged-sample corpus defaults ------------------------------------------

# Packaged sample corpus -- makes the plugin run on install (override via env for a real voice).
_SAMPLE = Path(__file__).parent / "sample"
DEFAULT_EXEMPLARS = _SAMPLE / "exemplars"
DEFAULT_CONTRAST = _SAMPLE / "contrast"


# --- concreteness.py: concreteness axis prior (#46) -------------------------------------

# Mean and spread are derived from two different units, because they answer two
# different questions and the axis this feeds (concreteness.py:concreteness_stats)
# scores a whole draft as one averaged number:
#
# mean=2.7094: frequency-weighted over individual lemmas in the Brysbaert, Warriner &
# Kuperman (2014) concreteness norms (src/timbro/norms/concreteness_brysbaert2014.csv.gz,
# 37,058 lemmas -- see src/timbro/norms/NOTICE.md), weighted by the SUBTLEX-US
# occurrence count carried in the same team's original distribution file
# (mean = sum(freq*conc) / sum(freq), all 37,058 vendored lemmas joined).
#
# spread=0.2792: population stdev of DOCUMENT-level mean concreteness, not lemma-level
# -- model.py's z-score divides by this spread, so it has to be in the same unit the
# z-score consumes (how much a document's average concreteness varies, not how much
# individual words' ratings vary -- lemma-level spread is ~3.75x wider and would make
# every draft's z-score silently shrink toward zero). Measured by running the shipped
# concreteness_stats extractor over 750 x 1000-word chunks of the same 7-book
# Gutenberg corpus scripts/derive_fw_reference.py (#59) uses, header/footer stripped.
#
# scripts/derive_concreteness_prior.py reproduces both numbers (#58; supersedes the
# earlier 7-doc-sample-derived 2.85/0.30). strength=2.0 unchanged: still a modest
# pseudo-count, enough for a 5+ doc profile corpus to dominate while reporting
# something sane with zero corpus.
CONCRETENESS_REFERENCE = Reference(
    mean=(2.7094,),
    spread=(0.2792,),
    strength=2.0,
)


# --- fw.py: function-word axis prior (#45, recomputed #59) ------------------------------

# Recomputed from a public-domain corpus (#59) -- the original prior below was a mean
# over the packaged 7-doc sample, too few documents to trust as a general-English
# baseline. Empirically derived (function-word POS rates are high-frequency
# grammatical categories -- many occurrences even within a single ~1000-word chunk --
# unlike hedge.py's sparse lexical-choice counts, which stayed hand-reasoned for that
# reason). strength=2.0 kept unchanged (issue spec): matches hedge.py's modest
# pseudo-count role, no reason found to pick a different number for this axis.
#
# Dataset: 7 Project Gutenberg texts (4 fiction + 3 non-fiction, IDs and titles in
# scripts/derive_fw_reference.py), Gutenberg header/footer stripped, chunked into
# 750 documents of 1000 word-tokens each (768,906 words total). Statistic: mean (and
# population stdev for spread) of `function_word_rates` per chunk -- same extractor,
# same per-1000-word denominator as the shipped metric.
#   first_person_sg:   mean=27.42   pstdev=25.14   (was 35.30 / 36.01)
#   article_rate:      mean=80.52   pstdev=20.86   (was 104.85 / 29.15)
#   preposition_rate:  mean=122.57  pstdev=17.99   (was 72.30 / 22.69)
#   conjunction_rate:  mean=72.36   pstdev=13.46   (was 50.24 / 20.16)
#   pronoun_rate:      mean=112.81  pstdev=40.16   (was 113.21 / 26.22)
# Reproducible via `uv run python scripts/derive_fw_reference.py` (re-downloads the
# corpus and re-derives; network required at derivation time only).
FUNCTION_WORD_REFERENCE = Reference(
    mean=(27.42, 80.52, 122.57, 72.36, 112.81),
    spread=(25.14, 20.86, 17.99, 13.46, 40.16),
    strength=2.0,
)
