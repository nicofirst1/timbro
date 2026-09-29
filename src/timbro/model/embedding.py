"""The "how far" lens: StyleDistance embedding kNN (one of the two lenses; the
orchestrator lives in `timbro.model`), plus `fit_embedding`, which holds the
embedding-fit portion of `VoiceModel.fit`."""

from __future__ import annotations

import os
from functools import lru_cache

import numpy as np

from timbro.metric import _knn
from timbro.text import _PARA


@lru_cache(maxsize=1)
def _style_model():
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    try:
        from transformers.utils import logging as tlog

        tlog.set_verbosity_error()
    except Exception:  # noqa: BLE001, S110 -- best-effort optional-lib logging setup, must not block model load
        pass
    try:
        from huggingface_hub.utils import disable_progress_bars
        from huggingface_hub.utils import logging as hlog

        disable_progress_bars()
        hlog.set_verbosity_error()
    except Exception:  # noqa: BLE001, S110 -- best-effort optional-lib logging setup, must not block model load
        pass
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer("StyleDistance/styledistance")  # content-invariant style


@lru_cache(maxsize=512)
def _style_vec(text: str) -> tuple[float, ...]:
    # one style vector per doc = mean of paragraph (chunk) style embeddings. cached
    # because the LOO harness re-scores the same docs across folds.
    chunks = [p.strip() for p in _PARA.split(text) if p.strip()] or [text[:2000]]
    return tuple(_style_model().encode(chunks, normalize_embeddings=True).mean(0))


def _loo_exemplar_distances(train_ez: np.ndarray, knn_k: int) -> np.ndarray:
    if len(train_ez) < 2:
        return np.zeros(1)
    dists = []
    k = max(1, min(knn_k, len(train_ez) - 1))
    for i in range(len(train_ez)):
        rest = np.delete(train_ez, i, axis=0)
        dists.append(_knn(rest, train_ez[i], k))
    return np.array(dists, dtype=float)


def fit_embedding(texts: list[str], contrast: list[str] | None, knn_k: int):
    """-> (emean, estd, train_ez, exemplar_floor, exemplar_spread, contrast_ceiling)"""
    # embedding path (scalar)
    E = np.array([_style_vec(t) for t in texts])
    emean, estd = E.mean(0), E.std(0)
    # Floor 1e-6, picked from data: E is float32, so byte-identical exemplars leave
    # mean-rounding stds up to 7.45e-9 (degen3b sandbox corpus), while the smallest
    # real per-dim std measures 1.38e-4 (packaged sample voice). Gap ~18500x: the
    # floor sits 134x above the noise and 138x below the real spread.
    estd[estd < 1e-6] = 1.0
    train_ez = (E - emean) / estd
    exemplar_dists = _loo_exemplar_distances(train_ez, knn_k)
    exemplar_floor = float(np.median(exemplar_dists))
    exemplar_spread = float(np.std(exemplar_dists) or 1.0)
    contrast_ceiling = None
    if contrast:
        C = np.array([_style_vec(t) for t in contrast])
        if len(C):
            contrast_ez = (C - emean) / estd
            contrast_ceiling = float(np.mean([_knn(train_ez, z, knn_k) for z in contrast_ez]))
    return emean, estd, train_ez, exemplar_floor, exemplar_spread, contrast_ceiling
