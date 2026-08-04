"""Derive CONCRETENESS_REFERENCE (config.py) for issue #58.

Two derivations, mixed deliberately because they answer different questions:

MEAN: frequency-weighted over individual lemmas. The vendored
`src/timbro/norms/concreteness_brysbaert2014.csv.gz` keeps only `lemma`/`concreteness`
(SUBTLEX frequency was dropped as an unused column when it was trimmed). This script
re-fetches the original Brysbaert, Warriner & Kuperman (2014) distribution -- same
CC BY 4.0 file, mirrored at the GitHub repo cited in `src/timbro/norms/NOTICE.md` --
which still carries the `SUBTLEX` column (raw SUBTLEX-US occurrence count per lemma).
Joining on lemma against the vendored file keeps the weighted set identical to what's
shipped; this script does not overwrite the vendored norms file.
    weighted_mean = sum(freq_i * conc_i) / sum(freq_i)

SPREAD: population stdev of DOCUMENT-level mean concreteness, not lemma-level. The
axis this prior feeds (`concreteness.py:concreteness_stats`) scores one draft as a
single averaged number, and `model.py`'s z-score divides by this spread -- so the
spread must be measured in the same units the z-score consumes: how much a
~1000-word document's mean concreteness varies, not how much individual words'
ratings vary (~3.5x wider and the wrong unit -- see #58 verifier finding). Reuses
the same public-domain Gutenberg corpus and chunking approach as
`scripts/derive_fw_reference.py` (#59): 7 books, header/footer stripped, 1000-word
chunks, run through the shipped `concreteness_stats` extractor.
    spread = pstdev(chunk mean_concreteness for each chunk)

Not a runtime dependency: stdlib only (urllib, re, statistics, csv, gzip, math),
invoked manually. Re-run: `uv run python scripts/derive_concreteness_prior.py`
"""

from __future__ import annotations

import csv
import gzip
import math
import re
import statistics
import urllib.request
from pathlib import Path

_ORIGINAL_URL = (
    "https://raw.githubusercontent.com/ArtsEngine/concreteness/master/"
    "Concreteness_ratings_Brysbaert_et_al_BRM.txt"
)
_VENDORED_NORMS = (
    Path(__file__).parent.parent / "src" / "timbro" / "norms" / "concreteness_brysbaert2014.csv.gz"
)

# Same 7 public-domain texts as scripts/derive_fw_reference.py (#59) -- reusing the
# corpus keeps every doc-level-spread prior in this repo measured against one
# consistent general-English baseline instead of a different sample per axis.
GUTENBERG_TEXTS = [
    (1342, "Pride and Prejudice", "fiction"),
    (84, "Frankenstein", "fiction"),
    (2701, "Moby-Dick", "fiction"),
    (76, "Adventures of Huckleberry Finn", "fiction"),
    (5827, "The Problems of Philosophy", "non-fiction"),
    (205, "Walden", "non-fiction"),
    (408, "The Souls of Black Folk", "non-fiction"),
]

_START_RE = re.compile(r"\*\*\*\s*START OF (THE|THIS) PROJECT GUTENBERG EBOOK.*?\*\*\*", re.IGNORECASE | re.DOTALL)
_END_RE = re.compile(r"\*\*\*\s*END OF (THE|THIS) PROJECT GUTENBERG EBOOK", re.IGNORECASE)

CHUNK_WORDS = 1000


def weighted_mean_spread(values: list[float], weights: list[float]) -> tuple[float, float]:
    """Frequency-weighted mean and population stdev over `values`."""
    total_weight = sum(weights)
    mean = sum(v * w for v, w in zip(values, weights)) / total_weight
    variance = sum(w * (v - mean) ** 2 for v, w in zip(values, weights)) / total_weight
    return mean, math.sqrt(variance)


def load_vendored_lemmas(path: Path = _VENDORED_NORMS) -> set[str]:
    """Lemma set already shipped in the trimmed norms file -- restricts the
    frequency join to exactly the rows timbro's lookup table uses."""
    with gzip.open(path, "rt", newline="") as f:
        return {row["lemma"] for row in csv.DictReader(f)}


