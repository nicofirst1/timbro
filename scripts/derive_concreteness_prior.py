"""Derive CONCRETENESS_REFERENCE (config.py) from Brysbaert concreteness norms,
frequency-weighted by SUBTLEX-US (issue #58).

The vendored `src/timbro/norms/concreteness_brysbaert2014.csv.gz` keeps only
`lemma`/`concreteness` (SUBTLEX frequency was dropped as an unused column when it
was trimmed). This script re-fetches the original Brysbaert, Warriner & Kuperman
(2014) distribution -- same CC BY 4.0 file, mirrored at the GitHub repo cited in
`src/timbro/norms/NOTICE.md` -- which still carries the `SUBTLEX` column (raw
SUBTLEX-US occurrence count per lemma, the same corpus the Brysbaert team used
to select which words to rate). Joining on lemma against the vendored file
keeps the weighted set identical to what's shipped; this script does not
overwrite the vendored norms file.

Weighted mean:   sum(freq_i * conc_i) / sum(freq_i)
Weighted spread: sqrt(sum(freq_i * (conc_i - mean)^2) / sum(freq_i))  (weighted population stdev)

Not a runtime dependency: pandas/requests are dev-only, invoked manually.
Re-run: `uv run --with pandas --with requests python scripts/derive_concreteness_prior.py`
"""

from __future__ import annotations

import csv
import gzip
import math
from pathlib import Path

_ORIGINAL_URL = (
    "https://raw.githubusercontent.com/ArtsEngine/concreteness/master/"
    "Concreteness_ratings_Brysbaert_et_al_BRM.txt"
)
_VENDORED_NORMS = (
    Path(__file__).parent.parent / "src" / "timbro" / "norms" / "concreteness_brysbaert2014.csv.gz"
)


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
    """Frequency-weighted (mean, spread) restricted to the vendored lemma set."""
    kept = [(conc, freq) for lemma, conc, freq in rows if lemma in vendored_lemmas]
    concreteness = [c for c, _ in kept]
    frequency = [f for _, f in kept]
    return weighted_mean_spread(concreteness, frequency)


def main() -> None:
    import urllib.request

    with urllib.request.urlopen(_ORIGINAL_URL) as resp:
        text = resp.read().decode("utf-8")
    rows = parse_original_tsv(text)
    vendored_lemmas = load_vendored_lemmas()
    mean, spread = derive(rows, vendored_lemmas)
    print(f"rows joined: {sum(1 for lemma, *_ in rows if lemma in vendored_lemmas)} / {len(rows)}")
    print(f"mean={mean:.4f} spread={spread:.4f}")


if __name__ == "__main__":
    main()
