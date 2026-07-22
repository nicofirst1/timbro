"""Phase 5: thin MCP wrapper. One tool, score_voice(text) -> {distance, direction, flow}.

Fit is lazy + cached: the model loads from the corpus dirs (env-overridable) on the
first call. Point TIMBRO_EXEMPLARS / TIMBRO_CONTRAST at your own corpora.

Run: uv run timbro-mcp   (stdio transport)
"""

from functools import lru_cache

from mcp.server.fastmcp import FastMCP

from timbro.model import VoiceModel, default_model
from timbro.report import voice_report
from timbro.rewrite import evaluate_rewrite
from timbro.rubrics import check_text

mcp = FastMCP("timbro")


@lru_cache(maxsize=1)
def _model() -> VoiceModel:
    return default_model()


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


@mcp.tool()
def check_voice(text: str, rubric: str = "schimel", profile: str | None = None) -> dict:
    """Run a deterministic writing rubric over `text` (no model, no voice corpus, no LLM-as-judge).

    Returns a structured verdict (pass/warn/fail), per-dimension scores, and located findings.

    Pick the rubric by the question you're answering:
    - `slop` — does this read AI-generated? Catches the mechanical AI-slop tells: em/en
      dashes, "it's not X, it's Y", delve/tapestry/leverage diction, signposting and wrap-up
      phrases, emoji, curly quotes, bold lead-in bullets, and uniform/staccato rhythm. Use
      this for "check for AI slop", "does this sound like an LLM wrote it", "de-slop this".
    - `schimel` (default) — is this good prose? Weak opening, objective-only challenge,
      resolution that doesn't answer or closes on a caveat, broken circle-back, undefined
      acronyms, fuzzy verbs, nominalization, noun trains, overloaded sentences, stacked
      adjectives, inline number-ladders, and coy/deferral phrasing.

    `profile` (slop only): baseline the tells against that profile's exemplar corpus, so a
    draft is flagged only where it overuses a tell versus *your* norm — not against zero.
    Use it when a voice legitimately uses some tells (an em-dash habit) and you only want
    the drift called out.

    This is the second pair of eyes a draft's author cannot reliably be: it grades text
    mechanically, so use it instead of self-reporting that a rubric pass was run.
    """
    return check_text(text, rubric=rubric, profile=profile).to_dict()


def main():
    mcp.run()


if __name__ == "__main__":
    main()
