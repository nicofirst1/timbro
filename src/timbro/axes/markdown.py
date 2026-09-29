"""Markdown-structure axis (#28) as a registered `Metric`, moved verbatim from
model.py (#106) into the axes package -- a peer of hedge/fw/concreteness/richness,
not VoiceModel-internal machinery. See timbro.metric for the Metric protocol."""

from __future__ import annotations

from functools import lru_cache

from timbro.metric import Reference, register


@lru_cache(maxsize=512)
def _struct_vec(text: str) -> tuple[float, ...]:
    """Markdown-structure feature vector (STRUCT_AXIS_NAMES order) for one raw document.
    Reuses analyze._struct_features -- the same extractor `timbro analyze` emits, so
    scoring and analysis never drift. Ratio axes are None on empty input; coerce to 0.0
    (no structure == zero structure) so a draft with no markdown never breaks z-scoring.
    """
    from timbro.analyze import (
        _struct_features,  # lazy: a module-level import closes model -> axes.markdown -> analyze -> model.direction
    )

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
