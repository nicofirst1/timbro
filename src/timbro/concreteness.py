"""Concreteness axis (#46): abstract<->concrete style dimension via Brysbaert norms.

Brysbaert, Warriner & Kuperman (2014) rated ~37k English word lemmas 1 (abstract,
"idea") to 5 (concrete, "hammer") by crowdsourced survey. This axis looks up each
content-word lemma in a draft against that table and averages the hits: a draft that
leans on concrete nouns/verbs ("the rusty hammer hit the oak table") scores higher than
one that leans on abstractions ("the underlying framework enables systemic value").
Norms file provenance/license: `src/timbro/norms/NOTICE.md`.

Lemmatised via the shared cached `metric.parsed_doc` (spaCy tagger+lemmatizer), same
parse hedge.py uses -- one Doc per draft, not a second pipeline. Only content-word POS
(NOUN/VERB/ADJ/ADV) are looked up; function words (determiners, prepositions...) have
no useful concreteness rating and aren't in the norms table's intended use anyway.
Out-of-vocabulary lemmas are skipped, not imputed -- a near-zero-coverage draft (all
proper nouns, code, non-English) should read as low-confidence, not silently averaged
to some default. Coverage is returned alongside the mean so a caller can judge that.
"""

from __future__ import annotations

import csv
import gzip
from functools import lru_cache
from pathlib import Path

from timbro.config import CONCRETENESS_REFERENCE
from timbro.metric import parsed_doc, register

_CONTENT_POS = {"NOUN", "VERB", "ADJ", "ADV"}
# Package-relative, same convention as model.py's `_SAMPLE = Path(__file__).parent /
# "sample"` -- resolves against the installed package dir, not CWD, so the plugin cache
# sandbox and any CWD find it the same way.
_NORMS_PATH = Path(__file__).parent / "norms" / "concreteness_brysbaert2014.csv.gz"


@lru_cache(maxsize=1)
def _norms() -> dict[str, float]:
    """Lazy-loaded lemma -> concreteness (1-5) lookup. Loaded once per process, only
    when this axis is actually used (no import-time cost for callers that skip it)."""
    with gzip.open(_NORMS_PATH, "rt", newline="") as f:
        return {row["lemma"]: float(row["concreteness"]) for row in csv.DictReader(f)}


@lru_cache(maxsize=512)
def concreteness_stats(text: str) -> tuple[float, float]:
    """(mean_concreteness, coverage): mean over content-word lemmas found in the norms
    table (0.0 if none found), and coverage = fraction of content-word tokens that hit
    the table (0.0-1.0, informational -- callers can flag a near-zero-coverage draft)."""
    norms = _norms()
    doc = parsed_doc(text)
    hits = []
    content_tokens = 0
    for tok in doc:
        if tok.pos_ not in _CONTENT_POS:
            continue
        content_tokens += 1
        score = norms.get(tok.lemma_.lower())
        if score is not None:
            hits.append(score)
    mean = sum(hits) / len(hits) if hits else 0.0
    coverage = len(hits) / content_tokens if content_tokens else 0.0
    return mean, coverage


# --- Metric (#43/#46) -----------------------------------------------------------------
# CONCRETENESS_REFERENCE lives in config.py now (PR #57 review); re-imported above.


class _ConcretenessMetric:
    """Concreteness axis as a `Metric`. `extract` returns (mean_concreteness,) for one
    raw document, per-lemma norms averaged over content words. Standalone axis group --
    does not feed the embedding distance or POS direction (issue #46)."""

    name = "concreteness"
    axes = ("mean_concreteness",)
    prior = CONCRETENESS_REFERENCE

    def extract(self, text: str) -> tuple[float, ...]:
        mean, _coverage = concreteness_stats(text)
        return (mean,)


CONCRETENESS_METRIC = register(_ConcretenessMetric())


if __name__ == "__main__":
    # Self-check: a concrete string scores higher mean_concreteness than an abstract one.
    concrete = "The rusty hammer hit the oak table."
    abstract = "The underlying framework enables systemic value."
    c_score, c_cov = concreteness_stats(concrete)
    a_score, a_cov = concreteness_stats(abstract)
    assert c_score > a_score, (c_score, a_score)
    assert c_cov > 0 and a_cov > 0, (c_cov, a_cov)
    print(f"ok: concrete={c_score:.2f} (cov {c_cov:.2f}) > abstract={a_score:.2f} (cov {a_cov:.2f})")
