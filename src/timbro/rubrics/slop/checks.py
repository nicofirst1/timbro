"""The `slop` rubric: deterministic AI-writing tells (em-dashes, "not X but Y",
delve/tapestry diction, curly quotes, staccato rhythm, ...) surfaced through the same
findings/verdict machinery as `check`. No model, no voice corpus, no LLM-as-judge.

The detectors live in `timbro.tells` (they also feed the voice `score` direction as
lexical features); this module just turns their spans into RubricFindings. Recall-first,
like every rubric: prefer false positives and let the consumer filter — see CLAUDE.md.
"""

from __future__ import annotations

from timbro.rubrics.base import RubricFinding
from timbro.tells import TELL_LABEL, TELL_NAMES, TELL_PRIOR, tell_occurrences, tell_rates

# Each tell rolls up under one report dimension. Grouped by what the reader would fix:
# word choice, phrase templates, sentence cadence, surface markup.
DIMENSION = {
    "diction": "diction", "filler": "diction", "aphorism": "diction",
    "rule_of_three": "diction",
    "not_x_y": "construction", "signpost": "construction", "conclusion": "construction",
    "sycophancy": "construction", "rhetorical_opener": "construction",
    "empty_punch": "rhythm", "dropped_subject": "rhythm", "staccato_run": "rhythm",
    "dash": "formatting", "emoji": "formatting", "curly_quote": "formatting",
    "bold_leadin": "formatting", "hr_divider": "formatting", "quote_punct": "formatting",
    "colon_list": "formatting",
}
DIMENSIONS = ("diction", "construction", "rhythm", "formatting")


# A draft must exceed its corpus's own rate for a tell by more than this many standard
# deviations before relative mode flags it — under that, it's within your normal usage.
_REL_FLAG_Z = 1.0


def _abs_severity(prior: float) -> str:
    # Absolute mode: severity tracks the tell's reliability (TELL_PRIOR, from the Reddit
    # study). em-dash / not-X-Y / diction are load-bearing, so they carry the most weight.
    return "high" if prior >= 0.5 else "medium" if prior >= 0.3 else "low"


def _rel_severity(z: float) -> str:
    # Relative mode: severity tracks how far the draft strays from its own corpus norm.
    return "high" if z >= 3 else "medium" if z >= 2 else "low"


def _finding(name: str, spans: list[str], severity: str, message: str) -> RubricFinding:
    # One finding per tell, not per occurrence: a tell carries no location (paragraph /
    # sentence are None), so N rows for one tell would just repeat. The count lives in the
    # message; the span quotes the first hit as an example. Penalty is per-rule anyway.
    return RubricFinding(severity, DIMENSION[name], name, None, None, spans[0].strip()[:220], message)


def tell_findings(text: str, baseline: dict[str, tuple[float, float]] | None = None) -> list[RubricFinding]:
    """AI-tell findings for `text`.

    Absolute mode (`baseline=None`): every tell that fires is slop, severity from its prior.
    Relative mode (`baseline` from `tell_baseline`): a tell fires only where the draft
    overuses it versus *your* corpus norm, severity from how far it strays.
    """
    occ = tell_occurrences(text)
    if baseline is None:
        return [
            _finding(
                name, spans, _abs_severity(TELL_PRIOR[name]),
                f"{len(spans)}× {TELL_LABEL[name]} — a deterministic AI-writing tell; cut or vary it.",
            )
            for name, spans in ((n, occ[n]) for n in TELL_NAMES) if spans
        ]

    rates = tell_rates(text)
    findings: list[RubricFinding] = []
    for name in TELL_NAMES:
        spans = occ[name]
        if not spans:
            continue
        mean, std = baseline[name]
        # Zero-variance corpus (a tell it never uses, or uses uniformly): 1 rate-unit
        # (one occurrence per 1000 words) sets the scale, matching model.py's std guard.
        z = (rates[f"tell_{name}"] - mean) / (std or 1.0)
        if z <= _REL_FLAG_Z:
            continue
        # A bucketed descriptor, not the raw z: short drafts extrapolate to large per-1000
        # rates, so the number looks absurd ("151σ"). Severity carries the real magnitude.
        descriptor = "far above" if z >= 3 else "well above" if z >= 2 else "above"
        message = (
            f"{len(spans)}× {TELL_LABEL[name]} — {descriptor} your corpus norm; "
            "pull back toward your own rate."
        )
        findings.append(_finding(name, spans, _rel_severity(z), message))
    return findings
