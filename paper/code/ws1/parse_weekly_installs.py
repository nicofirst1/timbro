#!/usr/bin/env python3
r"""Re-parse the cached skills.sh HTML for the sparkline weekly-install series (§8 amd 2).

No re-crawl: reads the on-disk crawl cache written by build_skillssh.py
(paper/data/skillssh_cache/<sha>.body + <sha>.meta.json) and emits
skillssh_weekly.parquet keyed owner/repo/skill — a WS3-side join artifact like
skillssh_meta.parquet, NOT a CORPUS_COLUMNS field.

Frozen parse rule (LEDGER 2026-07-08 inspection): the sparkline aria-label
"Weekly installs: 87, 88, ..." is ALWAYS an 8-week series. Values >=1,000 carry a
thousands-separator comma (`1,901`), so the value separator is `,\s+` (comma +
whitespace), NOT bare comma; strip intra-value commas before int(). Verified to yield
exactly 8 values on 19,906/19,906 cached pages. installs_wk_mean = mean of the series
(all-zero -> 0.0).
"""
from __future__ import annotations

import glob
import json
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from _manifest import data_dir, write_manifest
from build_skillssh import cache_dir, parse_owner_repo_skill

_ARIA_RE = re.compile(r'aria-label="Weekly installs:\s*([^"]*)"', re.I)
_SEP_RE = re.compile(r",\s+")  # value separator; thousands sep `1,901` has no space

_SCHEMA = pa.schema([
    ("owner", pa.string()),
    ("repo", pa.string()),
    ("skill", pa.string()),
    ("weekly_installs", pa.list_(pa.int64())),
    ("installs_wk_mean", pa.float64()),
])


def parse_weekly_series(html: str) -> list[int] | None:
    """The 8-week install series from the sparkline aria-label, or None if absent."""
    m = _ARIA_RE.search(html)
    if not m:
        return None
    out = []
    for tok in _SEP_RE.split(m.group(1).strip()):
        s = tok.replace(",", "")  # drop thousands separators
        if not s:
            continue
        if not s.isdigit():
            return None  # unexpected format -> caller skips + counts
        out.append(int(s))
    return out or None


def series_mean(series: list[int]) -> float:
    return sum(series) / len(series) if series else 0.0


def build_row(html: str, url: str) -> dict | None:
    """{owner, repo, skill, weekly_installs, installs_wk_mean} or None if unparseable."""
    owr = parse_owner_repo_skill(url)
    if owr is None:
        return None
    series = parse_weekly_series(html)
    if series is None:
        return None
    owner, repo, skill = owr
    return {
        "owner": owner,
        "repo": repo,
        "skill": skill,
        "weekly_installs": series,
        "installs_wk_mean": series_mean(series),
    }


def main():
    cache = cache_dir()
    metas = sorted(glob.glob(str(cache / "*.meta.json")))
    print(f"[weekly] scanning {len(metas)} cached pages in {cache}")

    rows, n_no_aria, n_all_zero = [], 0, 0
    for meta_path in metas:
        meta = json.loads(Path(meta_path).read_text())
        if meta.get("status") != 200:
            continue
        body_path = Path(meta_path[: -len(".meta.json")] + ".body")
        if not body_path.exists():
            continue
        row = build_row(body_path.read_text(encoding="utf-8", errors="replace"), meta["url"])
        if row is None:
            n_no_aria += 1
            continue
        if not any(row["weekly_installs"]):
            n_all_zero += 1
        rows.append(row)

    rows.sort(key=lambda r: (r["owner"], r["repo"], r["skill"]))
    n_rows = len(rows)
    print(f"[weekly] {n_rows} rows  ({n_no_aria} no-aria/unparseable, {n_all_zero} all-zero)")

    out_path = data_dir() / "skillssh_weekly.parquet"
    pq.write_table(pa.Table.from_pylist(rows, schema=_SCHEMA), str(out_path))
    write_manifest(
        out_path,
        source="skillssh_weekly",
        inputs=[{"cache_dir": cache.name, "n_pages_scanned": len(metas)}],
        n_rows=n_rows,
        packages=["pyarrow"],
        extra={"n_no_aria": n_no_aria, "n_all_zero": n_all_zero, "window_weeks": 8},
    )
    print(f"[weekly] wrote {n_rows} rows to {out_path.name}")


if __name__ == "__main__":
    main()
