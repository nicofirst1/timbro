"""The one payload both the CLI and the MCP server return: score + flow."""

from timbro.flow import flow_report, paragraphs


def voice_report(model, text: str) -> dict:
    """Full report for a draft: {distance, direction, flow}. Flow is null on snippets."""
    out = model.score(text).to_dict()
    out["flow"] = flow_report(text).to_dict() if len(paragraphs(text)) >= 4 else None
    return out
