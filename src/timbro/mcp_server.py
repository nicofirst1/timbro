"""Phase 5: thin MCP wrapper. One tool, score_voice(text) -> {distance, direction, flow}.

Fit is lazy + cached: the model loads from the corpus dirs (env-overridable) on the
first call. Point TIMBRO_EXEMPLARS / TIMBRO_CONTRAST at your own corpora.

Run: uv run timbro-mcp   (stdio transport)
"""

import os
from functools import lru_cache

from mcp.server.fastmcp import FastMCP

from timbro.core import VoiceModel
from timbro.flow import flow_report, paragraphs

mcp = FastMCP("timbro")


@lru_cache(maxsize=1)
def _model() -> VoiceModel:
    return VoiceModel.from_dir(
        os.environ.get("TIMBRO_EXEMPLARS", "data/exemplars"),
        contrast=os.environ.get("TIMBRO_CONTRAST", "data/contrast"),
    )


@mcp.tool()
def score_voice(text: str) -> dict:
    """Measure how far `text` sits from the seeded voice.

    Returns the embedding distance (smaller = more like the voice), a named,
    confidence-weighted revision direction (which features to move and which way),
    and flow metrics (trajectory + circle-back). Flow is null for very short text.
    """
    result = _model().score(text).to_dict()
    # flow needs a few paragraphs to have an arc; skip it on snippets
    result["flow"] = flow_report(text).to_dict() if len(paragraphs(text)) >= 4 else None
    return result


def main():
    mcp.run()


if __name__ == "__main__":
    main()
