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

    # local-first (#139): with the model cached, the online call still does a hub
    # HEAD request whose retry backoff stalls minutes with the network down. Try
    # the cache first; on failure (model not cached, first-run download) fall back
    # to the unchanged online call.
    try:
        return SentenceTransformer("StyleDistance/styledistance", local_files_only=True)
    except Exception:  # noqa: BLE001 -- cache miss must not block the online fallback
        return SentenceTransformer("StyleDistance/styledistance")  # content-invariant style


_STYLE_CACHE_MAX = 4096
_style_cache: dict[str, np.ndarray] = {}


def _chunks(text: str) -> list[str]:
    # the paragraph chunking every style vector shares: one style vector per doc =
    # mean of paragraph (chunk) style embeddings; a chunk-less text falls back to
    # its first 2000 chars.
    return [p.strip() for p in _PARA.split(text) if p.strip()] or [text[:2000]]


def _style_cache_put(text: str, vec: np.ndarray) -> None:
    # explicit dict instead of lru_cache (issue #153) so the batched path can warm
    # the same cache. Insertion-order eviction of the oldest entry stands in for
    # lru_cache's least-recently-used rule. The window is 8x the old lru maxsize:
    # one big draft now works through thousands of span texts in one pass, and a
    # 512-entry window would evict the paragraphs the per-span direction pass
    # re-requests right after the batch (measured on a 300 KB draft: ~450
    # re-encodes at 512, zero at 4096). Entries are float32 arrays (~3 KB each),
    # so the full window costs ~13 MB (tracemalloc, 4096 realistic entries);
    # tuples of boxed floats would cost ~103 MB. Same behavior for any repeated
    # text: hit.
    if text not in _style_cache and len(_style_cache) >= _STYLE_CACHE_MAX:
        _style_cache.pop(next(iter(_style_cache)))
    _style_cache[text] = vec


def _style_vec(text: str) -> tuple[float, ...]:
    # one style vector per doc. cached because the LOO harness re-scores the same
    # docs across folds. Entries are float32 arrays for memory; the tuple
    # contract is preserved on read.
    cached = _style_cache.get(text)
    if cached is not None:
        return tuple(cached)
    vec = _style_vecs([text])[0]
    _style_cache_put(text, vec)
    return tuple(vec)


def _style_vecs(texts: list[str]) -> np.ndarray:
    """(len(texts), dim) style vectors, one row per text, in input order.

    Batched twin of _style_vec (issue #153): the span path used to give every
    paragraph its own encode call; here all chunks of all texts go through one
    encode call and are averaged per text, with chunking identical to
    _style_vec. A single-text call is byte-identical to the old single encode;
    batched calls can differ from single-item encodes at the float level
    (padding), so span paragraph distances may drift at that scale. The batch
    warms _style_vec's cache, so later single-text lookups of the same texts hit
    it instead of re-encoding.
    """
    chunk_lists = [_chunks(t) for t in texts]
    all_chunks = [chunk for chunks in chunk_lists for chunk in chunks]
    embeddings = _style_model().encode(all_chunks, normalize_embeddings=True)
    rows = []
    at = 0
    for chunks in chunk_lists:
        rows.append(embeddings[at : at + len(chunks)].mean(0))
        at += len(chunks)
    for text, row in zip(texts, rows):
        _style_cache_put(text, row)
    return np.array(rows)


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
