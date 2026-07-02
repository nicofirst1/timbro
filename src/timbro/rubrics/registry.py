from __future__ import annotations

from timbro.rubrics.density import DensityRubric
from timbro.rubrics.schimel import SchimelRubric


def get_rubric(name: str):
    if name == "schimel":
        return SchimelRubric()
    if name == "density":
        return DensityRubric()
    raise KeyError(f"Unknown rubric: {name}")
