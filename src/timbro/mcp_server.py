"""Phase 5: thin MCP wrapper. One tool, score_voice(text) -> {distance, direction, flow}.

Fit is lazy + cached: the model loads from the corpus dirs (env-overridable) on the
first call. Point TIMBRO_EXEMPLARS / TIMBRO_CONTRAST at your own corpora.

Run: uv run timbro-mcp   (stdio transport)
"""

import os
from functools import lru_cache

from mcp.server.fastmcp import FastMCP

from timbro.core import VoiceModel
from timbro.report import voice_report
from timbro.rewrite import evaluate_rewrite

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
    return voice_report(_model(), text)


@mcp.tool()
def accept_rewrite(original: str, revised: str) -> dict:
    """Judge a candidate rewrite. Returns whether it's accepted -- i.e. it moved
    CLOSER to the voice (distance_after < distance_before) WITHOUT changing meaning
    (content similarity > 0.85) -- plus the before/after distances and similarity.

    Use in a loop: score_voice -> rewrite toward the direction -> accept_rewrite.
    """
    return evaluate_rewrite(_model(), original, revised)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
