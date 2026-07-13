"""The one payload both the CLI and the MCP server return: score + flow."""

from timbro.cleanup import preprocess_runtime_text
from timbro.flow import flow_report, paragraphs
from timbro.text import split_sentences


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
    out["spans"] = _span_guidance(model, prepared)
    out["flow"] = flow_report(prepared).to_dict() if len(paragraphs(prepared)) >= 4 else None
    return out
