from __future__ import annotations

from timbro.rubrics.density.checks import density_findings
from timbro.rubrics.document import DocumentRubric

_WEIGHTS = {"density": 1.0, "jargon": 1.0}


class DensityRubric(DocumentRubric):
    name = "density"
    version = "v1"
    weights = _WEIGHTS

    def findings(self, doc):
        return density_findings(doc)
