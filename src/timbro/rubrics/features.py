from __future__ import annotations

import re
from functools import cached_property, lru_cache
from statistics import pstdev

import numpy as np

from timbro.cleanup import preprocess_runtime_text
from timbro.flow import _model as _embed_model
from timbro.rubrics.sections import detect_sections, split_paragraphs, split_sentences


@lru_cache(maxsize=1)
def _rubric_nlp():
    """spaCy with the dependency parser AND lemmatizer ON (passive voice, comma splices,
    sentence boundaries need the parser; repetition/terminology/defensive checks need lemmas).
    Separate from core._nlp, which disables both for fast scoring."""
    import spacy

    try:
        return spacy.load("en_core_web_sm", disable=["ner"])
    except OSError as e:  # pragma: no cover
        raise OSError("Run: uv run python -m spacy download en_core_web_sm") from e


_CITATION = re.compile(r"\([A-Z][A-Za-z-]+(?: et al\.)?,? \d{4}\)|\[\d+\]")
_FUZZY = re.compile(
    r"\b(?:affect|facilitate|occur|perform|conduct|implement|provide|utilize|evaluate|examine)\w*\b",
    re.I,
)
_NOM = re.compile(r"\b\w+(?:tion|sion|ment|ance|ence|ity|ness)\b", re.I)
_ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
_ALLOW = {"DNA", "RNA", "CO2", "NLP", "AI", "LLM", "OCAR", "SUCCES", "NIH", "NSF"}
_PROBLEM = re.compile(
    r"\b(?:challenge|problem|question|unknown|unclear|important|critical|controls?|drives?|limits?|affects?)\b",
    re.I,
)
_METHOD = re.compile(
    r"\b(?:method|methods|measured|measures?|dataset|datasets|algorithm|algorithms|model|models|experiment|experiments)\b",
    re.I,
)
_WEAK_END = re.compile(
    r"\b(?:more research is needed|future work is needed|may provide insights|could be important)\b",
    re.I,
)
_OBJECTIVE_ONLY = re.compile(r"\bour objective(?:s)? (?:was|were|is|are)\b", re.I)
# A section closing on a hedge/concession instead of the result ("we cry at the end").
_HEDGE_CLOSE = re.compile(
    r"\b(?:however|although|though|nonetheless|nevertheless|admittedly|unfortunately|"
    r"caveat|limitation|we do not (?:claim|argue)|we make no|we cannot|"
    r"does not (?:claim|establish|prove)|no\b[^.]{0,30}\bsuperiority|"
    r"rather than (?:a|an|evidence)|to be fair|falls short|is not (?:more|better|a stronger))\b",
    re.I,
)
# Coy/deferral predicates that point at the claim instead of making it.
_COY = re.compile(
    r"\b(?:its value (?:is|lies)\b|the (?:real )?(?:key|point|answer|crux|value) (?:is|lies|here is)\b|"
    r"what (?:really )?matters (?:is|here)\b|the answer lies\b|the trick is\b|the magic (?:is|happens)\b)",
    re.I,
)
# Inline statistics (decimals / percentages) — a run of these is a number-ladder for a table.
_STAT_NUMBER = re.compile(r"\d+\.\d+|\d+\s?%")
# Mid-sentence appositive colon splice ("X is Y: clause" → two sentences). A following
# lowercase word marks a clause, not a (usually capitalised or comma-listed) enumeration.
_APPOSITIVE_COLON = re.compile(r"[a-z]{3,}: [a-z]")
# Sentence opening on a bare demonstrative/pronoun + verb (orphan "this/it" → "this measurement").
_ORPHAN_START = re.compile(
    r"^(?:This|These|That|It|They)\s+"
    r"(?:is|are|was|were|will|would|can|could|may|might|has|have|had|does|do|did|"
    r"shows?|means?|makes?|gives?|provides?|suggests?|implies|allows?|enables?|"
    r"leads?|results?|reflects?|captures?|measures?|remains?|becomes?)\b"
)
# High-signal claim-strength words to confirm against the robustness gate (polysemous
# ones like "first"/"significant" are left to experiment-discipline, not flagged here).
_OVERCLAIM = re.compile(
    r"\b(?:proves?|proven|establishes?|novel|state[- ]of[- ]the[- ]art|outperforms?|"
    r"validate[ds]?|load[- ]bearing|unprecedented|definitive)\b",
    re.I,
)
# Throat-clearing and stacked hedges that carry no information.
_DEADWOOD = re.compile(
    r"\b(?:it is important to note that|it should be noted that|it is worth noting that|"
    r"needless to say|as a matter of fact|for all intents and purposes|"
    r"may possibly|might perhaps|could potentially|somewhat suggests?)\b",
    re.I,
)
# Long Latinate words where a short Anglo-Saxon one works (Schimel, Writing Science ch. 9:
# "prefer short words"). Map gives the plain alternative so the finding is actionable.
_LATINATE_PLAIN = {
    "utilize": "use",
    "utilise": "use",
    "facilitate": "help",
    "demonstrate": "show",
    "sufficient": "enough",
    "additional": "more",
    "approximately": "about",
    "commence": "start",
    "terminate": "end",
    "methodology": "method",
    "numerous": "many",
    "obtain": "get",
    "initiate": "start",
    "endeavor": "try",
    "endeavour": "try",
    "ascertain": "find out",
    "necessitate": "need",
    "subsequently": "then",
    "predominantly": "mostly",
    "utilization": "use",
    "modification": "change",
}
# Detection is a rule, not the list: long words (>= 4 vowel-group syllables) are
# overwhelmingly Latinate/Greek, which is Schimel's "prefer short words" target. We skip
# nominalizations (-tion, -ity, ...) — the nominalization check already owns those — and
# use the map above only to upgrade the advice to a plain-word swap when we know one.
_SYLLABLE = re.compile(r"[aeiouy]+", re.I)
_NOMINAL_END = re.compile(r"(?:tion|sion|ment|ity|ance|ence|ness)s?$", re.I)
_WORD_TOKEN = re.compile(r"[A-Za-z][A-Za-z-]{4,}")
# Content parts of speech for the repetition/terminology checks (skip function words).
_CONTENT_POS = {"NOUN", "PROPN", "VERB", "ADJ", "ADV"}
# Leitwort (leading-word) detector thresholds (#4): corpus-free positional-clustering
# entropy via gap-burstiness (coefficient of variation of inter-occurrence gaps). Under
# roughly uniform placement CV ≈ 1; clustered words score higher.
_LEITWORT_MIN_DOC_TOKENS = 300  # alphabetic tokens; shorter docs return []
_LEITWORT_MIN_OCCURRENCES = 4
_LEITWORT_MIN_GAPS = 3
_LEITWORT_SCORE_THRESHOLD = 1.3
_LEITWORT_MAX_RESULTS = 10
# First-person markers and negations for the defensive-claim check (structural, not a
# phrase list — "we + negation" catches "we do not claim", "we make no…", "we lack…").
# "i" is left out on purpose: academic prose uses "we", and "(i)/(ii)" enumeration markers
# would otherwise read as first person.
_FIRST_PERSON = {"we", "our", "us"}
_NEGATION = {
    "not",
    "no",
    "never",
    "cannot",
    "neither",
    "nor",
    "n't",
    "without",
    "fail",
    "lack",
}
# Finite-verb tags: a sentence with none of these (and no AUX) has no main verb.
_FINITE_TAG = {"VBP", "VBZ", "VBD", "MD"}
# Reporting/attribution verbs — a genuinely closed lexical class (there is no structural
# signal for "this is a reporting verb"), so a small list here is strictly necessary.
_REPORT_VERB = (
    r"(?:found|shows?|showed|shown|reports?|reported|observes?|observed|demonstrates?|"
    r"demonstrated|argues?|argued|notes?|noted|proposes?|proposed|suggests?|suggested|"
    r"concludes?|concluded|claims?|claimed|establish(?:es|ed)?|reveals?|revealed|finds?)"
)
# Citation as the grammatical subject (\citet{...} or "Name (2003)") governing a reporting
# verb — Schimel's funnel (ch. 6): make the finding the subject, not the researcher.
_CITATION_SUBJECT = re.compile(
    r"(?:\\citet\{[^}]*\}|[A-Z][A-Za-z]+(?: et al\.?| and [A-Z][A-Za-z]+)?\s*\(\d{4}\))\s+"
    + _REPORT_VERB
    + r"\b"
)
# Metadiscourse frame: first person + reporting verb + "that" ("we found that X" → state X).
_METADISCOURSE = re.compile(
    r"\b(?:we|this (?:study|paper|work|analysis)|our (?:results?|data|analysis|experiments?))\s+"
    + _REPORT_VERB
    + r"\s+that\b",
    re.I,
)
# Expletive opening: "There is/are…", "It is/was…" — an empty subject Schimel says to cut.
_EXPLETIVE_OPEN = re.compile(
    r"^(?:There\s+(?:is|are|was|were|has|have|exists?|remains?|seems?|appears?)|"
    r"It\s+(?:is|was|has been|seems?|appears?|turns out))\b",
    re.I,
)
# "significant(ly)" or a p-value; a run of these with no co-located magnitude is Schimel's
# "tell the story through the data, not the statistics" (ch. 8) — report the effect size.
_SIGNIF = re.compile(r"\bsignificantly?\b|\bp\s*[<=>]\s*0?\.\d+", re.I)
_MAGNITUDE = re.compile(
    r"%|[×x]\b|\bfold\b|\btimes\b|\bfactor\b|\bpercent\b|\bpoints?\b|"
    r"\d+\s*(?:mm|cm|km|kg|mg|ms|Hz|days?|years?|hours?)\b",
    re.I,
)
# A "of … of … of" run: 3+ prepositional phrases stacked (Schimel ch. 15: unstack them).
_OF_CHAIN = re.compile(r"\bof\b(?:\s+\S+){1,4}\s+\bof\b(?:\s+\S+){1,4}\s+\bof\b", re.I)
# Words that legally introduce a clause after a comma (coordinators + subordinators +
# relatives), so they are NOT comma splices.
_SPLICE_SKIP = {
    "and",
    "but",
    "or",
    "nor",
    "yet",
    "so",
    "for",
    "which",
    "who",
    "whom",
    "whose",
    "that",
    "where",
    "when",
    "while",
    "because",
    "although",
    "though",
    "since",
    "if",
    "as",
    "whereas",
    "unless",
    "until",
    "whether",
    "once",
}


