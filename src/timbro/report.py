"""The one payload both the CLI and the MCP server return: score + flow."""

from timbro.cleanup import preprocess_runtime_text
from timbro.flow import flow_report, paragraphs


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
    out["spans"] = _span_guidance(model, prepared)
    out["flow"] = flow_report(prepared).to_dict() if len(paragraphs(prepared)) >= 4 else None
    return out
