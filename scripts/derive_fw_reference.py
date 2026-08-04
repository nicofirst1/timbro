"""Derive `FUNCTION_WORD_REFERENCE` (config.py, #59) from a public-domain corpus.

Downloads a fixed set of Project Gutenberg texts (fiction + non-fiction, no lexicon,
no NLTK -- stdlib `urllib` only), strips the Gutenberg header/footer boilerplate,
chunks each text into ~1000-word documents, and runs the shipped
`function_word_rates` extractor over every chunk. Chunking (rather than one mean per
whole book) is what gives `strength=2.0` a meaningful spread to blend against: a
single number per book would be 7 data points again, just longer ones.

Network only at derivation time; nothing here runs at package runtime. Re-run with
`uv run python scripts/derive_fw_reference.py`.
"""

from __future__ import annotations

import re
import statistics
import urllib.request

# (Gutenberg ID, title, category) -- 4 fiction + 3 non-fiction, chosen for public-domain
# status and to balance genre against the 7-doc sample being all short blog-style prose.
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

_WORD = re.compile(r"\b\w+\b")

CHUNK_WORDS = 1000


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


def derive_reference(chunks: list[str], rate_fn) -> tuple[tuple[float, ...], tuple[float, ...], int]:
    """Per-axis (mean, population-stdev) of `rate_fn(chunk)` across `chunks`, plus the
    chunk count. `rate_fn` is injected so this is testable without spaCy/network."""
    per_chunk = [rate_fn(c) for c in chunks]
    n_axes = len(per_chunk[0])
    means = tuple(statistics.mean(r[i] for r in per_chunk) for i in range(n_axes))
    spreads = tuple(statistics.pstdev(r[i] for r in per_chunk) for i in range(n_axes))
    return means, spreads, len(chunks)


def fetch_text(gutenberg_id: int) -> str:
    url = f"https://www.gutenberg.org/cache/epub/{gutenberg_id}/pg{gutenberg_id}.txt"
    with urllib.request.urlopen(url, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def main() -> None:
    from timbro.fw import function_word_rates

    all_chunks: list[str] = []
    for gid, title, category in GUTENBERG_TEXTS:
        raw = fetch_text(gid)
        body = strip_gutenberg_boilerplate(raw)
        chunks = chunk_words(body)
        all_chunks.extend(chunks)
        print(f"  gutenberg #{gid} {title!r} ({category}): {len(body.split())} words, {len(chunks)} chunks")

    total_words = sum(len(_WORD.findall(c)) for c in all_chunks)
    print(f"total: {len(all_chunks)} chunks, {total_words} words across {len(GUTENBERG_TEXTS)} texts")

    means, spreads, n = derive_reference(all_chunks, function_word_rates)
    axes = ("first_person_sg", "article_rate", "preposition_rate", "conjunction_rate", "pronoun_rate")
    for axis, m, s in zip(axes, means, spreads):
        print(f"  {axis}: mean={m:.2f}  pstdev={s:.2f}")

    print()
    print("FUNCTION_WORD_REFERENCE = Reference(")
    print(f"    mean=({', '.join(f'{m:.2f}' for m in means)}),")
    print(f"    spread=({', '.join(f'{s:.2f}' for s in spreads)}),")
    print("    strength=2.0,")
    print(")")


if __name__ == "__main__":
    main()
