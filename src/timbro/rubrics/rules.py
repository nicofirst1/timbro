"""Rule definitions for the schimel rubric.

Recall-first: prefer false positives; the LLM consumer judges each finding itself. A
rule is demoted (never deleted) only when the M3 dashboard (#8) shows it's noisy on
known-good prose.
"""

from __future__ import annotations

from timbro.rubrics.base import RubricFinding
from timbro.rubrics.features import DocumentView

# Applied uniformly to every span-producing rule below: at most this many findings per
# rule, even if a rule found more occurrences. Recall-first — the LLM consumer filters
# false positives itself, so we cap for payload size, not precision.
MAX_FINDINGS_PER_RULE = 10


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
    internally, capped at MAX_FINDINGS_PER_RULE and converted to 1-based indices."""
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


def schimel_findings(doc: DocumentView) -> list[RubricFinding]:
    findings: list[RubricFinding] = []

    if doc.opening_problem_score() == 0:
        findings.append(
            RubricFinding(
                "high",
                "opening",
                "opening_problem_present",
                1,
                None,
                doc.opening_text()[:220],
                "Opening does not clearly frame an important problem.",
            )
        )
    if doc.opening_method_score() > doc.opening_problem_score():
        findings.append(
            RubricFinding(
                "medium",
                "opening",
                "opening_not_method_first",
                1,
                None,
                doc.opening_text()[:220],
                "Opening leans on methods more than on the problem.",
            )
        )

    if doc.sections.challenge_paragraph is None:
        findings.append(
            RubricFinding(
                "high",
                "challenge",
                "challenge_present",
                None,
                None,
                "",
                "No concrete challenge paragraph was detected.",
            )
        )
    elif doc.objective_only():
        findings.append(
            RubricFinding(
                "high",
                "challenge",
                "objective_only_challenge",
                doc.sections.challenge_paragraph + 1,
                None,
                doc.challenge_text()[:220],
                "States objectives but does not pose a concrete question or gap.",
            )
        )

    if doc.weak_resolution():
        findings.append(
            RubricFinding(
                "high",
                "resolution",
                "weak_resolution",
                doc.sections.resolution_paragraphs[0] + 1
                if doc.sections.resolution_paragraphs
                else None,
                None,
                doc.resolution_text()[:220],
                "Resolution falls back to generic future-work language instead of a concrete conclusion.",
            )
        )
    if doc.challenge_resolution_similarity() < 0.20:
        findings.append(
            RubricFinding(
                "high",
                "resolution",
                "challenge_answered",
                doc.sections.resolution_paragraphs[0] + 1
                if doc.sections.resolution_paragraphs
                else None,
                None,
                doc.resolution_text()[:220],
                "Resolution does not appear to answer the challenge.",
            )
        )
    if doc.opening_resolution_similarity() < 0.15:
        findings.append(
            RubricFinding(
                "medium",
                "resolution",
                "closing_the_circle",
                doc.sections.resolution_paragraphs[0] + 1
                if doc.sections.resolution_paragraphs
                else None,
                None,
                doc.resolution_text()[:220],
                "Resolution does not clearly reconnect to the opening problem.",
            )
        )

    _emit(
        findings,
        severity="medium",
        dimension="clarity",
        rule="undefined_acronyms",
        occurrences=doc.undefined_acronyms(),
        message="Uses an acronym without defining it for readers.",
    )
    fuzzy_density = doc.fuzzy_verb_density()
    if fuzzy_density > 6:
        findings.append(
            RubricFinding(
                "medium",
                "sentences",
                "fuzzy_verb_density",
                None,
                None,
                "",
                "Uses many weak process verbs instead of stronger action verbs.",
            )
        )
    elif fuzzy_density > 4:
        findings.append(
            RubricFinding(
                "low",
                "sentences",
                "fuzzy_verb_density",
                None,
                None,
                "",
                "Uses several weak process verbs instead of stronger action verbs.",
            )
        )
    nominalization = doc.nominalization_density()
    if nominalization > 35:
        findings.append(
            RubricFinding(
                "medium",
                "sentences",
                "nominalization_density",
                None,
                None,
                "",
                "Uses heavy nominalization density that can flatten action.",
            )
        )
    elif nominalization > 25:
        findings.append(
            RubricFinding(
                "low",
                "sentences",
                "nominalization_density",
                None,
                None,
                "",
                "Uses a moderate nominalization density that can flatten action.",
            )
        )
    if doc.noun_trains() > 2:
        findings.append(
            RubricFinding(
                "low",
                "clarity",
                "noun_trains",
                None,
                None,
                "",
                "Contains several dense noun trains.",
            )
        )

    sims = doc.adjacent_paragraph_similarity()
    drift_medium = sorted(
        (idx for idx, s in enumerate(sims) if s < 0.25), key=lambda idx: sims[idx]
    )
    drift_low = sorted(
        (idx for idx, s in enumerate(sims) if 0.25 <= s < 0.35),
        key=lambda idx: sims[idx],
    )
    # Emit the medium band first so report.py's per-rule dedup (first occurrence wins)
    # attributes the stronger penalty when a document has both bands present.
    _emit(
        findings,
        severity="medium",
        dimension="flow",
        rule="paragraph_drift",
        occurrences=[
            (idx + 1, None, doc.paragraphs[idx + 1][:220]) for idx in drift_medium
        ],
        message="A paragraph shift appears abrupt or weakly connected.",
    )
    _emit(
        findings,
        severity="low",
        dimension="flow",
        rule="paragraph_drift",
        occurrences=[
            (idx + 1, None, doc.paragraphs[idx + 1][:220]) for idx in drift_low
        ],
        message="A paragraph shift appears somewhat abrupt or weakly connected.",
    )

    nowhere = [
        i
        for i, para in enumerate(doc.paragraphs, start=1)
        if len(doc.sentences[i - 1]) >= 3
        and doc.paragraph_internal_similarity(i - 1) < 0.25
    ]
    for i in nowhere[:MAX_FINDINGS_PER_RULE]:
        findings.append(
            RubricFinding(
                "medium",
                "paragraphs",
                "point_nowhere_paragraph",
                i,
                None,
                doc.paragraphs[i - 1][:220],
                "Paragraph appears to bundle multiple weakly connected points.",
            )
        )

    caveat = doc.resolution_caveat_span()
    if caveat:
        findings.append(
            RubricFinding(
                "medium",
                "resolution",
                "caveat_closing",
                doc.sections.resolution_paragraphs[-1] + 1,
                None,
                caveat[:220],
                "Resolution closes on a hedge or concession instead of stating the result; do not end on the caveat.",
            )
        )

    for pi, n, c, span in doc.long_sentences()[:MAX_FINDINGS_PER_RULE]:
        findings.append(
            RubricFinding(
                "medium",
                "sentences",
                "overloaded_sentence",
                pi + 1,
                None,
                span[:220],
                f"A sentence runs {n} words / {c} commas; split it so each sentence does one job.",
            )
        )

    for pi, cnt in doc.number_dense_paragraph()[:MAX_FINDINGS_PER_RULE]:
        findings.append(
            RubricFinding(
                "low",
                "clarity",
                "number_ladder",
                pi + 1,
                None,
                doc.paragraphs[pi][:220],
                f"Paragraph packs {cnt} inline statistics; move the ladder to a table and keep only the interpretation in prose.",
            )
        )

    _emit(
        findings,
        severity="medium",
        dimension="clarity",
        rule="coy_predicate",
        occurrences=doc.coy_predicates(),
        message="Coy/deferral phrasing points at the claim instead of stating it; name the value directly.",
    )

    _emit(
        findings,
        severity="low",
        dimension="sentences",
        rule="appositive_colon",
        occurrences=doc.appositive_colon_spans(),
        message="A mid-sentence colon splices two clauses; split 'X is Y: clause' into two sentences.",
    )

    _emit(
        findings,
        severity="low",
        dimension="clarity",
        rule="orphan_pronoun",
        occurrences=doc.orphan_pronoun_spans(),
        message="Sentence opens on a bare 'this/it/they'; attach the noun it refers to (e.g. 'this measurement').",
    )

    _emit(
        findings,
        severity="medium",
        dimension="clarity",
        rule="overclaim_words",
        occurrences=doc.overclaim_words(),
        message="Claim-strength word present; confirm it cleared the robustness gate and is stated at the earned strength, else downgrade.",
    )

    _emit(
        findings,
        severity="low",
        dimension="clarity",
        rule="deadwood",
        occurrences=doc.deadwood_spans(),
        message="Throat-clearing or a stacked hedge carries no information; cut it.",
    )

    _emit(
        findings,
        severity="low",
        dimension="clarity",
        rule="latinate_diction",
        occurrences=doc.latinate_words(),
        message=lambda span: f"Long Latinate word where a short plain one works (Schimel: prefer short words); e.g. {span}.",
    )

    passives = doc.passive_clauses()
    total_sentences = sum(len(s) for s in doc.sentences)
    if total_sentences and passives > max(2, 0.20 * total_sentences):
        findings.append(
            RubricFinding(
                "low",
                "sentences",
                "passive_voice",
                None,
                None,
                "",
                f"{passives} of ~{total_sentences} clauses are passive; Schimel prefers active voice — lead with the actor unless the object is genuinely the topic.",
            )
        )

    _emit(
        findings,
        severity="medium",
        dimension="sentences",
        rule="comma_splice",
        occurrences=doc.comma_splice_spans(),
        message="A comma joins two independent clauses (run-on); use a period, a semicolon, or a conjunction.",
    )

    _emit(
        findings,
        severity="medium",
        dimension="clarity",
        rule="word_repetition",
        occurrences=doc.repetition_bursts(),
        message="A word is echoed several times in a short span; vary it or cut the echo (Schimel: repetition should be deliberate, not accidental).",
    )

    inconsistent = doc.inconsistent_terms()
    _emit(
        findings,
        severity="medium",
        dimension="clarity",
        rule="inconsistent_terminology",
        occurrences=[(None, None, pair) for pair in inconsistent],
        message="Near-synonym terms may name one concept; pick a single term and propagate it through the whole manuscript.",
    )

    _emit(
        findings,
        severity="medium",
        dimension="clarity",
        rule="defensive_claim",
        occurrences=doc.defensive_claims(),
        message="First-person sentence framed around a negation ('we do not…', 'we make no…', 'we lack…'); state what the work does, positively, instead of pre-emptively conceding.",
    )

    _emit(
        findings,
        severity="low",
        dimension="sentences",
        rule="verbless_sentence",
        occurrences=doc.verbless_sentences(),
        message="Sentence has no finite main verb — a fragment or a phrase detached from its verb; attach it or give it a verb.",
    )

    _emit(
        findings,
        severity="medium",
        dimension="sentences",
        rule="buried_verb_core",
        occurrences=doc.buried_verb_spans(),
        message="Subject and verb are far apart (oversized subject or an interruption); Schimel: keep the subject–verb core together, move the rest after the verb.",
    )

    _emit(
        findings,
        severity="low",
        dimension="clarity",
        rule="citation_as_subject",
        occurrences=doc.citation_subject_spans(),
        message="Citation is the sentence subject ('Smith (2003) found…'); make the finding the subject and cite parenthetically (Schimel's funnel).",
    )

    _emit(
        findings,
        severity="low",
        dimension="sentences",
        rule="expletive_opening",
        occurrences=doc.expletive_openings(),
        message="Sentence opens on an empty expletive ('There is…', 'It is…'); lead with the real subject.",
    )

    _emit(
        findings,
        severity="low",
        dimension="clarity",
        rule="significance_without_magnitude",
        occurrences=doc.significance_without_magnitude(),
        message="States significance / a p-value with no effect size; Schimel: tell the story through the data — report the magnitude, and don't equate 'not significant' with 'no effect'.",
    )

    _emit(
        findings,
        severity="low",
        dimension="sentences",
        rule="preposition_chain",
        occurrences=doc.preposition_chains(),
        message="A stack of 'of' phrases; unstack the prepositional chain (Schimel: energy dies in long noun-of-noun-of-noun strings).",
    )

    _emit(
        findings,
        severity="low",
        dimension="clarity",
        rule="metadiscourse_frame",
        occurrences=doc.metadiscourse_frames(),
        message="Metadiscourse frame ('we found that…'); state the finding directly and drop the frame.",
    )

    return findings
