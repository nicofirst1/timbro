"""The `slop` rubric: deterministic AI-writing tells (em-dashes, "not X but Y",
delve/tapestry diction, curly quotes, staccato rhythm, ...) surfaced through the same
findings/verdict machinery as `check`. No model, no voice corpus, no LLM-as-judge.

The detectors live in `timbro.tells` (they also feed the voice `score` direction as
lexical features); this module just turns their spans into RubricFindings. Recall-first,
like every rubric: prefer false positives and let the consumer filter — see CLAUDE.md.
"""

from __future__ import annotations

from timbro.rubrics.base import RubricFinding
from timbro.tells import TELL_LABEL, TELL_NAMES, TELL_PRIOR, tell_occurrences

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


def _severity(prior: float) -> str:
    # Severity tracks the tell's reliability (TELL_PRIOR, from the Reddit frequency study):
    # em-dash / not-X-Y / diction are the load-bearing tells, so they carry the most weight.
    return "high" if prior >= 0.5 else "medium" if prior >= 0.3 else "low"


def tell_findings(text: str) -> list[RubricFinding]:
    # One finding per tell, not per occurrence: a tell carries no location (paragraph /
    # sentence are None), so N rows for one tell would just repeat. The count lives in the
    # message; the span quotes the first hit as an example. Penalty is per-rule anyway.
    findings: list[RubricFinding] = []
    occ = tell_occurrences(text)
    for name in TELL_NAMES:
        spans = occ[name]
        if not spans:
            continue
        message = (
            f"{len(spans)}× {TELL_LABEL[name]} — a deterministic AI-writing tell; cut or vary it."
        )
        findings.append(
            RubricFinding(
                _severity(TELL_PRIOR[name]), DIMENSION[name], name, None, None,
                spans[0].strip()[:220], message,
            )
        )
    return findings
