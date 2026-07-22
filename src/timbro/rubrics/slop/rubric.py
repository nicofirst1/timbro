from __future__ import annotations

from timbro.rubrics.report import build_result
from timbro.rubrics.slop.checks import DIMENSIONS, tell_findings

_WEIGHTS = {name: 1.0 for name in DIMENSIONS}


class SlopRubric:
    name = "slop"
    version = "v1"

    def __init__(self, baseline: dict[str, tuple[float, float]] | None = None):
        # baseline from timbro.tells.tell_baseline switches on corpus-relative mode
        # (`slop --profile`); None keeps the default absolute, corpus-free detection.
        self.baseline = baseline

    def check(self, text: str):
        # Tells are lexical/positional and location-agnostic; no section map needed.
        return build_result(
            rubric=self.name,
            version=self.version,
            sections={},
            findings=tell_findings(text, self.baseline),
            weights=_WEIGHTS,
        )
