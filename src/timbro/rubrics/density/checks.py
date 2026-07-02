"""Rule definitions for the density rubric (#5): lexical density + jargon.

Recall-first: prefer false positives; the LLM consumer judges each finding itself. See
CLAUDE.md's rubric design policy — never suppress a finding to look precise.
"""

from __future__ import annotations

from wordfreq import zipf_frequency

from timbro.rubrics.base import RubricFinding
from timbro.rubrics.features import DocumentView

# Mirrors rules.MAX_FINDINGS_PER_RULE: cap per-rule findings for payload size, not
# precision — the LLM consumer filters false positives itself.
MAX_FINDINGS_PER_RULE = 10

# padding_paragraph (#5 spec): paragraphs below this many alphabetic tokens are too short
# for a stable content-ratio estimate and are excluded from both the mean and the check.
_PADDING_MIN_TOKENS = 30
# Need at least this many qualifying paragraphs before "document mean ratio" is meaningful.
_PADDING_MIN_PARAGRAPHS = 2
# A paragraph fires when its ratio trails the qualifying-paragraph mean by more than this.
_PADDING_GAP = 0.08

# jargon_cluster (#5 spec): rare word = alphabetic, length >= 4, zipf < 3.0, POS != PROPN,
# not a leading word (#4), not an already-defined acronym.
_JARGON_MIN_WORD_LEN = 4
_JARGON_ZIPF_MAX = 3.0
_JARGON_MIN_DISTINCT_PER_SENTENCE = 3


def _emit(
    findings: list[RubricFinding],
    *,
    severity: str,
    dimension: str,
    rule: str,
    occurrences: list[tuple[int | None, int | None, str]],
    message,
) -> None:
    """One RubricFinding per occurrence (paragraph_idx, sentence_idx, span), 0-based
    internally, capped at MAX_FINDINGS_PER_RULE and converted to 1-based indices. Mirrors
    rules._emit (kept local rather than imported so this module has no dependency on the
    concurrently-edited rules.py)."""
    for pi, si, span in occurrences[:MAX_FINDINGS_PER_RULE]:
        findings.append(
            RubricFinding(
                severity,
                dimension,
                rule,
                pi + 1 if pi is not None else None,
                si + 1 if si is not None else None,
                span[:220],
                message(span) if callable(message) else message,
            )
        )


def _padding_paragraphs(doc: DocumentView) -> list[tuple[int, None, str]]:
    ratios = doc.paragraph_content_ratios(min_tokens=_PADDING_MIN_TOKENS)
    if len(ratios) < _PADDING_MIN_PARAGRAPHS:
        return []
    mean_ratio = sum(ratio for _, ratio in ratios) / len(ratios)
    threshold = mean_ratio - _PADDING_GAP
    return [
        (pi, None, doc.paragraphs[pi][:220]) for pi, ratio in ratios if ratio < threshold
    ]


def _rare_words_by_sentence(doc: DocumentView) -> list[tuple[int, int, list[str]]]:
    leading_lemmas = {item["lemma"] for item in doc.leading_words}
    defined = doc.defined_acronyms
    out: list[tuple[int, int, list[str]]] = []
    for pi, si, tokens in doc.sentence_tokens():
        rare: list[str] = []
        seen_lower: set[str] = set()
        for tok in tokens:
            word = tok.text
            if len(word) < _JARGON_MIN_WORD_LEN:
                continue
            if tok.pos_ == "PROPN":
                continue
            if word in defined:
                continue
            if tok.lemma_.lower() in leading_lemmas:
                continue
            lw = word.lower()
            if lw in seen_lower:
                continue
            if zipf_frequency(lw, "en") >= _JARGON_ZIPF_MAX:
                continue
            seen_lower.add(lw)
            rare.append(word)
        if len(rare) >= _JARGON_MIN_DISTINCT_PER_SENTENCE:
            out.append((pi, si, rare))
    return out


def density_findings(doc: DocumentView) -> list[RubricFinding]:
    findings: list[RubricFinding] = []

    _emit(
        findings,
        severity="low",
        dimension="density",
        rule="padding_paragraph",
        occurrences=_padding_paragraphs(doc),
        message="Filler-heavy stretch: this paragraph's content-word ratio trails the "
        "document mean; tighten it or cut it.",
    )

    _emit(
        findings,
        severity="medium",
        dimension="jargon",
        rule="jargon_cluster",
        occurrences=[
            (pi, si, ", ".join(words)) for pi, si, words in _rare_words_by_sentence(doc)
        ],
        message=lambda span: (
            f"Sentence clusters {len(span.split(', '))} rare/technical terms ({span}); "
            "make sure the jargon earns its keep or unpack it for the reader."
        ),
    )

    return findings
