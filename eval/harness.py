"""Phase 1 gate: leave-one-out AUC, exemplars vs contrast.

For each exemplar, fit the region on the OTHER exemplars and score the held-out
one (positive) against all contrast docs (negative). The region is re-fit per
fold, so no exemplar leaks into the model that judges it. Target AUC > 0.80;
<= 0.65 falsifies the feature set.

Permutation baseline: shuffle the positive/negative labels and re-run -> tells
you what AUC chance produces at this n (critical, n~=15 makes AUC noisy).

Usage:
    uv run python eval/harness.py data/exemplars data/contrast
"""

import sys

from sklearn.metrics import roc_auc_score

from timbro import core
from timbro.core import VoiceModel, read_corpus


def loo_scores(exemplars: list[str], contrast: list[str]) -> tuple[list[float], list[int]]:
    dists, labels = [], []
    for i in range(len(exemplars)):
        held = exemplars[i]
        model = VoiceModel.fit(exemplars[:i] + exemplars[i + 1 :])
        dists.append(model.score(held).distance)
        labels.append(1)
        # contrast scored once per fold against that fold's region
        for c in contrast:
            dists.append(model.score(c).distance)
            labels.append(0)
    return dists, labels


def auc(exemplars: list[str], contrast: list[str]) -> float:
    dists, labels = loo_scores(exemplars, contrast)
    # closer (smaller distance) should mean positive -> negate for roc_auc_score
    return roc_auc_score(labels, [-d for d in dists])


def confound_guard(exemplars: list[str], contrast: list[str]) -> float:
    """LOO-AUC using only function-word rates (length-normalized). If voice
    separation only survives WITH length/readability features, the gate was won on
    a document-length artifact, not voice -- this cratering is the falsifier."""
    core.FEATURE_FILTER = lambda k: k.startswith("fw_")
    try:
        return auc(exemplars, contrast)
    finally:
        core.FEATURE_FILTER = None


def permutation_baseline(exemplars, contrast, rounds=200) -> float:
    """Mean AUC under shuffled labels -- the chance level at this n."""
    import numpy as np  # local: only the baseline needs it

    dists, labels = loo_scores(exemplars, contrast)
    scores = np.array([-d for d in dists])
    labels = np.array(labels)
    rng = np.random.default_rng(0)  # NFR5: seeded, deterministic
    return float(np.mean([roc_auc_score(rng.permutation(labels), scores) for _ in range(rounds)]))


def sign_test(exemplars: list[str], contrast: list[str], top_k: int = 6):
    """Phase 2 gate: for each contrast post, move its top-k recommended features to
    your corpus mean and check the distance drops -- vs moving k RANDOM features.
    The recommended direction should beat random. Returns (rec_rate, rand_rate)."""
    import numpy as np

    model = VoiceModel.fit(exemplars, contrast=contrast, top_k=top_k)
    rng = np.random.default_rng(0)  # NFR5: seeded
    rec_wins, rand_wins = 0, 0
    for c in contrast:
        vec = model.feature_vector(c)
        d0 = model._dist(vec)
        rec_idx = [model.names.index(m.feature) for m in model.score(c).direction]
        rand_idx = rng.choice(len(model.names), size=top_k, replace=False)
        for idx, bucket in ((rec_idx, "rec"), (rand_idx, "rand")):
            moved = vec.copy()
            moved[list(idx)] = model.mean[list(idx)]  # snap those features to your mean
            won = model._dist(moved) < d0
            if bucket == "rec":
                rec_wins += won
            else:
                rand_wins += won
    n = len(contrast)
    return rec_wins / n, rand_wins / n


if __name__ == "__main__":
    ex_dir, co_dir = sys.argv[1], sys.argv[2]
    ex, co = read_corpus(ex_dir), read_corpus(co_dir)
    assert ex and co, f"need posts in {ex_dir} and {co_dir}"
    a = auc(ex, co)
    base = permutation_baseline(ex, co)
    verdict = "PASS" if a > 0.80 else "FALSIFIED" if a <= 0.65 else "weak"
    print(f"LOO-AUC = {a:.3f}  (chance ~ {base:.3f})  -> {verdict}  "
          f"[{len(ex)} exemplars vs {len(co)} contrast]")

    g = confound_guard(ex, co)
    gverdict = "PASS (voice, not length)" if g > 0.80 else "CONFOUNDED (length artifact)"
    print(f"confound guard (function-words only) = {g:.3f}  -> {gverdict}")

    rec, rand = sign_test(ex, co)
    sverdict = "PASS" if rec > rand and rec >= 0.5 else "weak"
    print(f"sign test: recommended cuts distance {rec:.0%} of posts vs "
          f"{rand:.0%} random  -> {sverdict}")
