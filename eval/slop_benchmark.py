"""M4 (#15) sanity check: how often the `slop` tell detectors fire per paragraph.

Scores every paragraph in two small corpora with the `slop` rubric's raw findings:
  - eval/slop_bench/llm/       genuinely LLM-generated paragraphs (unprompted
    "AI assistant" register -- the target class)
  - src/timbro/sample/exemplars/   the packaged known-good human prose, reused
    from the M3 dashboard (#8) as the negative/false-positive class

A paragraph is "flagged" if at least one tell fires in it. This counts raw
findings, not the pass/warn/fail verdict: the verdict threshold (report.py) is
calibrated for whole documents, and single paragraphs rarely accumulate enough
findings to cross it -- that's a document-level design choice this benchmark
must not route around by inventing a second threshold.

CAVEAT (review, PR #51): the human side (src/timbro/sample/exemplars/) is the
exact corpus the slop rules were tuned against (see rules.py docstring and the
M3 dashboard, #8) -- so its false-positive rate here is circular, not
independent validation. This script is a reproducible smoke test for changes
to the rules, not a claim about false-positive behavior on unseen prose. Point
it at your own corpus (or extend it to accept one) before citing a number.

Reports:
  - hit rate: % of LLM paragraphs with >=1 finding
  - false-positive rate: % of human paragraphs with >=1 finding (not independent, see CAVEAT)

Usage:
    uv run python eval/slop_benchmark.py            # human-readable
    uv run python eval/slop_benchmark.py --json      # machine-readable
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from timbro.model import DEFAULT_EXEMPLARS, read_corpus
from timbro.rubrics import check_text
from timbro.text import split_paragraphs

LLM_DIR = Path(__file__).parent / "slop_bench" / "llm"


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
    human_paras = _paragraphs(DEFAULT_EXEMPLARS)
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