def parse_original_tsv(text: str) -> list[tuple[str, float, float]]:
    """(lemma, concreteness, subtlex_frequency) for single-word rows (Bigram == 0)."""
    rows = []
    reader = csv.DictReader(text.splitlines(), delimiter="\t")
    for row in reader:
        if row["Bigram"] != "0":
            continue
        rows.append((row["Word"], float(row["Conc.M"]), float(row["SUBTLEX"])))
    return rows


def derive(rows: list[tuple[str, float, float]], vendored_lemmas: set[str]) -> tuple[float, float]:
    """Frequency-weighted (mean, spread) over individual lemmas, restricted to the
    vendored lemma set. The spread this returns is the LEMMA-level spread -- kept for
    reference/testing but NOT what CONCRETENESS_REFERENCE.spread uses; see
    `derive_document_spread` for the document-level number the config actually needs.
    """
    kept = [(conc, freq) for lemma, conc, freq in rows if lemma in vendored_lemmas]
    concreteness = [c for c, _ in kept]
    frequency = [f for _, f in kept]
    return weighted_mean_spread(concreteness, frequency)


def strip_gutenberg_boilerplate(raw: str) -> str:
    """Cut the license header/footer Gutenberg wraps every text in, keeping only the
    work itself."""
    start = _START_RE.search(raw)
    body = raw[start.end() :] if start else raw
    end = _END_RE.search(body)
    return body[: end.start()] if end else body


def chunk_words(text: str, chunk_words: int = CHUNK_WORDS) -> list[str]:
    """Split `text` into whitespace-joined chunks of `chunk_words` word-tokens each,
    dropping a trailing partial chunk (keeps every chunk's denominator comparable)."""
    words = text.split()
    chunks = []
    for i in range(0, len(words) - chunk_words + 1, chunk_words):
        chunks.append(" ".join(words[i : i + chunk_words]))
    return chunks


def derive_document_spread(chunks: list[str], mean_concreteness_fn) -> float:
    """Population stdev of per-chunk mean concreteness -- the document-level unit the
    z-score in `model.py` actually divides by. `mean_concreteness_fn` is injected so
    this is testable without spaCy/network."""
    per_chunk_means = [mean_concreteness_fn(c) for c in chunks]
    return statistics.pstdev(per_chunk_means)


def fetch_text(gutenberg_id: int) -> str:
    url = f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main() -> None:
    from timbro.concreteness import concreteness_stats

    with urllib.request.urlopen(_ORIGINAL_URL) as resp:
        text = resp.read().decode("utf-8")
    rows = parse_original_tsv(text)
    vendored_lemmas = load_vendored_lemmas()
    mean, lemma_spread = derive(rows, vendored_lemmas)
    print(f"mean (lexicon, freq-weighted): rows joined {sum(1 for lemma, *_ in rows if lemma in vendored_lemmas)} / {len(rows)}")
    print(f"  mean={mean:.4f}  (lemma-level spread, NOT used: {lemma_spread:.4f})")

    all_chunks: list[str] = []
    for gid, title, category in GUTENBERG_TEXTS:
        raw = fetch_text(gid)
        body = strip_gutenberg_boilerplate(raw)
        chunks = chunk_words(body)
        all_chunks.extend(chunks)
        print(f"  gutenberg #{gid} {title!r} ({category}): {len(body.split())} words, {len(chunks)} chunks")

    spread = derive_document_spread(all_chunks, lambda c: concreteness_stats(c)[0])
    print(f"spread (document-level, {len(all_chunks)} chunks of {CHUNK_WORDS} words): pstdev={spread:.4f}")

    print()
    print("CONCRETENESS_REFERENCE = Reference(")
    print(f"    mean=({mean:.4f},),")
    print(f"    spread=({spread:.4f},),")
    print("    strength=2.0,")
    print(")")


if __name__ == "__main__":
    main()
