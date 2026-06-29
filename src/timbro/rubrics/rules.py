from __future__ import annotations

from timbro.rubrics.base import RubricFinding
from timbro.rubrics.features import DocumentView


def schimel_findings(doc: DocumentView) -> list[RubricFinding]:
    findings: list[RubricFinding] = []

    if doc.opening_problem_score() == 0:
        findings.append(RubricFinding("high", "opening", "opening_problem_present", 1, None, doc.opening_text()[:220], "Opening does not clearly frame an important problem."))
    if doc.opening_method_score() > doc.opening_problem_score():
        findings.append(RubricFinding("medium", "opening", "opening_not_method_first", 1, None, doc.opening_text()[:220], "Opening leans on methods more than on the problem."))

    if doc.sections.challenge_paragraph is None:
        findings.append(RubricFinding("high", "challenge", "challenge_present", None, None, "", "No concrete challenge paragraph was detected."))
    elif doc.objective_only():
        findings.append(RubricFinding("high", "challenge", "objective_only_challenge", doc.sections.challenge_paragraph + 1, None, doc.challenge_text()[:220], "States objectives but does not pose a concrete question or gap."))

    if doc.weak_resolution():
        findings.append(RubricFinding("high", "resolution", "weak_resolution", doc.sections.resolution_paragraphs[0] + 1 if doc.sections.resolution_paragraphs else None, None, doc.resolution_text()[:220], "Resolution falls back to generic future-work language instead of a concrete conclusion."))
    if doc.challenge_resolution_similarity() < 0.20:
        findings.append(RubricFinding("high", "resolution", "challenge_answered", doc.sections.resolution_paragraphs[0] + 1 if doc.sections.resolution_paragraphs else None, None, doc.resolution_text()[:220], "Resolution does not appear to answer the challenge."))
    if doc.opening_resolution_similarity() < 0.15:
        findings.append(RubricFinding("medium", "resolution", "closing_the_circle", doc.sections.resolution_paragraphs[0] + 1 if doc.sections.resolution_paragraphs else None, None, doc.resolution_text()[:220], "Resolution does not clearly reconnect to the opening problem."))

    acronyms = doc.undefined_acronyms()
    if acronyms:
        findings.append(RubricFinding("medium", "clarity", "undefined_acronyms", None, None, ", ".join(acronyms[:8]), "Uses acronyms without defining them for readers."))
    if doc.fuzzy_verb_density() > 6:
        findings.append(RubricFinding("medium", "sentences", "fuzzy_verb_density", None, None, "", "Uses many weak process verbs instead of stronger action verbs."))
    if doc.nominalization_density() > 35:
        findings.append(RubricFinding("medium", "sentences", "nominalization_density", None, None, "", "Uses heavy nominalization density that can flatten action."))
    if doc.noun_trains() > 2:
        findings.append(RubricFinding("low", "clarity", "noun_trains", None, None, "", "Contains several dense noun trains."))

    sims = doc.adjacent_paragraph_similarity()
    if sims and min(sims) < 0.25:
        idx = sims.index(min(sims))
        findings.append(RubricFinding("medium", "flow", "paragraph_drift", idx + 2, None, doc.paragraphs[idx + 1][:220], "A paragraph shift appears abrupt or weakly connected."))

    for i, para in enumerate(doc.paragraphs, start=1):
        if len(doc.sentences[i - 1]) >= 3 and doc.paragraph_internal_similarity(i - 1) < 0.25:
            findings.append(RubricFinding("medium", "paragraphs", "point_nowhere_paragraph", i, None, para[:220], "Paragraph appears to bundle multiple weakly connected points."))
            break

    return findings
