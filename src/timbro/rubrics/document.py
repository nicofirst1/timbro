from __future__ import annotations

from timbro.rubrics.base import RubricFinding
from timbro.rubrics.features import DocumentView
from timbro.rubrics.report import build_result
from timbro.text import strip_markup


class DocumentRubric:
    """A rubric that judges a parsed DocumentView.

    Subclasses declare `name`, `version`, `weights` and `findings(doc)`; the
    shared check() assembles the RubricResult (#192).
    """

    name: str
    version: str
    weights: dict[str, float]

    def check(self, text: str, doc: DocumentView | None = None):
        """doc is a shared DocumentView (from check_text) so the draft is parsed once
        per check call (#192); direct callers may omit it and one is built here."""
        if doc is None:
            doc = DocumentView(strip_markup(text))
        return build_result(
            rubric=self.name,
            version=self.version,
            sections=doc.sections.to_dict(),
            findings=self.findings(doc),
            weights=self.weights,
        )

    def findings(self, doc: DocumentView) -> list[RubricFinding]:
        raise NotImplementedError
