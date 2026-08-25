"""Generic scorer for benchmark-gating a check against dumb baselines.

A check either LOCATES one unit per document (thesis, core insight) or CLASSIFIES
each unit (filler / not). Either way it earns a Tier-A claim only if it beats the
laziest baselines (position, length, centrality, base-rate) on a real benchmark.
This module is the comparison; the datasets and signals live in the spike, not here.

See docs/adr/0005-benchmark-gated-check-development.md.

    uv run python eval/benchmarks/race.py   # runs the self-check
"""

from __future__ import annotations


def top_k(rankings: list[list[int]], gold: list[int], k: int) -> float:
    """Fraction of documents whose gold unit is in the method's top-k ranked units."""
    assert len(rankings) == len(gold)
    if not gold:
        return 0.0
    return sum(g in r[:k] for r, g in zip(rankings, gold)) / len(gold)


def mrr(rankings: list[list[int]], gold: list[int]) -> float:
    """Mean reciprocal rank of the gold unit across documents (0 if unranked)."""
    assert len(rankings) == len(gold)
    if not gold:
        return 0.0
    total = sum(1.0 / (r.index(g) + 1) if g in r else 0.0 for r, g in zip(rankings, gold))
    return total / len(gold)


def compare(methods: dict[str, list[list[int]]], gold: list[int], ks=(1, 3)) -> str:
    """Table of top-k + MRR per method. A candidate check must BEAT the baseline rows."""
    cols = [f"top-{k}" for k in ks] + ["mrr"]
    lines = ["method".ljust(14) + "".join(c.rjust(9) for c in cols)]
    for name, rankings in methods.items():
        vals = [top_k(rankings, gold, k) for k in ks] + [mrr(rankings, gold)]
        lines.append(name.ljust(14) + "".join(f"{v:9.3f}" for v in vals))
    return "\n".join(lines)


if __name__ == "__main__":
    # self-check: a perfect method ranks gold first everywhere; a bad one ranks it last.
    gold = [0, 1, 2]
    perfect = [[0, 8, 9], [1, 8, 9], [2, 8, 9]]
    worst = [[8, 9, 0], [8, 9, 1], [8, 9, 2]]  # gold at rank 3 -> reciprocal 1/3
    assert top_k(perfect, gold, 1) == 1.0
    assert mrr(perfect, gold) == 1.0
    assert top_k(worst, gold, 1) == 0.0
    assert top_k(worst, gold, 3) == 1.0
    assert abs(mrr(worst, gold) - 1 / 3) < 1e-9
    print(compare({"perfect": perfect, "worst": worst}, gold))
    print("ok")
