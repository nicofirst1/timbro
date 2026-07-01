from __future__ import annotations

from timbro.rubrics.features import DocumentView
from timbro.rubrics.report import build_result
from timbro.rubrics.rules import schimel_findings


class SchimelRubric:
    name = "schimel"
    version = "v3"

    def check(self, text: str):
        doc = DocumentView(text)
        findings = schimel_findings(doc)
        return build_result(
            rubric=self.name,
            version=self.version,
            sections=doc.sections.to_dict(),
            findings=findings,
        )