def _syllable_estimate(word: str) -> int:
    return len(_SYLLABLE.findall(word))


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b)) or 1.0
    return float(np.dot(a, b) / denom)


class DocumentView:
    def __init__(self, text: str):
        self.text = preprocess_runtime_text(text)
        self.paragraphs = split_paragraphs(self.text)
        self.sentences = [split_sentences(p) for p in self.paragraphs]
        self.sections = detect_sections(self.paragraphs)

    @cached_property
    def paragraph_embeddings(self) -> np.ndarray:
        if not self.paragraphs:
            return np.zeros((0, 384))
        return np.asarray(
            _embed_model().encode(self.paragraphs, normalize_embeddings=True)
        )

    @cached_property
    def _spacy_paragraphs(self) -> list:
        """Parse each paragraph once; shared by the POS/dep checks (noun trains, passive, splice)."""
        return [_rubric_nlp()(p[:100000]) for p in self.paragraphs]

    @cached_property
    def leading_words(self) -> list[dict]:
        """Leitwort detector (#4): content lemmas whose occurrences cluster positionally in
        this document instead of spreading evenly, via gap-burstiness (coefficient of
        variation of inter-occurrence gaps over the whole-document token stream). Corpus-free
        and single-document-relative — no reference corpus, no LLM, no randomness. Public
        surface consumed by #5 (density-rubric payload) and #6 (repetition annotation); keep
        the return shape ({lemma, count, score, paragraphs}) stable."""
        total_alpha_tokens = sum(
            1 for doc in self._spacy_paragraphs for tok in doc if tok.is_alpha
        )
        if total_alpha_tokens < _LEITWORT_MIN_DOC_TOKENS:
            return []

        positions: dict[str, list[int]] = {}
        paragraphs_seen: dict[str, list[int]] = {}
        pos = 0
        for pi, doc in enumerate(self._spacy_paragraphs):
            for tok in doc:
                if tok.pos_ in _CONTENT_POS and tok.is_alpha:
                    lemma = tok.lemma_.lower()
                    positions.setdefault(lemma, []).append(pos)
                    paras = paragraphs_seen.setdefault(lemma, [])
                    if not paras or paras[-1] != pi:
                        paras.append(pi)
                pos += 1

        results = []
        for lemma, occ in positions.items():
            if len(occ) < _LEITWORT_MIN_OCCURRENCES:
                continue
            gaps = [b - a for a, b in zip(occ, occ[1:])]
            if len(gaps) < _LEITWORT_MIN_GAPS:
                continue
            mean_gap = sum(gaps) / len(gaps)
            if mean_gap <= 0:
                continue
            score = pstdev(gaps) / mean_gap
            if score >= _LEITWORT_SCORE_THRESHOLD:
                results.append(
                    {
                        "lemma": lemma,
                        "count": len(occ),
                        "score": score,
                        "paragraphs": paragraphs_seen[lemma],
                    }
                )

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:_LEITWORT_MAX_RESULTS]

    def paragraph_similarity(self, a: int, b: int) -> float:
        if a >= len(self.paragraphs) or b >= len(self.paragraphs):
            return 0.0
        return _cos(self.paragraph_embeddings[a], self.paragraph_embeddings[b])

    def adjacent_paragraph_similarity(self) -> list[float]:
        return [
            self.paragraph_similarity(i, i + 1) for i in range(len(self.paragraphs) - 1)
        ]

    def paragraph_internal_similarity(self, i: int) -> float:
        sents = self.sentences[i]
        if len(sents) < 2:
            return 1.0
        emb = np.asarray(_embed_model().encode(sents, normalize_embeddings=True))
        sims = [_cos(emb[j], emb[j + 1]) for j in range(len(emb) - 1)]
        return float(np.mean(sims)) if sims else 1.0

    def citation_density(self, paragraph: str) -> float:
        words = max(1, len(paragraph.split()))
        return len(_CITATION.findall(paragraph)) / words

    def fuzzy_verb_density(self) -> float:
        words = max(1, len(self.text.split()))
        return len(_FUZZY.findall(self.text)) * 1000 / words

    def nominalization_density(self) -> float:
        words = max(1, len(self.text.split()))
        return len(_NOM.findall(self.text)) * 1000 / words

    def undefined_acronyms(self) -> list[tuple[int, int, str]]:
        # Doc-level: an acronym expanded once (parenthetically) anywhere counts as defined,
        # so a later bare use is not re-flagged. Flag only the never-expanded ones, located
        # at their first bare occurrence.
        seen: dict[str, tuple[int, int]] = {}
        expanded: set[str] = set()
        for pi, para in enumerate(self.paragraphs):
            for ac in _ACRONYM.findall(para):
                if ac in _ALLOW:
                    continue
                if re.search(rf"\([^)]*\b{ac}\b[^)]*\)", para):
                    expanded.add(ac)
                elif ac not in seen:
                    si = next(
                        (j for j, s in enumerate(self.sentences[pi]) if ac in s), 0
                    )
                    seen[ac] = (pi, si)
        return [(pi, si, ac) for ac, (pi, si) in seen.items() if ac not in expanded]

    def noun_trains(self) -> int:
        train_count = 0
        for doc in self._spacy_paragraphs:
            run = 0
            for tok in doc:
                if tok.pos_ in {"NOUN", "PROPN"}:
                    run += 1
                else:
                    if run >= 3:
                        train_count += 1
                    run = 0
            if run >= 3:
                train_count += 1
        return train_count

    def opening_problem_score(self) -> int:
        return sum(
            len(_PROBLEM.findall(self.paragraphs[i]))
            for i in self.sections.opening_paragraphs
            if i < len(self.paragraphs)
        )

    def opening_method_score(self) -> int:
        return sum(
            len(_METHOD.findall(self.paragraphs[i]))
            for i in self.sections.opening_paragraphs
            if i < len(self.paragraphs)
        )

    def challenge_text(self) -> str:
        i = self.sections.challenge_paragraph
        return self.paragraphs[i] if i is not None and i < len(self.paragraphs) else ""

    def resolution_text(self) -> str:
        return "\n\n".join(
            self.paragraphs[i]
            for i in self.sections.resolution_paragraphs
            if i < len(self.paragraphs)
        )

    def opening_text(self) -> str:
        return "\n\n".join(
            self.paragraphs[i]
            for i in self.sections.opening_paragraphs
            if i < len(self.paragraphs)
        )

    def challenge_resolution_similarity(self) -> float:
        if not self.challenge_text() or not self.resolution_text():
            return 0.0
        emb = np.asarray(
            _embed_model().encode(
                [self.challenge_text(), self.resolution_text()],
                normalize_embeddings=True,
            )
        )
        return _cos(emb[0], emb[1])

    def opening_resolution_similarity(self) -> float:
        if not self.opening_text() or not self.resolution_text():
            return 0.0
        emb = np.asarray(
            _embed_model().encode(
                [self.opening_text(), self.resolution_text()], normalize_embeddings=True
            )
        )
        return _cos(emb[0], emb[1])

    def weak_resolution(self) -> bool:
        return bool(_WEAK_END.search(self.resolution_text()))

    def objective_only(self) -> bool:
        txt = self.challenge_text()
        return (
            bool(_OBJECTIVE_ONLY.search(txt))
            and "?" not in txt
            and "hypothes" not in txt.lower()
            and "whether" not in txt.lower()
        )

    def resolution_caveat_span(self) -> str:
        """Last sentence of the resolution, returned only if it closes on a hedge/concession."""
        res = self.sections.resolution_paragraphs
        if not res:
            return ""
        last_i = res[-1]
        if last_i >= len(self.sentences) or not self.sentences[last_i]:
            return ""
        last = self.sentences[last_i][-1]
        return last if _HEDGE_CLOSE.search(last) else ""

    def long_sentences(
        self, max_words: int = 45, max_commas: int = 4
    ) -> list[tuple[int, int, int, str]]:
        """(paragraph_idx, word_count, comma_count, sentence) for over-long sentences, worst first."""
        out = []
        for pi, sents in enumerate(self.sentences):
            for s in sents:
                n, c = len(s.split()), s.count(",")
                if n > max_words or c >= max_commas:
                    out.append((pi, n, c, s))
        out.sort(key=lambda t: (t[1], t[2]), reverse=True)
        return out

    def number_dense_paragraph(self, threshold: int = 6) -> list[tuple[int, int]]:
        """(paragraph_idx, stat_count) for every paragraph with >= threshold inline
        statistics, worst (most stats) first."""
        out = [
            (pi, len(_STAT_NUMBER.findall(para)))
            for pi, para in enumerate(self.paragraphs)
        ]
        out = [(pi, cnt) for pi, cnt in out if cnt >= threshold]
        out.sort(key=lambda t: t[1], reverse=True)
        return out

    def coy_predicates(self) -> list[tuple[int, int, str]]:
        return [
            (pi, si, m.group(0))
            for pi, sents in enumerate(self.sentences)
            for si, s in enumerate(sents)
            for m in _COY.finditer(s)
        ]

    def appositive_colon_spans(self) -> list[tuple[int, int, str]]:
        return [
            (pi, si, s)
            for pi, sents in enumerate(self.sentences)
            for si, s in enumerate(sents)
            if _APPOSITIVE_COLON.search(s)
        ]

    def orphan_pronoun_spans(self) -> list[tuple[int, int, str]]:
        return [
            (pi, si, s)
            for pi, sents in enumerate(self.sentences)
            for si, s in enumerate(sents)
            if _ORPHAN_START.match(s)
        ]

    def overclaim_words(self) -> list[tuple[int, int, str]]:
        seen: dict[str, tuple[int, int]] = {}
        for pi, sents in enumerate(self.sentences):
            for si, s in enumerate(sents):
                for m in _OVERCLAIM.finditer(s):
                    w = m.group(0).lower()
                    if w not in seen:
                        seen[w] = (pi, si)
        return [(pi, si, w) for w, (pi, si) in seen.items()]

    def deadwood_spans(self) -> list[tuple[int, int, str]]:
        return [
            (pi, si, m.group(0))
            for pi, sents in enumerate(self.sentences)
            for si, s in enumerate(sents)
            for m in _DEADWOOD.finditer(s)
        ]

    def latinate_words(self, min_syllables: int = 4) -> list[tuple[int, int, str]]:
        """Long Latinate words a short Anglo-Saxon one could replace (Schimel: prefer short
        words). Detection is a syllable/morphology rule, not a fixed list; the map only adds a
        plain-word suggestion for common offenders. Nominalizations are left to that check."""
        seen: dict[str, tuple[int, int, str]] = {}
        for pi, sents in enumerate(self.sentences):
            for si, s in enumerate(sents):
                for w in _WORD_TOKEN.findall(s):
                    lw = w.lower()
                    if lw in seen:
                        continue
                    base = next((b for b in _LATINATE_PLAIN if lw.startswith(b)), None)
                    if base is None and (
                        _NOMINAL_END.search(lw) or _syllable_estimate(lw) < min_syllables
                    ):
                        continue
                    label = f"{lw} → {_LATINATE_PLAIN[base]}" if base else lw
                    seen[lw] = (pi, si, label)
        return list(seen.values())

    def passive_clauses(self) -> int:
        """Count of passive-voice clauses (Schimel: active by default). spaCy dep parse."""
        return sum(
            1
            for doc in self._spacy_paragraphs
            for tok in doc
            if tok.dep_ == "nsubjpass"
        )

    def comma_splice_spans(self) -> list[tuple[int, int, str]]:
        """Sentences where a comma joins two independent clauses with no conjunction — the
        'weirdly structured' run-on ('X separates Y from Z, no signal wins everywhere').
        A real splice has a full clause (subject + its verb) in the window right AFTER the
        comma; that bounded window rejects interrupting parentheticals and comma lists."""
        out: list[tuple[int, int, str]] = []
        for pi, doc in enumerate(self._spacy_paragraphs):
            for si, sent in enumerate(doc.sents):
                toks = list(sent)
                for idx, tok in enumerate(toks):
                    if tok.text != "," or idx + 1 >= len(toks):
                        continue
                    nxt = toks[idx + 1]
                    if nxt.pos_ in {"CCONJ", "SCONJ"} or nxt.lower_ in _SPLICE_SKIP:
                        continue
                    window = []
                    for t in toks[idx + 1 :]:
                        if t.text == ",":
                            break
                        window.append(t)
                    wset = {t.i for t in window}
                    right = any(
                        t.dep_ in {"nsubj", "nsubjpass"}
                        and t.head.pos_ in {"VERB", "AUX"}
                        and t.head.i in wset
                        for t in window
                    )
                    left = any(
                        t.dep_ in {"nsubj", "nsubjpass"}
                        and t.head.pos_ in {"VERB", "AUX"}
                        and t.i < tok.i
                        and t.head.i < tok.i
                        for t in sent
                    )
                    if right and left:
                        out.append((pi, si, sent.text.strip()))
                        break
        return out

    def repetition_bursts(
        self, window: int = 20, min_repeats: int = 3
    ) -> list[tuple[int, int, str]]:
        """Same word echoed in a short span ('reference-free … reference-based … reference-free',
        'rules' hammered). Generalizes over lemmas — no word list. Also flags two derivations of
        one stem sitting adjacent ('normalisation, normalises'). One burst per paragraph."""
        out: list[tuple[int, int, str]] = []
        for pi, doc in enumerate(self._spacy_paragraphs):
            sent_list = list(doc.sents)

            def _sent_idx(tok_i: int, _sent_list=sent_list) -> int:
                return next(
                    (j for j, sent in enumerate(_sent_list) if sent.start <= tok_i < sent.end),
                    0,
                )

            toks = [
                t
                for t in doc
                if t.pos_ in _CONTENT_POS and t.is_alpha and len(t.text) >= 4
            ]
            lemmas = [t.lemma_.lower() for t in toks]
            for i in range(len(lemmas)):
                counts: dict[str, int] = {}
                end = min(i + window, len(lemmas))
                for j in range(i, end):
                    counts[lemmas[j]] = counts.get(lemmas[j], 0) + 1
                hot = next((w for w, c in counts.items() if c >= min_repeats), None)
                if hot:
                    span = doc[toks[i].i : toks[end - 1].i + 1].text.replace("\n", " ")
                    out.append(
                        (pi, _sent_idx(toks[i].i), f"{hot} ×{counts[hot]}: …{span[:160]}…")
                    )
                    break
            for a, b in zip(toks, toks[1:]):
                fa, fb = a.text.lower(), b.text.lower()
                if fa != fb and len(fa) >= 7 and fa[:7] == fb[:7]:
                    out.append((pi, _sent_idx(a.i), f"{a.text} / {b.text}"))
        return out

    def inconsistent_terms(
        self, min_count: int = 3, threshold: float = 0.55, top: int = 5
    ) -> list[str]:
        """Near-synonym technical terms both used for what looks like one concept
        (composite/combined, scaled/normalised/calibrated). Generalizes via semantic-embedding
        cosine — no synonym list. Recall-first; the model consumer discards genuinely distinct
        pairs. Morphological/substring dupes are left to repetition_bursts."""
        counts: dict[str, int] = {}
        surface: dict[str, str] = {}
        for doc in self._spacy_paragraphs:
            for t in doc:
                if (
                    t.pos_ in {"NOUN", "PROPN", "ADJ"}
                    and t.is_alpha
                    and len(t.text) >= 4
                ):
                    lemma = t.lemma_.lower()
                    counts[lemma] = counts.get(lemma, 0) + 1
                    surface.setdefault(lemma, t.text.lower())
        terms = [w for w, c in counts.items() if c >= min_count]
        if len(terms) < 2:
            return []
        emb = np.asarray(
            _embed_model().encode(
                [surface[w] for w in terms], normalize_embeddings=True
            )
        )
        pairs: list[tuple[float, str, str]] = []
        for i in range(len(terms)):
            for j in range(i + 1, len(terms)):
                a, b = terms[i], terms[j]
                if a[:4] == b[:4] or a in b or b in a:
                    continue
                sim = _cos(emb[i], emb[j])
                if sim >= threshold:
                    pairs.append((sim, surface[a], surface[b]))
        pairs.sort(reverse=True)
        return [f"{a} / {b} (≈{s:.2f})" for s, a, b in pairs[:top]]

    def defensive_claims(self) -> list[tuple[int, int, str]]:
        """First-person sentences built around a negation ('we do not claim…', 'we make no
        superiority claim', 'we lack references') — Schimel: say what the work DOES, with
        confidence, instead of pre-emptively conceding. Structural (first person + negation),
        not a phrase list."""
        out: list[tuple[int, int, str]] = []
        for pi, doc in enumerate(self._spacy_paragraphs):
            for si, sent in enumerate(doc.sents):
                lowers = {t.text.lower() for t in sent} | {
                    t.lemma_.lower() for t in sent
                }
                if lowers & _FIRST_PERSON and lowers & _NEGATION:
                    out.append((pi, si, sent.text.strip()))
        return out

    def verbless_sentences(self, min_words: int = 5) -> list[tuple[int, int, str]]:
        """Sentences with no finite main verb — a fragment, or a phrase left 'detached from its
        main verb'. Short/heading-like lines are skipped."""
        out: list[tuple[int, int, str]] = []
        for pi, doc in enumerate(self._spacy_paragraphs):
            for si, sent in enumerate(doc.sents):
                s = sent.text.strip()
                if s[:1] in {"-", "*", "•"} or (
                    s[:1].isdigit() and s[1:2] in {".", ")"}
                ):
                    continue  # list items are legitimately verbless
                if sum(1 for t in sent if t.is_alpha) < min_words:
                    continue
                if not any(t.tag_ in _FINITE_TAG or t.pos_ == "AUX" for t in sent):
                    out.append((pi, si, s))
        return out

    def buried_verb_spans(self, max_gap: int = 10) -> list[tuple[int, int, str]]:
        """Subject and its verb pulled far apart by an oversized subject or an interrupting
        clause (Schimel ch. 12: keep the subject–verb core together). Dependency distance from
        the subject head to its verb — no word list. One per paragraph."""
        out: list[tuple[int, int, str]] = []
        for pi, doc in enumerate(self._spacy_paragraphs):
            sent_list = list(doc.sents)
            for tok in doc:
                if tok.dep_ in {"nsubj", "nsubjpass"} and tok.head.pos_ in {
                    "VERB",
                    "AUX",
                }:
                    gap = tok.head.i - tok.i
                    if gap >= max_gap:
                        si = next(
                            (
                                j
                                for j, sent in enumerate(sent_list)
                                if sent.start <= tok.i < sent.end
                            ),
                            0,
                        )
                        out.append(
                            (
                                pi,
                                si,
                                f"(subject→verb {gap} words) {tok.sent.text.strip()[:200]}",
                            )
                        )
                        break
        return out

    def citation_subject_spans(self) -> list[tuple[int, int, str]]:
        """Citations used as the sentence subject ('Smith (2003) found …', '\\citet{} showed …')
        — Schimel: put the finding in the subject, cite parenthetically."""
        return [
            (pi, si, m.group(0)[:120])
            for pi, sents in enumerate(self.sentences)
            for si, s in enumerate(sents)
            for m in _CITATION_SUBJECT.finditer(s)
        ]

    def expletive_openings(self) -> list[tuple[int, int, str]]:
        return [
            (pi, si, s)
            for pi, sents in enumerate(self.sentences)
            for si, s in enumerate(sents)
            if _EXPLETIVE_OPEN.match(s)
        ]

    def significance_without_magnitude(self) -> list[tuple[int, int, str]]:
        """Sentences asserting significance / a p-value with no effect size in view."""
        return [
            (pi, si, s.strip())
            for pi, sents in enumerate(self.sentences)
            for si, s in enumerate(sents)
            if _SIGNIF.search(s) and not _MAGNITUDE.search(s)
        ]

    def preposition_chains(self) -> list[tuple[int, int, str]]:
        return [
            (pi, si, m.group(0))
            for pi, sents in enumerate(self.sentences)
            for si, s in enumerate(sents)
            for m in _OF_CHAIN.finditer(s)
        ]

    def metadiscourse_frames(self) -> list[tuple[int, int, str]]:
        return [
            (pi, si, m.group(0))
            for pi, sents in enumerate(self.sentences)
            for si, s in enumerate(sents)
            for m in _METADISCOURSE.finditer(s)
        ]
