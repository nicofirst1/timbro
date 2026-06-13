"""One-shot CLI so a coding agent (or you) can score a draft without a running server.

    uv run timbro score draft.md
    cat draft.md | uv run timbro score -        # stdin
    uv run timbro score draft.md --json         # raw payload

Corpus comes from TIMBRO_EXEMPLARS / TIMBRO_CONTRAST (default data/exemplars, data/contrast).
"""

import argparse
import json
import os
import sys

from timbro import VoiceModel
from timbro.report import voice_report


def _model() -> VoiceModel:
    return VoiceModel.from_dir(
        os.environ.get("TIMBRO_EXEMPLARS", "data/exemplars"),
        contrast=os.environ.get("TIMBRO_CONTRAST", "data/contrast"),
    )


def main():
    ap = argparse.ArgumentParser(prog="timbro", description="Score a draft against your voice.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score", help="distance + named revision direction for a draft")
    s.add_argument("file", help="path to the draft, or - for stdin")
    s.add_argument("--json", action="store_true", help="raw JSON payload")
    args = ap.parse_args()

    text = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
    payload = voice_report(_model(), text)

    if args.json:
        print(json.dumps(payload, indent=2))
        return
    print(f"distance from your voice: {payload['distance']:.1f}  (smaller = closer)")
    print("revise toward your voice:")
    for mv in payload["direction"]:
        print(f"  - {mv['hint']:24s} (confidence {mv['confidence']:.2f})")


if __name__ == "__main__":
    main()
