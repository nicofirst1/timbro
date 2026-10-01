"""Markdown-structure axis (#28) as a registered `Metric` -- a peer of
hedge/fw/concreteness/richness in the axes package, not VoiceModel-internal
machinery. See timbro.metric for the Metric protocol."""

from __future__ import annotations

import json
import re
from functools import lru_cache

import yaml

from timbro.metric import Reference, register
from timbro.spacy_model import cached_pipeline
from timbro.text import strip_markup

_FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*\n?", re.DOTALL)
_FENCE = re.compile(r"(```|~~~).*?\1", re.DOTALL)
_HEADING = re.compile(r"(?m)^[ \t]*(#{1,6})[ \t]+.*$")
_TABLE_SEPARATOR = re.compile(r"(?m)^[ \t]*:?-{2,}:?(?:[ \t]*\|[ \t]*:?-{2,}:?)+[ \t]*$")
_BULLET_LIST = re.compile(r"^[ \t]*[-*+][ \t]+")
_ORDERED_LIST = re.compile(r"^[ \t]*\d+\.[ \t]+")
_BLANK_LINE = re.compile(r"\n[ \t]*\n")
_SENTENCE_END = re.compile(r"[.!?]+")  # naive sentence count; _struct runs without spaCy

# Folk-advice exploratory features (#21).
_INLINE_CODE_SPAN = re.compile(r"`([^`\n]+)`")
_MD_LINK = re.compile(r"\[(.*?)\]\((.*?)\)")
_EXTERNAL_REF = re.compile(r"(scripts/|references/|assets/)[^\s)\]]*")
_NAMED_SECTIONS = (
    "examples", "guidelines", "when to use", "procedure", "pitfalls", "usage", "instructions",
)
_NAME_FORMAT = re.compile(r"[a-z0-9-]{1,64}")
_HEADING_MARK = re.compile(r"^[ \t]*#{1,6}[ \t]+")
_FM_WHEN_CLAUSE = re.compile(r"\b(when|use (this|it) (when|for|to)|whenever|if you)\b", re.IGNORECASE)
_FM_OR_WORD = re.compile(r"\bor\b", re.IGNORECASE)
_FM_WILDCARD = re.compile(r"\b(any|all|every|always|whenever|anything|everything)\b", re.IGNORECASE)


def _struct_features(raw: str) -> tuple[dict, str]:
    n = len(raw)
    headings = list(_HEADING.finditer(raw))
    code_chars = sum(len(m.group(0)) for m in _FENCE.finditer(raw))
    lines = raw.split("\n")
    non_blank = [ln for ln in lines if ln.strip()]
    ordered_lines = sum(1 for ln in lines if _ORDERED_LIST.match(ln))
    bullet_lines = sum(1 for ln in lines if _BULLET_LIST.match(ln))
    list_lines = ordered_lines + bullet_lines
    prose = strip_markup(raw)

    inline_chars = sum(len(s) for s in _INLINE_CODE_SPAN.findall(_FENCE.sub("", raw)))

    # External refs: bare scripts//references//assets/ tokens (with markdown links
    # collapsed to their text) plus the same pattern inside every link target.
    bare_refs = len(_EXTERNAL_REF.findall(_MD_LINK.sub(lambda m: m.group(1), raw)))
    target_refs = sum(len(_EXTERNAL_REF.findall(m.group(2))) for m in _MD_LINK.finditer(raw))

    named_section = 0
    for m in headings:
        htext = _HEADING_MARK.sub("", m.group(0)).strip().lower()
        if any(s in htext for s in _NAMED_SECTIONS):
            named_section = 1
            break

    # Long-paragraph ratio (#22): split blank-line-delimited paragraphs of the raw text with
    # frontmatter and fenced code removed, so neither is double-counted as prose.
    without_fences = _FENCE.sub("", _FRONTMATTER.sub("", raw))
    paragraphs = [p for p in _BLANK_LINE.split(without_fences) if p.strip()]
    long_paragraphs = sum(1 for p in paragraphs if len(_SENTENCE_END.findall(p)) > 6)

    frontmatter = {}
    fm_match = _FRONTMATTER.match(raw)
    if fm_match:
        try:
            loaded = yaml.safe_load(fm_match.group(1))
        except yaml.YAMLError:
            loaded = None
        if isinstance(loaded, dict):
            frontmatter = loaded

    name = frontmatter.get("name")
    description = frontmatter.get("description")
    if isinstance(description, str) and description:
        # Only len(doc) is consumed, and spaCy pipeline components never retokenize: the bare
        # tokenizer counts exactly what the full pipeline (same en_core_web_sm tokenizer) would.
        fm_tokens = len(
            cached_pipeline(("ner", "lemmatizer", "parser"), ()).tokenizer(description)
        )
        wildcards = len(_FM_WILDCARD.findall(description))
        fm_desc = {
            "fm_desc_present": 1,
            "fm_desc_tokens": fm_tokens,
            "fm_desc_when_clause": 1 if _FM_WHEN_CLAUSE.search(description) else 0,
            "fm_desc_or_count": len(_FM_OR_WORD.findall(description)),
            "fm_desc_wildcard_per_token": wildcards / fm_tokens if fm_tokens else 0,
        }
    else:
        fm_desc = {
            "fm_desc_present": 0,
            "fm_desc_tokens": 0,
            "fm_desc_when_clause": 0,
            "fm_desc_or_count": 0,
            "fm_desc_wildcard_per_token": 0,
        }

    struct = {
        "struct_heading_count": len(headings),
        "struct_max_heading_depth": max((len(m.group(1)) for m in headings), default=0),
        "struct_code_char_ratio": code_chars / n if n else None,
        "struct_list_item_ratio": list_lines / len(non_blank) if non_blank else None,
        "struct_table_count": len(_TABLE_SEPARATOR.findall(raw)),
        "struct_prose_ratio": len(prose) / n if n else None,
        "struct_frontmatter_field_count": len(frontmatter),
        "struct_line_count": len(lines) if raw else 0,
        "struct_inline_code_char_ratio": inline_chars / n if n else 0.0,
        "struct_ordered_list_ratio": ordered_lines / len(non_blank) if non_blank else 0.0,
        "struct_bullet_list_ratio": bullet_lines / len(non_blank) if non_blank else 0.0,
        "struct_external_ref_count": bare_refs + target_refs,
        "struct_named_section_present": named_section,
        "struct_name_format_valid": 1 if isinstance(name, str) and _NAME_FORMAT.fullmatch(name) else 0,
        "struct_long_paragraph_ratio": long_paragraphs / len(paragraphs) if paragraphs else 0.0,
        **fm_desc,
        "frontmatter_json": json.dumps(frontmatter, default=str),
    }
    return struct, prose


