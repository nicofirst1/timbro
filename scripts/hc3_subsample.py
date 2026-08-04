"""One-off conversion: HC3 (Hello-SimpleAI/HC3, CC-BY-SA-4.0) subsample -> per-file
.md corpus for eval/slop_benchmark.py (#60).

Pulls human_answers / chatgpt_answers from HC3's 5 English domain configs via the
HF datasets-server JSON API (no parquet/pandas/datasets runtime dependency -- this
script uses stdlib urllib only, and is not part of the package's runtime deps).

Writes DOCS_PER_DOMAIN human docs and DOCS_PER_DOMAIN LLM docs per domain, balanced
across domains, filtered to answers with >= MIN_WORDS words to drop degenerate/
one-line replies. Selection uses a fixed SEED so re-running reproduces the same
subsample from the same upstream data.

This is the held-out benchmark corpus: it must never overlap with
src/timbro/sample/exemplars/ (the rule-tuning sample), and that file is read-only.

Usage:
    uv run python scripts/hc3_subsample.py
"""

from __future__ import annotations

import json
import random
import urllib.request
from pathlib import Path

DOMAINS = ["finance", "medicine", "open_qa", "reddit_eli5", "wiki_csai"]
DOCS_PER_DOMAIN = 8
MIN_WORDS = 40
SEED = 60  # fixed for reproducibility; matches issue number, no other significance
PAGE_SIZE = 100
MAX_ROWS_PER_DOMAIN = 500  # enough rows to find DOCS_PER_DOMAIN eligible answers per side

OUT_ROOT = Path(__file__).parent.parent / "eval" / "slop_bench" / "hc3"

API = "https://datasets-server.huggingface.co/rows"


def _fetch_rows(domain: str) -> list[dict]:
    rows: list[dict] = []
    offset = 0
    while offset < MAX_ROWS_PER_DOMAIN:
        url = f"{API}?dataset=Hello-SimpleAI/HC3&config={domain}&split=train&offset={offset}&length={PAGE_SIZE}"
        with urllib.request.urlopen(url, timeout=30) as resp:
            payload = json.load(resp)
        page = [r["row"] for r in payload["rows"]]
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return rows


def _eligible_answers(rows: list[dict], key: str) -> list[str]:
    out = []
    for row in rows:
        for answer in row.get(key) or []:
            text = answer.strip()
            if len(text.split()) >= MIN_WORDS:
                out.append(text)
    return out


def _slugify(domain: str, idx: int) -> str:
    return f"{domain}-{idx:02d}"


def _write_docs(dir_path: Path, domain: str, docs: list[str]) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    for i, text in enumerate(docs):
        (dir_path / f"{_slugify(domain, i)}.md").write_text(text + "\n", encoding="utf-8")


def main() -> None:
    rng = random.Random(SEED)
    human_dir = OUT_ROOT / "human"
    llm_dir = OUT_ROOT / "llm"

    for old in (*human_dir.glob("*.md"), *llm_dir.glob("*.md")):
        old.unlink()

    for domain in DOMAINS:
        rows = _fetch_rows(domain)
        human_pool = _eligible_answers(rows, "human_answers")
        llm_pool = _eligible_answers(rows, "chatgpt_answers")
        if len(human_pool) < DOCS_PER_DOMAIN or len(llm_pool) < DOCS_PER_DOMAIN:
            raise RuntimeError(
                f"{domain}: only {len(human_pool)} human / {len(llm_pool)} llm eligible "
                f"answers, need {DOCS_PER_DOMAIN} each"
            )
        human_docs = rng.sample(human_pool, DOCS_PER_DOMAIN)
        llm_docs = rng.sample(llm_pool, DOCS_PER_DOMAIN)
        _write_docs(human_dir, domain, human_docs)
        _write_docs(llm_dir, domain, llm_docs)
        print(f"{domain}: wrote {len(human_docs)} human, {len(llm_docs)} llm docs")


if __name__ == "__main__":
    main()
