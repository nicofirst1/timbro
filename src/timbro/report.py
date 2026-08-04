"""Formats VoiceModel results for humans: axis dataclasses, hint labels, and the
one payload both the CLI and the MCP server return (score + flow).

Split from model.py (PR #57 review) -- model.py keeps the statistical model
(corpus loading, spaCy pipeline, feature extraction, z-scores/distances, Metric
orchestration); this module formats those results as named advice. Imports
from model only where needed (never the reverse -- model.py imports the
dataclasses/constants below to build and return them).
"""

from dataclasses import asdict, dataclass

from timbro.cleanup import preprocess_runtime_text
from timbro.flow import flow_report, paragraphs
from timbro.tells import TELL_LABEL
from timbro.text import split_sentences

# Plain-English labels so the direction reads as advice, not tag soup.
POS_LABEL = {
    "ADJ": "adjectives", "ADP": "prepositions", "ADV": "adverbs",
    "AUX": "auxiliary verbs", "CCONJ": "conjunctions", "DET": "determiners",
    "INTJ": "interjections", "NOUN": "nouns", "NUM": "numbers", "PART": "particles",
    "PRON": "pronouns", "PROPN": "proper nouns", "PUNCT": "punctuation",
    "SCONJ": "subordinating conjunctions", "SYM": "symbols", "VERB": "verbs", "X": "other tokens",
}


def _label(name: str) -> str:
    """POS or tell label for a feature, so the hint reads as advice not a feature id."""
    return POS_LABEL[name[4:]] if name.startswith("pos_") else TELL_LABEL[name[5:]]


@dataclass
class FeatureMove:
    feature: str
    current_z: float
    delta: float        # signed move toward your corpus mean (target z = 0)
    confidence: float   # R^2: how reliably this feature marks your voice (0-1)
    hint: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MarkdownAxis:
    """One markdown-structure axis: where the draft sits vs the corpus (z-score) and the
    named direction back toward the corpus pole. Separate from FeatureMove -- struct is a
    standalone axis group, not part of the embedding/POS composite (issue #28)."""
    axis: str
    value: float        # the draft's raw feature value on this axis
    corpus_mean: float
    z: float            # draft's distance from corpus mean in corpus std units (0 = on-target)
    direction: str      # imperative phrase toward the corpus mean, "" once |z| is negligible

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HedgeAxis:
    """One hedge/booster stance axis: where the draft sits vs the reference (prior, or
    prior blended with the profile corpus) and the named direction back toward it.
    Mirrors `MarkdownAxis`'s shape/naming; unlike markdown this axis always has a
    reference (the declared prior), so it reports even with no corpus."""
    axis: str
    value: float           # the draft's raw rate on this axis (per 1000 words)
    reference_mean: float  # prior, or prior blended with the corpus (Reference.blend)
    z: float                # draft's distance from reference_mean in reference-spread units
    direction: str          # imperative phrase toward the reference, "" once |z| is negligible

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FwAxis:
    """One function-word axis: where the draft sits vs the reference (prior, or prior
    blended with the profile corpus) and the named direction back toward it. Mirrors
    `HedgeAxis`'s shape/naming; always has a reference (the declared prior), so it
    reports even with no corpus."""
    axis: str
    value: float           # the draft's raw rate on this axis (per 1000 words)
    reference_mean: float  # prior, or prior blended with the corpus (Reference.blend)
    z: float                # draft's distance from reference_mean in reference-spread units
    direction: str          # imperative phrase toward the reference, "" once |z| is negligible

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ConcretenessAxis:
    """The concreteness axis: where the draft sits vs the reference (prior, or prior
    blended with the profile corpus) and the named direction back toward it. Same shape
    as `HedgeAxis` -- always has a reference, so it reports even with no corpus (#46)."""
    axis: str
    value: float           # the draft's raw mean concreteness (1-5 scale)
    reference_mean: float  # prior, or prior blended with the corpus (Reference.blend)
    z: float                # draft's distance from reference_mean in reference-spread units
    direction: str          # imperative phrase toward the reference, "" once |z| is negligible

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ScoreResult:
    distance: float           # StyleDistance embedding kNN distance to your voice cloud
    direction: list[FeatureMove]

    def to_dict(self) -> dict:
        return {"distance": self.distance, "direction": [m.to_dict() for m in self.direction]}


