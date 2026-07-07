"""Phase 3 flow layer -- GATE FIRST.

Before building named flow features (speed/volume/circle-back/TAACO), prove that
paragraph ORDER is even discriminative at this doc length. The measuring stick is
one order-sensitive scalar: mean adjacent-paragraph cosine (local coherence).

Two gates (PLAN sec 7/8), run per document and averaged:
  - insertion test: pull each interior paragraph, find the slot that maximises
    coherence; the original slot should win (rank-1). The stronger gate at ~15 paras.
  - shuffle test: original order should beat >80% of random permutations on coherence.

If insertion ~ chance and shuffle < 60%, order isn't signal here -> drop the flow
layer entirely. # ponytail: no flow features until these gates earn them.

Usage: uv run python -m timbro.flow data/exemplars
"""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass

import numpy as np

from timbro.model import read_corpus
from timbro.text import _model, split_paragraphs


def paragraphs(text: str, min_words: int = 15) -> list[str]:
    # min_words drops markdown headers / one-liners; code fences may survive.
    # ponytail: accept that noise; strip fences only if the gate is borderline.
    return split_paragraphs(text, min_words)


def embed(paras: list[str]) -> np.ndarray:
    return _model().encode(paras, normalize_embeddings=True)


def coherence(emb: np.ndarray) -> float:
    """Mean adjacent-paragraph cosine. Higher = smoother local flow. Order-sensitive
    (the whole point: a shuffle should lower it)."""
    if len(emb) < 2:
        return 0.0
    return float(np.mean(np.sum(emb[:-1] * emb[1:], axis=1)))


def shuffle_test(emb: np.ndarray, rounds: int = 200, seed: int = 0) -> float:
    """Fraction of random permutations the original order beats on coherence."""
    rng = np.random.default_rng(seed)  # NFR5: seeded
    base = coherence(emb)
    perms = [coherence(emb[rng.permutation(len(emb))]) for _ in range(rounds)]
    return float(np.mean([base > p for p in perms]))


def insertion_test(emb: np.ndarray) -> tuple[float, float]:
    """Top-1 rate that the original slot maximises coherence, and chance (1/len)."""
    hits = trials = 0
    for i in range(1, len(emb) - 1):
        rest = np.delete(emb, i, axis=0)
        scores = [coherence(np.insert(rest, pos, emb[i], axis=0)) for pos in range(len(emb))]
        hits += int(np.argmax(scores) == i)
        trials += 1
    return (hits / trials if trials else 0.0), (1 / len(emb))


# ---- Named flow features (built only because the gates above passed) ----------

@dataclass
class FlowReport:
    speed: float                   # mean novelty: how fast ideas move through space
    volume: float                  # spread: how much conceptual ground is covered
    circuitousness: float          # path length / direct start->end (wandering vs linear)
    terminal_initial_ratio: float  # closing novelty vs opening (winding up vs down)
    circle_back: float             # cos(first, last) paragraph: Schimel OCAR bookend
    coherence: float               # mean adjacent cosine (the gated scalar)

    def to_dict(self) -> dict:      # FR6: machine-readable
        return asdict(self)


def novelty_curve(emb: np.ndarray) -> np.ndarray:
    """1 - cos(e_i, running centroid of e_<i): how new each paragraph is vs the past."""
    out = []
    for i in range(1, len(emb)):
        c = emb[:i].mean(0)
        c /= np.linalg.norm(c) + 1e-9
        out.append(1 - float(emb[i] @ c))
    return np.array(out)


def flow_report(text: str) -> FlowReport:
    # ponytail: doc-local geometry, no corpus-mean centering yet -- add when flow is
    # compared across docs, not just reported for one draft.
    emb = embed(paragraphs(text))
    nov = novelty_curve(emb)
    steps = np.linalg.norm(emb[1:] - emb[:-1], axis=1)
    direct = np.linalg.norm(emb[-1] - emb[0]) + 1e-9
    return FlowReport(
        speed=float(nov.mean()),
        volume=float(np.mean(np.linalg.norm(emb - emb.mean(0), axis=1))),
        circuitousness=float(steps.sum() / direct),
        terminal_initial_ratio=float(nov[-1] / (nov[0] + 1e-9)),
        circle_back=float(emb[0] @ emb[-1]),
        coherence=coherence(emb),
    )


if __name__ == "__main__":
    docs = read_corpus(sys.argv[1])
    embs = [embed(paragraphs(d)) for d in docs]
    embs = [e for e in embs if len(e) >= 4]  # need a few paragraphs to test order

    shuffles = [shuffle_test(e) for e in embs]
    ins = [insertion_test(e) for e in embs]
    ins_rate = float(np.mean([r for r, _ in ins]))
    chance = float(np.mean([c for _, c in ins]))
    shuf = float(np.mean(shuffles))

    print(f"docs tested: {len(embs)}  (paras: {[len(e) for e in embs]})")
    print(f"shuffle test : original beats {shuf:.0%} of permutations  "
          f"-> {'PASS' if shuf > 0.80 else 'DROP FLOW' if shuf < 0.60 else 'weak'}")
    print(f"insertion    : original slot rank-1 {ins_rate:.0%}  (chance {chance:.0%})  "
          f"-> {'PASS' if ins_rate > 2 * chance else 'weak'}")

    print("\nflow report (doc 0):")
    for k, v in flow_report(docs[0]).to_dict().items():
        print(f"  {k:24s} {v:+.3f}")
