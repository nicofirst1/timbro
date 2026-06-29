from __future__ import annotations

import re
from functools import cached_property

import numpy as np

from timbro.cleanup import preprocess_runtime_text
from timbro.core import _nlp
from timbro.flow import _model as _embed_model
from timbro.rubrics.sections import detect_sections, split_paragraphs, split_sentences

_CITATION = re.compile(r"\([A-Z][A-Za-z-]+(?: et al\.)?,? \d{4}\)|\[\d+\]")
_FUZZY = re.compile(r"\b(?:affect|facilitate|occur|perform|conduct|implement|provide|utilize|evaluate|examine)\w*\b", re.I)
_NOM = re.compile(r"\b\w+(?:tion|sion|ment|ance|ence|ity|ness)\b", re.I)
_ACRONYM = re.compile(r"\b[A-Z]{2,}\b")
_ALLOW = {"DNA", "RNA", "CO2", "NLP", "AI", "LLM", "OCAR", "SUCCES", "NIH", "NSF"}
_PROBLEM = re.compile(r"\b(?:challenge|problem|question|unknown|unclear|important|critical|controls?|drives?|limits?|affects?)\b", re.I)
_METHOD = re.compile(r"\b(?:method|methods|measured|measures?|dataset|datasets|algorithm|algorithms|model|models|experiment|experiments)\b", re.I)
_WEAK_END = re.compile(r"\b(?:more research is needed|future work is needed|may provide insights|could be important)\b", re.I)
_OBJECTIVE_ONLY = re.compile(r"\bour objective(?:s)? (?:was|were|is|are)\b", re.I)


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
        return np.asarray(_embed_model().encode(self.paragraphs, normalize_embeddings=True))

    def paragraph_similarity(self, a: int, b: int) -> float:
        if a >= len(self.paragraphs) or b >= len(self.paragraphs):
            return 0.0
        return _cos(self.paragraph_embeddings[a], self.paragraph_embeddings[b])

    def adjacent_paragraph_similarity(self) -> list[float]:
        return [self.paragraph_similarity(i, i + 1) for i in range(len(self.paragraphs) - 1)]

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

    def undefined_acronyms(self) -> list[str]:
        found = []
        for para in self.paragraphs:
            for ac in _ACRONYM.findall(para):
                if ac in _ALLOW:
                    continue
                if re.search(rf"\([^)]*\b{ac}\b[^)]*\)", para):
                    continue
                if ac not in found:
                    found.append(ac)
        return found

    def noun_trains(self) -> int:
        train_count = 0
        for para in self.paragraphs:
            run = 0
            for tok in _nlp()(para[:100000]):
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
        return sum(len(_PROBLEM.findall(self.paragraphs[i])) for i in self.sections.opening_paragraphs if i < len(self.paragraphs))

    def opening_method_score(self) -> int:
        return sum(len(_METHOD.findall(self.paragraphs[i])) for i in self.sections.opening_paragraphs if i < len(self.paragraphs))

    def challenge_text(self) -> str:
        i = self.sections.challenge_paragraph
        return self.paragraphs[i] if i is not None and i < len(self.paragraphs) else ""

    def resolution_text(self) -> str:
        return "\n\n".join(self.paragraphs[i] for i in self.sections.resolution_paragraphs if i < len(self.paragraphs))

    def opening_text(self) -> str:
        return "\n\n".join(self.paragraphs[i] for i in self.sections.opening_paragraphs if i < len(self.paragraphs))

    def challenge_resolution_similarity(self) -> float:
        if not self.challenge_text() or not self.resolution_text():
            return 0.0
        emb = np.asarray(_embed_model().encode([self.challenge_text(), self.resolution_text()], normalize_embeddings=True))
        return _cos(emb[0], emb[1])

    def opening_resolution_similarity(self) -> float:
        if not self.opening_text() or not self.resolution_text():
            return 0.0
        emb = np.asarray(_embed_model().encode([self.opening_text(), self.resolution_text()], normalize_embeddings=True))
        return _cos(emb[0], emb[1])

    def weak_resolution(self) -> bool:
        return bool(_WEAK_END.search(self.resolution_text()))

    def objective_only(self) -> bool:
        txt = self.challenge_text()
        return bool(_OBJECTIVE_ONLY.search(txt)) and "?" not in txt and "hypothes" not in txt.lower() and "whether" not in txt.lower()
