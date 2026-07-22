from __future__ import annotations

from timbro.rubrics.report import build_result
from timbro.rubrics.slop.checks import DIMENSIONS, tell_findings

_WEIGHTS = {name: 1.0 for name in DIMENSIONS}


class SlopRubric:
    name = "slop"
    version = "v1"

    def check(self, text: str):
        # Tells are lexical/positional and location-agnostic; no section map needed.
        return build_result(
            rubric=self.name,
            version=self.version,
            sections={},
            findings=tell_findings(text),
            weights=_WEIGHTS,
        )
