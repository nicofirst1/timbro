from __future__ import annotations

from timbro.rubrics.registry import get_rubric


def check_text(text: str, rubric: str = "schimel"):
    return get_rubric(rubric).check(text)


__all__ = ["check_text", "get_rubric"]
