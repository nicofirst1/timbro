"""The one payload both the CLI and the MCP server return: score + flow."""

from timbro.cleanup import preprocess_runtime_text
from timbro.flow import flow_report, paragraphs


def voice_report(model, text: str) -> dict:
    """Full report for a draft: {distance, direction, flow}. Flow is null on snippets."""
    prepared = preprocess_runtime_text(text)
    out = model.score(prepared).to_dict()
    out["flow"] = flow_report(prepared).to_dict() if len(paragraphs(prepared)) >= 4 else None
    return out
