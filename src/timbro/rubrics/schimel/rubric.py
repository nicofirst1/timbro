from __future__ import annotations

from timbro.rubrics.features import DocumentView
from timbro.rubrics.report import build_result
from timbro.rubrics.rules import schimel_findings
from timbro.text import strip_markup


class SchimelRubric:
    name = "schimel"
    version = "v3"

    def check(self, text: str, doc: DocumentView | None = None):
        """doc is a shared DocumentView (from check_text) so the draft is parsed once
        per check call (#192); direct callers may omit it and one is built here."""
        if doc is None:
            doc = DocumentView(strip_markup(text))
        findings = schimel_findings(doc)
        return build_result(
            rubric=self.name,
            version=self.version,
            sections=doc.sections.to_dict(),
            findings=findings,
        )
