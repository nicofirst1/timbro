from __future__ import annotations

import re

from timbro.rubrics.base import SectionMap
from timbro.text import split_paragraphs, split_sentences  # noqa: F401  (re-export)

_CHALLENGE = re.compile(
    r"\b(?:we (?:ask|test|hypothesi[sz]e|predict)|our (?:question|hypothesis)|"
    r"remains unclear|unknown|knowledge gap|objective(?:s)? (?:was|were|is|are)|"
    r"to determine|to test whether|whether)\b",
    re.I,
)


def detect_sections(paragraphs: list[str]) -> SectionMap:
    n = len(paragraphs)
    if not n:
        return SectionMap([], None, [], [])

    opening = list(range(min(2, n)))
    search_end = min(n, max(2, (n + 2) // 3))
    challenge = None
    best = 0
    for i in range(search_end):
        score = len(_CHALLENGE.findall(paragraphs[i]))
        if score > best:
            best = score
            challenge = i
    resolution = [n - 1]
    body = [i for i in range(n) if i not in opening and i not in resolution and i != challenge]
    return SectionMap(opening, challenge, resolution, body)
