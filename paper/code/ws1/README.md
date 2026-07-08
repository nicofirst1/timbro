# WS1 — Corpus assembly

Builds `paper/data/corpus.parquet` (the RQ1–RQ3 cross-sectional corpus) plus a
version-chain table for RQ4, from the sources in `paper/README.md` §3–§4. Governed by
the `experiment-discipline` skill; pre-registration and per-source counts live in
[`LEDGER.md`](./LEDGER.md).

## Reproducibility contract (non-negotiable)

1. **Every number is produced by a committed script**, never hand-typed. `REPORT.md`
   (the acceptance artifact) is *generated* by `merge.py` from the manifests.
2. **Every builder writes a manifest** via `_manifest.write_manifest()` →
   `manifests/<output>.manifest.json` (committed). It records the git commit, the
   script name, `seed=42`, UTC time, upstream input ids/revisions/hashes, output row
   count, output SHA256, and resolved package versions.
3. **Seed is 42 everywhere** (`_manifest.SEED`) — MinHash permutations, any sampling.
4. **Data is never committed.** Outputs land in `paper/data/` (gitignored via `data/`).
   Only scripts, manifests, `LEDGER.md`, and `REPORT.md` are tracked.
5. **Upstream counts are asserted, not assumed** (`_schema.*_EXPECTED`). A mismatch is a
   D7 spec/reality conflict → stop, log in `LEDGER.md`, ask the user. Do not substitute.
6. **Redistribute derived features, never raw skill text** (paper/README.md §3).

## Layout

```
paper/code/ws1/
├── _manifest.py        # git commit, hashing, manifest writer, paths, SEED
├── _schema.py          # CORPUS_COLUMNS + frozen upstream counts
├── requirements.txt    # corpus-side deps (pyarrow, huggingface_hub, datasketch, requests)
├── build_skill_diffs.py# anchor: shl0ms/skill-diffs → cross-sectional + version-chain tables
├── build_gos.py        # davidliuk/graph-of-skills-data (skills_2000.tar.gz)
├── build_clawhub.py    # clawhub.ai sanctioned feed (~549) + per-skill file fetch
├── build_slop.py       # amoghacloud/clawskills-intelligence-corpus (labeled low-quality)
├── build_skillssh.py   # skills.sh installs join — CODE ONLY, gated (see LEDGER.md), do not run
├── dedup.py            # exact SHA256 + MinHash 0.9 Jaccard (datasketch); D1 rule
├── merge.py            # → corpus.parquet + generates REPORT.md
├── manifests/          # committed provenance JSON, one per output
└── REPORT.md           # generated acceptance summary (counts, dedup, license, platform)
```

## Run

```bash
R="uv run --with-requirements paper/code/ws1/requirements.txt python paper/code/ws1"
$R/build_skill_diffs.py     # ~8GB parquet download; probes repos.parquet + asserts counts first
$R/build_gos.py
$R/build_clawhub.py
$R/build_slop.py
$R/dedup.py
$R/merge.py                 # writes corpus.parquet + REPORT.md
# build_skillssh.py is GATED — read skills.sh/terms + get user sign-off before running (LEDGER.md).
```
