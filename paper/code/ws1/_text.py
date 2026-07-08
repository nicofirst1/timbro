"""Shared SKILL.md text parsing + all-string parquet assembly for WS1 builders.

Kept out of _manifest.py on purpose: that module owns git/hash/provenance
bookkeeping; corpus text parsing is a different concern.
"""
from __future__ import annotations

import re

import pyarrow as pa

# Leading `--- ... ---` frontmatter fence, tolerant of BOTH \n and \r\n endings.
# The \r\n tolerance is load-bearing: skill-diffs ships CRLF SKILL.md files, and a
# \n-only pattern silently fails to match on them, leaving raw YAML frontmatter
# embedded in the body (WS3 then runs linguistic features over the YAML). Keep the
# [\r\n]+ classes — do not "simplify" them back to literal \n.
_FRONTMATTER_RE = re.compile(r"^---[\r\n]+(.*?)[\r\n]+---[\r\n]+(.*)$", re.DOTALL)


def extract_frontmatter(text: str | None) -> tuple[str, str | None]:
    """Split a SKILL.md into (body_without_frontmatter, raw_frontmatter_or_None)."""
    if not text:
        return text or "", None
    m = _FRONTMATTER_RE.match(text)
    if m:
        return m.group(2), m.group(1)
    return text, None


def string_table(rows: list[dict], columns: list[str]) -> pa.Table:
    """All-string pyarrow Table with exactly `columns`; missing keys become null."""
    schema = pa.schema([(c, pa.string()) for c in columns])
    arrays = [pa.array([r.get(c) for r in rows], type=pa.string()) for c in columns]
    return pa.table({c: a for c, a in zip(columns, arrays)}, schema=schema)
