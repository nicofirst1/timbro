#!/usr/bin/env python3
"""WS3 step 1: run `timbro analyze` over corpus.parquet canonical docs -> features.parquet.

The pure seam is `featurize_rows`: canonical corpus rows in, feature rows out, keyed by
skill_id and carrying every metadata column forward (platform/era for the WS3 confound
gates, installs/stars/age for RQ2). `analyze` is injectable so tests stay fast and never
import spaCy. main() is the thin parquet I/O wrapper around it.
"""
from __future__ import annotations

import sys
from pathlib import Path

# text becomes the feature vector; is_canonical/near_dup_cluster_id are dedup bookkeeping.
_DROP = {"text", "is_canonical", "near_dup_cluster_id"}


def featurize_rows(rows, analyze=None):
    """Canonical corpus rows -> feature rows. analyze(text)->dict defaults to timbro's."""
    if analyze is None:
        from timbro.analyze import analyze_text  # lazy: keeps the pure test spaCy-free
        analyze = analyze_text

    out = []
    for row in rows:
        if not row.get("is_canonical", True):
            continue
        meta = {k: v for k, v in row.items() if k not in _DROP}
        # analyze()'s frontmatter_json is authoritative on collision, so features win.
        out.append({**meta, **analyze(row["text"])})
    return out


def main(corpus="paper/data/corpus.parquet", out="paper/data/features.parquet"):
    import pyarrow as pa
    import pyarrow.parquet as pq  # ponytail: local import so the pure seam has no pyarrow dep

    rows = pq.read_table(corpus).to_pylist()
    features = featurize_rows(rows)
    print(f"featurized {len(features)}/{len(rows)} rows (canonical only)", file=sys.stderr)
    pq.write_table(pa.Table.from_pylist(features), out)
    # ponytail: manifest write deferred to the real run — reuse ws1/_manifest.write_manifest then.
    return 0


if __name__ == "__main__":
    raise SystemExit(main(*sys.argv[1:]))
