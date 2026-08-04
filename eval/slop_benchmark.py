"""M4 (#15) sanity check: how often the `slop` tell detectors fire per paragraph.

Scores every paragraph in an HC3 subsample (#60) with the `slop` rubric's raw
findings:
  - eval/slop_bench/hc3/llm/     chatgpt_answers from HC3 (Hello-SimpleAI/HC3,
    CC-BY-SA-4.0) -- the target class
  - eval/slop_bench/hc3/human/   human_answers from the same HC3 rows -- the
    negative/false-positive class

Both sides come from scripts/hc3_subsample.py and are independent of
src/timbro/sample/exemplars/ (the rule-tuning corpus), so the false-positive
rate here is a real held-out measurement, not circular validation.

A paragraph is "flagged" if at least one tell fires in it. This counts raw
findings, not the pass/warn/fail verdict: the verdict threshold (report.py) is
calibrated for whole documents, and single paragraphs rarely accumulate enough
findings to cross it -- that's a document-level design choice this benchmark
must not route around by inventing a second threshold.

Reports:
  - hit rate: % of LLM paragraphs with >=1 finding
  - false-positive rate: % of human paragraphs with >=1 finding

Usage:
    uv run python eval/slop_benchmark.py            # human-readable
    uv run python eval/slop_benchmark.py --json      # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from timbro.model import read_corpus
from timbro.rubrics import check_text
from timbro.text import split_paragraphs

HUMAN_DIR = Path(__file__).parent / "slop_bench" / "hc3" / "human"
LLM_DIR = Path(__file__).parent / "slop_bench" / "hc3" / "llm"


def _paragraphs(dir_path: Path) -> list[str]:
    out = []
    for doc in read_corpus(dir_path):
        out.extend(split_paragraphs(doc, min_words=15))
    return out


def flag_rate(paragraphs: list[str]) -> tuple[int, int]:
    flagged = sum(bool(check_text(p, rubric="slop").findings) for p in paragraphs)
    return flagged, len(paragraphs)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    llm_paras = _paragraphs(LLM_DIR)
    human_paras = _paragraphs(HUMAN_DIR)
    if not llm_paras or not human_paras:
        print(f"empty corpus: {len(llm_paras)} llm, {len(human_paras)} human", file=sys.stderr)
        return 1

    llm_flagged, llm_total = flag_rate(llm_paras)
    human_flagged, human_total = flag_rate(human_paras)
    hit_rate = llm_flagged / llm_total
    fp_rate = human_flagged / human_total

    if args.json:
        print(json.dumps({
            "hit_rate": round(hit_rate, 3),
            "false_positive_rate": round(fp_rate, 3),
            "llm_paragraphs": llm_total,
            "human_paragraphs": human_total,
        }, indent=2))
    else:
        print(
            f"flags {hit_rate:.0%} of LLM-generated paragraphs "
            f"at {fp_rate:.0%} false-positive rate on human-written prose"
        )
        print(f"  ({llm_flagged}/{llm_total} LLM paragraphs, {human_flagged}/{human_total} human paragraphs)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
