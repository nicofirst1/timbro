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

from timbro.core import VoiceModel, default_model
from timbro.profiles import add_file, diagnose_profile, get_profile, init_profile, list_profiles
from timbro.report import voice_report
from timbro.rubrics import check_text
from timbro.rubrics.report import render_text


def main():
    ap = argparse.ArgumentParser(prog="timbro", description="Score a draft against your voice.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score", help="distance + named revision direction for a draft")
    s.add_argument("file", help="path to the draft, or - for stdin")
    s.add_argument("--json", action="store_true", help="raw JSON payload")
    s.add_argument("--profile", help="named profile, or comma-separated profiles to compare")
    s.add_argument("--quiet", action="store_true", help="suppress explanatory prose")

    c = sub.add_parser("check", help="run a deterministic writing rubric")
    c.add_argument("file", help="path to the draft, or - for stdin")
    c.add_argument("--rubric", default="schimel", help="rubric name")
    c.add_argument("--json", action="store_true", help="raw JSON payload")

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

    pd = psub.add_parser("diagnose", help="diagnose profile coherence and outliers")
    pd.add_argument("name")
    pd.add_argument("--json", action="store_true", help="raw JSON payload")

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

        if args.profiles_cmd == "diagnose":
            payload = diagnose_profile(args.name)
            if args.json:
                print(json.dumps(payload, indent=2))
                return
            print(f"profile: {payload['name']}")
            print(f"exemplars: {payload['exemplars']}")
            if payload['coherence'] is not None:
                print(f"coherence: {payload['coherence']:.2f}")
            if payload['silhouette'] is not None:
                print(f"two-cluster silhouette: {payload['silhouette']:.2f}")
            if payload['warning']:
                print(f"warning: {payload['warning']}")
            for row in payload['files']:
                print(f"- {row['file']}: {row['words']} words, {row['paragraphs']} paragraphs, nn-dist {row['nearest_neighbor_distance']:.2f}")
            return

    if args.cmd == "check":
        text = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
        result = check_text(text, rubric=args.rubric)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
            return
        print(render_text(result))
        return

    text = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()

    if args.profile:
        names = [name.strip() for name in args.profile.split(",") if name.strip()]
        rows = []
        for name in names:
            prof = get_profile(name)
            model = VoiceModel.from_dir(prof.exemplars_dir, contrast=prof.contrast_dir)
            rows.append({"profile_name": name, **voice_report(model, text)})
        if args.json:
            print(json.dumps(rows if len(rows) > 1 else rows[0], indent=2))
            return
        if len(rows) > 1:
            print("profile               distance   z      health        on_voice")
            for row in rows:
                dz = f"{row['distance_z']:6.2f}" if row["distance_z"] is not None else "   n/a"
                on_voice = str(row["on_voice"]).lower() if row["on_voice"] is not None else "-"
                print(
                    f"{row['profile_name'][:20]:20s} {row['distance']:8.1f} {dz}  "
                    f"{row['profile']['health'][:12]:12s} {on_voice}"
                )
            return
        payload = rows[0]
    else:
        payload = voice_report(default_model(), text)

    if args.json:
        print(json.dumps(payload, indent=2))
        return
    if args.quiet:
        dz = f"{payload['distance_z']:.2f}" if payload["distance_z"] is not None else "n/a"
        print(f"distance={payload['distance']:.1f} z={dz} health={payload['profile']['health']}")
        return
    else:
        z_text = f"z {payload['distance_z']:+.2f}" if payload["distance_z"] is not None else "z n/a"
        profile_line = (
            f"profile: {payload['profile']['health']}  "
            f"floor {payload['profile']['exemplar_floor']:.1f}  "
            f"spread {payload['profile']['exemplar_spread']:.1f}"
        )
        if payload["profile"]["contrast_ceiling"] is not None:
            profile_line += f"  ceiling {payload['profile']['contrast_ceiling']:.1f}"
        print(f"distance from your voice: {payload['distance']:.1f}  ({z_text})")
        print(profile_line)
        if payload['profile']['warning']:
            print(f"warning: {payload['profile']['warning']}")
        if payload['on_voice']:
            print("already on-voice: within the exemplar spread")
        print("revise toward your voice:")
    for mv in payload["direction"]:
        print(f"  - {mv['hint']:24s} (confidence {mv['confidence']:.2f})")
    if not args.quiet and payload.get("spans"):
        print("highest-leverage paragraphs:")
        for span in payload["spans"]:
            dz = f"{span['distance_z']:+.2f}" if span["distance_z"] is not None else "n/a"
            print(f"  - ¶{span['index']}: z {dz}  {span['text']}")
            for move in span.get("direction", []):
                print(f"      · {move['hint']} ({move['confidence']:.2f})")
            if span.get("sentence"):
                sentence = span["sentence"]
                print(f"      · top sentence: {sentence['text'][:180]}")
                for move in sentence.get("direction", []):
                    print(f"          - {move['hint']} ({move['confidence']:.2f})")


if __name__ == "__main__":
    main()