@lru_cache(maxsize=512)
def _struct_vec(text: str) -> tuple[float, ...]:
    """Markdown-structure feature vector (STRUCT_AXIS_NAMES order) for one raw document.
    Ratio axes are None on empty input; coerce to 0.0 (no structure == zero structure)
    so a draft with no markdown never breaks z-scoring.
    """
    struct, _ = _struct_features(text)
    return tuple(float(struct.get(name) or 0.0) for name in STRUCT_AXIS_NAMES)


class _MarkdownMetric:
    """Markdown-structure axis group as a `Metric`. `extract` returns the struct feature
    vector in `STRUCT_AXIS_NAMES` order for one raw document."""

    # Markdown-structure axes scored as a SEPARATE group from the embedding/POS composite
    # (issue #28) -- these never feed the distance/direction, they get their own
    # z-score-vs-corpus report. Each axis carries an imperative revision phrase per
    # direction, (axis, raise_hint, lower_hint), matching the "fewer/more <label>"
    # register of the POS direction. "raise" fires when the draft sits below the corpus
    # mean; "lower" fires above it. Only structural (`struct_*`) numeric axes a writer
    # can actually move are listed; the frontmatter-description (`fm_desc_*`) and string
    # fields are excluded.
    hint_axes: tuple[tuple[str, str, str], ...] = (
        ("struct_heading_count", "add section headings", "merge section headings"),
        ("struct_max_heading_depth", "deepen sectioning", "flatten sectioning"),
        ("struct_code_char_ratio", "add code blocks", "reduce code blocks"),
        ("struct_inline_code_char_ratio", "add inline code", "reduce inline code"),
        ("struct_list_item_ratio", "add lists", "reduce list share"),
        ("struct_bullet_list_ratio", "add bullets", "reduce bullet share"),
        ("struct_ordered_list_ratio", "add numbered steps", "reduce numbered steps"),
        ("struct_table_count", "add tables", "remove tables"),
        ("struct_external_ref_count", "add external references", "trim external references"),
        ("struct_long_paragraph_ratio", "lengthen paragraphs", "break up long paragraphs"),
        ("struct_prose_ratio", "add prose", "reduce prose"),
    )
    # Fixed tolerance; promote to a knob only if a caller needs to tune it.
    z_tol: float = 0.5

    name = "markdown"
    axes = tuple(a for a, _, _ in hint_axes)
    # Structural neutral placeholder, not a tunable prior (those live in priors.py): this
    # axis group runs only contrastively today -- the reference is corpus-derived at fit
    # (see VoiceModel.fit) and `axis_report` returns [] with no corpus stats. Derived
    # from `axes` so the length can't drift from the hint tuple.
    prior = Reference(
        mean=tuple(0.0 for _ in axes),
        spread=tuple(1.0 for _ in axes),
        strength=0.0,
    )

    def extract(self, text: str) -> tuple[float, ...]:
        return _struct_vec(text)


MARKDOWN_METRIC = register(_MarkdownMetric())

STRUCT_AXIS_NAMES: tuple[str, ...] = MARKDOWN_METRIC.axes
