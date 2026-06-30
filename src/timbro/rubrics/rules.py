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

    caveat = doc.resolution_caveat_span()
    if caveat:
        findings.append(RubricFinding("medium", "resolution", "caveat_closing", doc.sections.resolution_paragraphs[-1] + 1, None, caveat[:220], "Resolution closes on a hedge or concession instead of stating the result; do not end on the caveat."))

    longs = doc.long_sentences()
    if longs:
        pi, n, c, span = longs[0]
        findings.append(RubricFinding("medium", "sentences", "overloaded_sentence", pi + 1, None, span[:220], f"A sentence runs {n} words / {c} commas; split it so each sentence does one job."))

    dense = doc.number_dense_paragraph()
    if dense:
        findings.append(RubricFinding("low", "clarity", "number_ladder", dense[0] + 1, None, doc.paragraphs[dense[0]][:220], f"Paragraph packs {dense[1]} inline statistics; move the ladder to a table and keep only the interpretation in prose."))

    coy = doc.coy_predicates()
    if coy:
        findings.append(RubricFinding("medium", "clarity", "coy_predicate", None, None, ", ".join(coy[:5]), "Coy/deferral phrasing points at the claim instead of stating it; name the value directly."))

    appositive = doc.appositive_colon_spans()
    if appositive:
        findings.append(RubricFinding("low", "sentences", "appositive_colon", None, None, appositive[0][:220], "A mid-sentence colon splices two clauses; split 'X is Y: clause' into two sentences."))

    orphans = doc.orphan_pronoun_spans()
    if orphans:
        findings.append(RubricFinding("low", "clarity", "orphan_pronoun", None, None, orphans[0][:220], "Sentence opens on a bare 'this/it/they'; attach the noun it refers to (e.g. 'this measurement')."))

    over = doc.overclaim_words()
    if over:
        findings.append(RubricFinding("medium", "clarity", "overclaim_words", None, None, ", ".join(over[:8]), "Claim-strength words present; confirm each cleared the robustness gate and is stated at the earned strength, else downgrade."))

    dead = doc.deadwood_spans()
    if dead:
        findings.append(RubricFinding("low", "clarity", "deadwood", None, None, ", ".join(dead[:5]), "Throat-clearing or stacked hedges carry no information; cut them."))

    latinate = doc.latinate_words()
    if latinate:
        findings.append(RubricFinding("low", "clarity", "latinate_diction", None, None, "; ".join(latinate[:6]), f"Long Latinate words where a short plain one works (Schimel: prefer short words); e.g. {latinate[0]}."))

    passives = doc.passive_clauses()
    total_sentences = sum(len(s) for s in doc.sentences)
    if total_sentences and passives > max(2, 0.33 * total_sentences):
        findings.append(RubricFinding("low", "sentences", "passive_voice", None, None, "", f"{passives} of ~{total_sentences} clauses are passive; Schimel prefers active voice — lead with the actor unless the object is genuinely the topic."))

    splices = doc.comma_splice_spans()
    if splices:
        findings.append(RubricFinding("medium", "sentences", "comma_splice", None, None, splices[0][:220], "A comma joins two independent clauses (run-on); use a period, a semicolon, or a conjunction."))

    return findings
