"""Phase 4: content-preservation guard for voice rewrites.

The non-negotiable on any rewrite is that it changes *how* the text reads, never
*what* it says. This guard makes that falsifiable: semantic cosine between original
and revised via a general (content-bearing) sentence model -- NOT the style model,
which is trained to ignore content. Gate: similarity > 0.85 (PLAN sec 7/8).

The rewrite *engine* (TinyStyler / a local model) plugs in separately; this guard
is what validates whatever it produces.
"""

from __future__ import annotations

import numpy as np

from timbro.flow import _model  # all-MiniLM-L6-v2: general semantic embedding


def content_similarity(original: str, revised: str) -> float:
    """Semantic cosine in [0, 1-ish]. High = same meaning, regardless of style."""
    e = _model().encode([original, revised], normalize_embeddings=True)
    return float(np.dot(e[0], e[1]))


def preserves_content(original: str, revised: str, threshold: float = 0.85) -> tuple[bool, float]:
    """(passes, similarity). A rewrite is only valid if it clears the threshold."""
    sim = content_similarity(original, revised)
    return sim >= threshold, sim


def evaluate_rewrite(model, original: str, revised: str, threshold: float = 0.85) -> dict:
    """Close the rewrite loop: a candidate is accepted only if it moved CLOSER to the
    voice AND kept the meaning. The engine lives in the calling agent; Timbro judges."""
    content_ok, sim = preserves_content(original, revised, threshold)
    before = model.score(original).distance
    after = model.score(revised).distance
    improved = after < before
    return {
        "accepted": content_ok and improved,
        "content_ok": content_ok,
        "similarity": sim,
        "distance_before": before,
        "distance_after": after,
        "improved": improved,
    }


if __name__ == "__main__":
    base = "The committee approved the budget after a long debate about research funding."
    paraphrase = "Following lengthy discussion on research funding, the budget got the committee's approval."
    unrelated = "A cat slept on the warm windowsill all afternoon while it rained outside."

    ok_p, sim_p = preserves_content(base, paraphrase)
    ok_u, sim_u = preserves_content(base, unrelated)
    assert ok_p, f"paraphrase should preserve content: {sim_p:.2f}"
    assert not ok_u, f"unrelated text should fail the guard: {sim_u:.2f}"
    print(f"ok: paraphrase={sim_p:.2f} (pass) > unrelated={sim_u:.2f} (fail), threshold 0.85")
