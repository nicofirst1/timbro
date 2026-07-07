from __future__ import annotations

from timbro.rubrics.density.checks import density_findings
from timbro.rubrics.features import DocumentView
from timbro.text import strip_markup
from timbro.rubrics.report import build_result

_WEIGHTS = {"density": 1.0, "jargon": 1.0}


class DensityRubric:
    name = "density"
    version = "v1"

    def check(self, text: str):
        doc = DocumentView(strip_markup(text))
        findings = density_findings(doc)
        return build_result(
            rubric=self.name,
            version=self.version,
            sections=doc.sections.to_dict(),
            findings=findings,
            weights=_WEIGHTS,
        )
