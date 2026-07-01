from __future__ import annotations

from timbro.rubrics.base import RubricFinding
from timbro.rubrics.features import DocumentView


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

    acronyms = doc.undefined_acronyms()
    if acronyms:
        findings.append(
            RubricFinding(
                "medium",
                "clarity",
                "undefined_acronyms",
                None,
                None,
                ", ".join(acronyms[:8]),
                "Uses acronyms without defining them for readers.",
            )
        )
    if doc.fuzzy_verb_density() > 6:
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
    if doc.nominalization_density() > 35:
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
    if sims and min(sims) < 0.25:
        idx = sims.index(min(sims))
        findings.append(
            RubricFinding(
                "medium",
                "flow",
                "paragraph_drift",
                idx + 2,
                None,
                doc.paragraphs[idx + 1][:220],
                "A paragraph shift appears abrupt or weakly connected.",
            )
        )

    for i, para in enumerate(doc.paragraphs, start=1):
        if (
            len(doc.sentences[i - 1]) >= 3
            and doc.paragraph_internal_similarity(i - 1) < 0.25
        ):
            findings.append(
                RubricFinding(
                    "medium",
                    "paragraphs",
                    "point_nowhere_paragraph",
                    i,
                    None,
                    para[:220],
                    "Paragraph appears to bundle multiple weakly connected points.",
                )
            )
            break

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

    longs = doc.long_sentences()
    if longs:
        pi, n, c, span = longs[0]
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

    dense = doc.number_dense_paragraph()
    if dense:
        findings.append(
            RubricFinding(
                "low",
                "clarity",
                "number_ladder",
                dense[0] + 1,
                None,
                doc.paragraphs[dense[0]][:220],
                f"Paragraph packs {dense[1]} inline statistics; move the ladder to a table and keep only the interpretation in prose.",
            )
        )

    coy = doc.coy_predicates()
    if coy:
        findings.append(
            RubricFinding(
                "medium",
                "clarity",
                "coy_predicate",
                None,
                None,
                ", ".join(coy[:5]),
                "Coy/deferral phrasing points at the claim instead of stating it; name the value directly.",
            )
        )

    appositive = doc.appositive_colon_spans()
    if appositive:
        findings.append(
            RubricFinding(
                "low",
                "sentences",
                "appositive_colon",
                None,
                None,
                appositive[0][:220],
                "A mid-sentence colon splices two clauses; split 'X is Y: clause' into two sentences.",
            )
        )

    orphans = doc.orphan_pronoun_spans()
    if orphans:
        findings.append(
            RubricFinding(
                "low",
                "clarity",
                "orphan_pronoun",
                None,
                None,
                orphans[0][:220],
                "Sentence opens on a bare 'this/it/they'; attach the noun it refers to (e.g. 'this measurement').",
            )
        )

    over = doc.overclaim_words()
    if over:
        findings.append(
            RubricFinding(
                "medium",
                "clarity",
                "overclaim_words",
                None,
                None,
                ", ".join(over[:8]),
                "Claim-strength words present; confirm each cleared the robustness gate and is stated at the earned strength, else downgrade.",
            )
        )

    dead = doc.deadwood_spans()
    if dead:
        findings.append(
            RubricFinding(
                "low",
                "clarity",
                "deadwood",
                None,
                None,
                ", ".join(dead[:5]),
                "Throat-clearing or stacked hedges carry no information; cut them.",
            )
        )

    latinate = doc.latinate_words()
    if latinate:
        findings.append(
            RubricFinding(
                "low",
                "clarity",
                "latinate_diction",
                None,
                None,
                "; ".join(latinate[:6]),
                f"Long Latinate words where a short plain one works (Schimel: prefer short words); e.g. {latinate[0]}.",
            )
        )

    passives = doc.passive_clauses()
    total_sentences = sum(len(s) for s in doc.sentences)
    if total_sentences and passives > max(2, 0.33 * total_sentences):
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

    splices = doc.comma_splice_spans()
    if splices:
        findings.append(
            RubricFinding(
                "medium",
                "sentences",
                "comma_splice",
                None,
                None,
                splices[0][:220],
                "A comma joins two independent clauses (run-on); use a period, a semicolon, or a conjunction.",
            )
        )

    bursts = doc.repetition_bursts()
    if bursts:
        findings.append(
            RubricFinding(
                "medium",
                "clarity",
                "word_repetition",
                None,
                None,
                "; ".join(bursts[:4]),
                "A word is echoed several times in a short span; vary it or cut the echo (Schimel: repetition should be deliberate, not accidental).",
            )
        )

    inconsistent = doc.inconsistent_terms()
    if inconsistent:
        findings.append(
            RubricFinding(
                "medium",
                "clarity",
                "inconsistent_terminology",
                None,
                None,
                "; ".join(inconsistent),
                "Near-synonym terms may name one concept; pick a single term and propagate it through the whole manuscript.",
            )
        )

    defensive = doc.defensive_claims()
    if defensive:
        findings.append(
            RubricFinding(
                "medium",
                "clarity",
                "defensive_claim",
                None,
                None,
                defensive[0][:220],
                "First-person sentence framed around a negation ('we do not…', 'we make no…', 'we lack…'); state what the work does, positively, instead of pre-emptively conceding.",
            )
        )

    fragments = doc.verbless_sentences()
    if fragments:
        findings.append(
            RubricFinding(
                "low",
                "sentences",
                "verbless_sentence",
                None,
                None,
                fragments[0][:220],
                "Sentence has no finite main verb — a fragment or a phrase detached from its verb; attach it or give it a verb.",
            )
        )

    buried = doc.buried_verb_spans()
    if buried:
        findings.append(
            RubricFinding(
                "medium",
                "sentences",
                "buried_verb_core",
                None,
                None,
                buried[0][:220],
                "Subject and verb are far apart (oversized subject or an interruption); Schimel: keep the subject–verb core together, move the rest after the verb.",
            )
        )

    citations = doc.citation_subject_spans()
    if citations:
        findings.append(
            RubricFinding(
                "low",
                "clarity",
                "citation_as_subject",
                None,
                None,
                "; ".join(citations[:4]),
                "Citation is the sentence subject ('Smith (2003) found…'); make the finding the subject and cite parenthetically (Schimel's funnel).",
            )
        )

    expletives = doc.expletive_openings()
    if expletives:
        findings.append(
            RubricFinding(
                "low",
                "sentences",
                "expletive_opening",
                None,
                None,
                expletives[0][:220],
                "Sentence opens on an empty expletive ('There is…', 'It is…'); lead with the real subject.",
            )
        )

    signif = doc.significance_without_magnitude()
    if signif:
        findings.append(
            RubricFinding(
                "low",
                "clarity",
                "significance_without_magnitude",
                None,
                None,
                signif[0][:220],
                "States significance / a p-value with no effect size; Schimel: tell the story through the data — report the magnitude, and don't equate 'not significant' with 'no effect'.",
            )
        )

    prep_chains = doc.preposition_chains()
    if prep_chains:
        findings.append(
            RubricFinding(
                "low",
                "sentences",
                "preposition_chain",
                None,
                None,
                prep_chains[0][:220],
                "A stack of 'of' phrases; unstack the prepositional chain (Schimel: energy dies in long noun-of-noun-of-noun strings).",
            )
        )

    metadiscourse = doc.metadiscourse_frames()
    if metadiscourse:
        findings.append(
            RubricFinding(
                "low",
                "clarity",
                "metadiscourse_frame",
                None,
                None,
                "; ".join(metadiscourse[:4]),
                "Metadiscourse frame ('we found that…'); state the finding directly and drop the frame.",
            )
        )

    return findings
