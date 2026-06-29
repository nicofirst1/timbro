from __future__ import annotations

from timbro.rubrics.schimel import SchimelRubric


def get_rubric(name: str):
    if name == "schimel":
        return SchimelRubric()
    raise KeyError(f"Unknown rubric: {name}")
