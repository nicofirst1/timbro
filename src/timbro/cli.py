"""One-shot CLI so a coding agent (or you) can score a draft without a running server.

    uv run timbro score draft.md
    cat draft.md | uv run timbro score -        # stdin
    uv run timbro score draft.md --json         # raw payload
    uv run timbro profiles list

Corpus comes from TIMBRO_EXEMPLARS / TIMBRO_CONTRAST (falls back to the packaged sample).
"""

import argparse
import json
import sys

from timbro.core import default_model
from timbro.profiles import add_file, get_profile, init_profile, list_profiles
from timbro.report import voice_report


def main():
    ap = argparse.ArgumentParser(prog="timbro", description="Score a draft against your voice.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score", help="distance + named revision direction for a draft")
    s.add_argument("file", help="path to the draft, or - for stdin")
    s.add_argument("--json", action="store_true", help="raw JSON payload")

    p = sub.add_parser("profiles", help="manage named exemplar/contrast profiles")
    psub = p.add_subparsers(dest="profiles_cmd", required=True)

    pl = psub.add_parser("list", help="list available profiles")
    pl.add_argument("--json", action="store_true", help="raw JSON payload")

    pi = psub.add_parser("init", help="create a profile with README + folders")
    pi.add_argument("name")
    pi.add_argument("--about", default="", help="one-paragraph description for the profile README")

    pa = psub.add_parser("add-file", help="copy a .md/.txt file into a profile bucket")
    pa.add_argument("name")
    pa.add_argument("source")
    pa.add_argument("--to", required=True, choices=["exemplars", "contrast"], help="bucket to add the file to")
    pa.add_argument("--dest-name", default=None, help="override destination filename")
    pa.add_argument("--overwrite", action="store_true", help="replace an existing destination file")

    pe = psub.add_parser("env", help="print env vars for a profile")
    pe.add_argument("name")
    pe.add_argument("--json", action="store_true", help="raw JSON payload")

    args = ap.parse_args()

    if args.cmd == "profiles":
        if args.profiles_cmd == "list":
            profiles = list_profiles()
            payload = [
                {
                    "name": prof.name,
                    "path": str(prof.path),
                    "summary": prof.summary(),
                    "exemplars": str(prof.exemplars_dir),
                    "contrast": str(prof.contrast_dir),
                }
                for prof in profiles
            ]
            if args.json:
                print(json.dumps(payload, indent=2))
                return
            for prof in payload:
                summary = f" - {prof['summary']}" if prof["summary"] else ""
                print(f"{prof['name']}{summary}")
            return

        if args.profiles_cmd == "init":
            prof = init_profile(args.name, about=args.about)
            print(prof.path)
            return

        if args.profiles_cmd == "add-file":
            dst = add_file(
                args.name,
                args.source,
                bucket=args.to,
                dest_name=args.dest_name,
                overwrite=args.overwrite,
            )
            print(dst)
            return

        if args.profiles_cmd == "env":
            prof = get_profile(args.name)
            payload = prof.env
            if args.json:
                print(json.dumps(payload, indent=2))
                return
            print(f"TIMBRO_EXEMPLARS={payload['TIMBRO_EXEMPLARS']}")
            print(f"TIMBRO_CONTRAST={payload['TIMBRO_CONTRAST']}")
            return

    text = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
    payload = voice_report(default_model(), text)

    if args.json:
        print(json.dumps(payload, indent=2))
        return
    print(f"distance from your voice: {payload['distance']:.1f}  (smaller = closer)")
    print("revise toward your voice:")
    for mv in payload["direction"]:
        print(f"  - {mv['hint']:24s} (confidence {mv['confidence']:.2f})")


if __name__ == "__main__":
    main()
