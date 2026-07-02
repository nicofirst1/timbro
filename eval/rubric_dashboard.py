"""M3 (#8) calibration dashboard: findings per 1000 words, per rule, on known-good prose.

A rule that fires constantly on prose we already know is good ("known-good") is
noise -- a candidate for demotion to `low` severity (see #6), not deletion,
since timbro is recall-first by design. Every threshold change (#2) and every
new rule (#5, #7) should quote before/after numbers from this script in its PR.

Corpus: always includes the packaged sample exemplars
(src/timbro/sample/exemplars/). If TIMBRO_EXEMPLARS points elsewhere, that
corpus is scored too. Extra corpus directories can be passed as positional
args.

Usage:
    uv run python eval/rubric_dashboard.py            # table to stdout
    uv run python eval/rubric_dashboard.py --json      # machine-readable
    uv run python eval/rubric_dashboard.py data/exemplars   # + a local corpus
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path

from timbro.core import DEFAULT_EXEMPLARS, read_corpus
from timbro.rubrics.registry import get_rubric

# Candidate rubric names to try. Not every name is registered yet (e.g. `density`
# lands with #5); unregistered names are skipped with a note, so this script
# keeps working unmodified as new rubrics register.
CANDIDATE_RUBRICS = ["schimel", "density"]


def _word_count(text: str) -> int:
    return len(text.split())


def corpus_dirs(extra: list[str]) -> list[Path]:
    dirs = [DEFAULT_EXEMPLARS]
    env_exemplars = os.environ.get("TIMBRO_EXEMPLARS")
    if env_exemplars and Path(env_exemplars).resolve() != DEFAULT_EXEMPLARS.resolve():
        dirs.append(Path(env_exemplars))
    for e in extra:
        dirs.append(Path(e))
    # de-dupe, preserve order
    seen = set()
    unique = []
    for d in dirs:
        rd = d.resolve()
        if rd not in seen:
            seen.add(rd)
            unique.append(d)
    return unique


def score_rubric(rubric_name: str, texts: list[str]) -> dict | None:
    try:
        rubric = get_rubric(rubric_name)
    except KeyError:
        return None

    total_words = sum(_word_count(t) for t in texts)
    counts: Counter[str] = Counter()
    dimension: dict[str, str] = {}
    severities: defaultdict[str, Counter[str]] = defaultdict(Counter)

    for text in texts:
        result = rubric.check(text)
        for finding in result.findings:
            counts[finding.rule] += 1
            dimension[finding.rule] = finding.dimension
            severities[finding.rule][finding.severity] += 1

    rules = {}
    for rule, count in counts.items():
        per_1000 = (count * 1000 / total_words) if total_words else 0.0
        rules[rule] = {
            "dimension": dimension[rule],
            "severity": severities[rule].most_common(1)[0][0],
            "findings": count,
            "per_1000_words": round(per_1000, 2),
        }
    return {
        "rubric": rubric_name,
        "version": getattr(rubric, "version", "?"),
        "docs": len(texts),
        "total_words": total_words,
        "rules": rules,
    }


def render_text(report: dict) -> str:
    lines = [
        f"{report['rubric']} {report['version']}  "
        f"({report['docs']} docs, {report['total_words']} words)"
    ]
    if not report["rules"]:
        lines.append("  (no findings)")
        return "\n".join(lines)
    lines.append(f"  {'rule':<32s} {'dim':<12s} {'sev':<7s} {'n':>5s} {'per_1000w':>10s}")
    for rule, stats in sorted(
        report["rules"].items(), key=lambda kv: kv[1]["per_1000_words"], reverse=True
    ):
        lines.append(
            f"  {rule:<32s} {stats['dimension']:<12s} {stats['severity']:<7s} "
            f"{stats['findings']:>5d} {stats['per_1000_words']:>10.2f}"
        )
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "corpus", nargs="*", help="extra corpus directories (besides the packaged sample)"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    dirs = corpus_dirs(args.corpus)
    texts: list[str] = []
    for d in dirs:
        texts.extend(read_corpus(d))
    if not texts:
        print(f"no documents found in {[str(d) for d in dirs]}", file=sys.stderr)
        return 1

    reports = []
    skipped = []
    for name in CANDIDATE_RUBRICS:
        report = score_rubric(name, texts)
        if report is None:
            skipped.append(name)
        else:
            reports.append(report)

    if args.json:
        print(json.dumps({"corpus": [str(d) for d in dirs], "rubrics": reports}, indent=2))
    else:
        print(f"corpus: {', '.join(str(d) for d in dirs)}")
        print()
        for report in reports:
            print(render_text(report))
            print()
        if skipped:
            print(f"(skipped unregistered rubrics: {', '.join(skipped)})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
