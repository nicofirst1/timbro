"""Formats VoiceModel results for humans: axis dataclasses, hint labels, and the
one payload the CLI returns (score + flow).

Split from model.py (PR #57 review) -- model.py keeps the statistical model
(corpus loading, spaCy pipeline, feature extraction, z-scores/distances, Metric
orchestration); this module formats those results as named advice. Imports
from model only where needed (never the reverse -- model.py imports the dataclasses
below to build and return them).
"""

from dataclasses import asdict, dataclass

from timbro.axes.politeness import politeness_report as _politeness_report
from timbro.axes.tells import TELL_LABEL
from timbro.cleanup import preprocess_runtime_text
from timbro.flow import flow_report, paragraphs
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
class AxisReport:
    """One blend-style axis (#108): where the draft sits vs the reference and the named
    direction back toward it. Two cases share this shape: the reference is the declared
    prior blended with the profile corpus (`Reference.blend`, hedge/fw/concreteness/
    richness), or corpus-only for markdown (prior strength 0, so the corpus mean/std
    pass through unchanged). Standalone axis groups -- never part of the embedding
    distance or POS direction."""
    axis: str
    value: float           # the draft's raw value on this axis
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
    # Readability/richness/entropy (#88): standalone axis group, same treatment as hedge
    # -- runs on the markup-stripped `prepared` text since these are prose measures, not
    # markup. Tier B/C per ADR-0005: reported for information, does not feed the scored
    # POS/embedding direction.
    out["richness"] = [axis.to_dict() for axis in model.richness_report(prepared)]
    # Politeness strategies (#94): reporting-only axis, no corpus/prior involved -- `None`
    # ("not applicable") when zero of the 20 DNM strategies fire, which is the expected
    # case for narrative/expository prose. Never touches the embedding distance or POS
    # direction; runs on the markup-stripped `prepared` text like hedge/fw/concreteness.
    out["politeness"] = _politeness_report(prepared)
    out["spans"] = _span_guidance(model, prepared)
    out["flow"] = flow_report(prepared).to_dict() if len(paragraphs(prepared)) >= 4 else None
    return out
