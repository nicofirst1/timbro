from __future__ import annotations

from timbro.rubrics.document import DocumentRubric
from timbro.rubrics.report import _WEIGHTS
from timbro.rubrics.rules import schimel_findings


class SchimelRubric(DocumentRubric):
    name = "schimel"
    version = "v3"
    weights = _WEIGHTS

    def findings(self, doc):
        return schimel_findings(doc)