# Markdown-structure axes scored as a SEPARATE group from the embedding/POS composite
# (issue #28) -- these never feed the distance/direction above, they get their own
# z-score-vs-corpus report. Each axis carries an imperative revision phrase per
# direction, (raise, lower), matching the "fewer/more <label>" register of the POS
# direction. Only structural (`struct_*`) numeric axes a writer can actually move are
# listed; the frontmatter-description (`fm_desc_*`) and string fields are excluded.
MARKDOWN_AXES: tuple[tuple[str, str, str], ...] = (
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
# ponytail: fixed tolerance, promote to a knob only if a caller needs to tune it.
MARKDOWN_Z_TOL = 0.5

# Hedge/booster axis labels (#44): (axis, raise_hint, lower_hint), same shape as
# MARKDOWN_AXES. "raise" fires when the draft sits below the reference (needs more of
# the marker); "lower" fires above it.
HEDGE_AXES: tuple[tuple[str, str, str], ...] = (
    ("hedge_rate", "hedge claims more (might/perhaps/seems)", "hedge claims less, state more directly"),
    ("booster_rate", "assert claims more directly (clearly/must/in fact)", "soften strong claims"),
)
HEDGE_Z_TOL = 0.5

# Function-word axis labels (#45): (axis, raise_hint, lower_hint), same shape as
# HEDGE_AXES. "raise" fires when the draft sits below the reference (needs more of the
# marker); "lower" fires above it.
FW_AXES: tuple[tuple[str, str, str], ...] = (
    ("first_person_sg", "use more first-person singular (I/me/my)", "use less first-person singular"),
    ("article_rate", "add more articles (a/an/the)", "trim articles"),
    ("preposition_rate", "add more prepositions", "trim prepositions"),
    ("conjunction_rate", "add more conjunctions", "trim conjunctions"),
    ("pronoun_rate", "add more pronouns", "trim pronouns"),
)
FW_Z_TOL = 0.5

# Concreteness axis labels (#46): (axis, raise_hint, lower_hint), same shape as
# HEDGE_AXES. "raise" fires when the draft sits below the reference (needs more concrete
# language); "lower" fires above it (draft leans more concrete than the reference).
CONCRETENESS_AXES: tuple[tuple[str, str, str], ...] = (
    ("mean_concreteness", "use more concrete, physical language", "use more abstract language"),
)
CONCRETENESS_Z_TOL = 0.5


def _local_direction(model, text: str, top_k: int = 2) -> list[dict]:
    return [
        {"hint": move.hint, "confidence": move.confidence, "feature": move.feature}
        for move in model.score(text).direction[:top_k]
    ]


def _top_sentence(model, paragraph: str) -> dict | None:
    candidates = split_sentences(paragraph, min_words=8)
    if not candidates:
        return None
    scored = [{"text": s, "distance": model._dist(s)} for s in candidates]
    best = max(scored, key=lambda row: row["distance"])
    best["direction"] = _local_direction(model, best["text"], top_k=2)
    return best


def _span_guidance(model, text: str, top_k: int = 3) -> list[dict]:
    paras = paragraphs(text)
    if len(paras) < 2:
        return []
    scored = [
        {
            "index": i + 1,
            "distance": model._dist(p),
            "distance_z": model.normalized_distance(p),
            "text": p[:280],
            "direction": _local_direction(model, p, top_k=3),
            "sentence": _top_sentence(model, p),
        }
        for i, p in enumerate(paras)
    ]
    return sorted(scored, key=lambda row: row["distance"], reverse=True)[:top_k]


def voice_report(model, text: str) -> dict:
    """Full report for a draft: {distance, direction, flow}. Flow is null on snippets."""
    prepared = preprocess_runtime_text(text)
    out = model.score(prepared).to_dict()
    out["distance_z"] = model.normalized_distance(prepared)
    out["on_voice"] = model.on_voice(prepared)
    out["profile"] = model.profile_report()
    # Structure runs on the raw draft (markdown intact), not the markup-stripped `prepared`
    # text -- struct features live in the markup itself (#28). Separate axis group.
    out["markdown"] = [axis.to_dict() for axis in model.markdown_report(text)]
    # Hedge/booster (#44): standalone axis group, same treatment as markdown -- runs on
    # the markup-stripped `prepared` text since stance markers are prose, not markup.
    out["hedge"] = [axis.to_dict() for axis in model.hedge_report(prepared)]
    # Function words (#45): standalone axis group, same treatment as hedge -- runs on the
    # markup-stripped `prepared` text since pronoun/article/preposition density is prose.
    out["fw"] = [axis.to_dict() for axis in model.fw_report(prepared)]
    # Concreteness (#46): standalone axis group, same treatment as hedge -- runs on the
    # markup-stripped `prepared` text since word choice is prose, not markup.
    out["concreteness"] = [axis.to_dict() for axis in model.concreteness_report(prepared)]
    out["spans"] = _span_guidance(model, prepared)
    out["flow"] = flow_report(prepared).to_dict() if len(paragraphs(prepared)) >= 4 else None
    return out
