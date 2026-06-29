from __future__ import annotations

from dataclasses import dataclass, asdict


@dataclass(frozen=True)
class SectionMap:
    opening_paragraphs: list[int]
    challenge_paragraph: int | None
    resolution_paragraphs: list[int]
    body_paragraphs: list[int]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RubricFinding:
    severity: str
    dimension: str
    rule: str
    paragraph: int | None
    sentence: int | None
    span: str
    message: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RubricResult:
    rubric: str
    version: str
    overall: float
    verdict: str
    dimensions: dict[str, float]
    sections: dict
    findings: list[RubricFinding]

    def to_dict(self) -> dict:
        return {
            "rubric": self.rubric,
            "version": self.version,
            "overall": self.overall,
            "verdict": self.verdict,
            "dimensions": self.dimensions,
            "sections": self.sections,
            "findings": [f.to_dict() for f in self.findings],
        }
