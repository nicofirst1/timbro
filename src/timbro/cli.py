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

from timbro.model import VoiceModel, default_model
from timbro.profiles import (
    add_file,
    diagnose_profile,
    get_profile,
    init_profile,
    learn,
    list_profiles,
)
from timbro.report import voice_report
from timbro.rewrite import evaluate_rewrite
from timbro.rubrics import check_text
from timbro.rubrics.registry import RUBRIC_NAMES
from timbro.rubrics.report import combine_verdicts, render_text


def main():
    ap = argparse.ArgumentParser(prog="timbro", description="Score a draft against your voice.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score", help="distance + named revision direction for a draft")
    s.add_argument("file", help="path to the draft, or - for stdin")
    s.add_argument("--json", action="store_true", help="raw JSON payload")
    s.add_argument("--profile", help="named profile, or comma-separated profiles to compare")
    s.add_argument("--quiet", action="store_true", help="suppress explanatory prose")

    c = sub.add_parser("check", help="run one or more deterministic writing rubrics (default: all)")
    c.add_argument("file", help="path to the draft, or - for stdin")
    c.add_argument("--rubric", help=f"comma-separated rubric names ({', '.join(RUBRIC_NAMES)}); default: all")
    c.add_argument("--profile", help="for the slop rubric: baseline tells against this profile's corpus")
    c.add_argument("--json", action="store_true", help="raw JSON payload")

    ac = sub.add_parser("accept", help="judge a candidate rewrite: closer to voice + meaning preserved?")
    ac.add_argument("original", help="path to the original draft")
    ac.add_argument("revised", help="path to the candidate rewrite")
    ac.add_argument("--profile", help="named profile to score against")
    ac.add_argument("--threshold", type=float, default=0.85, help="content-similarity gate (default 0.85)")
    ac.add_argument("--json", action="store_true", help="raw JSON payload")

    an = sub.add_parser("analyze", help="emit deterministic linguistic feature vectors")
    an.add_argument("paths", nargs="+", help="one or more .md/.txt files")
    an.add_argument("--format", choices=["jsonl", "csv"], default="jsonl")
    an.add_argument("--out", help="write to this file instead of stdout")

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

    pn = psub.add_parser(
        "learn",
        help="save a (draft, final) editing pair into a profile — final→exemplars, draft→contrast, guarded",
    )
    pn.add_argument("name")
    pn.add_argument("--draft", required=True, help="path to the raw/first-pass draft (goes to contrast)")
    pn.add_argument("--final", required=True, help="path to the polished final (goes to exemplars)")
    pn.add_argument("--title", default=None, help="optional shared slug for both saved files (default: final's stem)")
    pn.add_argument("--force", action="store_true", help="skip the guard / overwrite existing / bootstrap an empty profile")
    pn.add_argument("--json", action="store_true", help="raw JSON payload")

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

        if args.profiles_cmd == "learn":
            try:
                result = learn(
                    args.name,
                    args.draft,
                    args.final,
                    title=args.title,
                    force=args.force,
                )
            except (FileExistsError, FileNotFoundError, ValueError) as exc:
                print(f"error: {exc}", file=sys.stderr)
                sys.exit(1)

            if args.json:
                print(json.dumps(result))
                return

            if not result["saved"]:
                print(result["reason"], file=sys.stderr)
                sys.exit(1)

            print(f"learned pair into '{args.name}': exemplar {result['exemplar']}, contrast {result['contrast']}")
            if result["distance_before"] is not None:
                print(
                    f"distance draft={result['distance_before']:.1f} -> final={result['distance_after']:.1f} "
                    f"(similarity {result['similarity']:.2f})"
                )
            return

    if args.cmd == "check":
        names = []
        if args.rubric:
            names = [name.strip() for name in args.rubric.split(",") if name.strip()]
        if not names:
            names = list(RUBRIC_NAMES)
        unknown = [name for name in names if name not in RUBRIC_NAMES]
        if unknown:
            print(
                f"error: unknown rubric(s) {', '.join(unknown)}; available rubrics: {', '.join(RUBRIC_NAMES)}",
                file=sys.stderr,
            )
            sys.exit(1)

        if args.file == "-":
            text = sys.stdin.read()
        else:
            with open(args.file, encoding="utf-8") as f:
                text = f.read()
        try:
            results = check_text(text, rubrics=names, profile=args.profile)
        except ValueError as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(1)

        if args.json:
            payload = {
                "verdict": combine_verdicts(results),
                "rubrics": {result.rubric: result.to_dict() for result in results},
            }
            print(json.dumps(payload, indent=2))
            return
        print(f"verdict: {combine_verdicts(results).upper()}")
        for result in results:
            print()
            print(render_text(result))
        return

    if args.cmd == "accept":
        with open(args.original, encoding="utf-8") as f:
            original = f.read()
        with open(args.revised, encoding="utf-8") as f:
            revised = f.read()
        if args.profile:
            prof = get_profile(args.profile)
            model = VoiceModel.from_dir(prof.exemplars_dir, contrast=prof.contrast_dir)
        else:
            model = default_model()
        result = evaluate_rewrite(model, original, revised, threshold=args.threshold)
        if args.json:
            print(json.dumps(result, indent=2))
            return
        verdict = "accepted" if result["accepted"] else "rejected"
        print(
            f"{verdict}: distance {result['distance_before']:.1f} -> {result['distance_after']:.1f} "
            f"(improved={result['improved']}), content similarity {result['similarity']:.2f} "
            f"(content_ok={result['content_ok']})"
        )
        return

    if args.cmd == "analyze":
        from timbro.analyze import run_analyze

        sys.exit(run_analyze(args.paths, fmt=args.format, out_path=args.out))

    if args.file == "-":
        text = sys.stdin.read()
    else:
        with open(args.file, encoding="utf-8") as f:
            text = f.read()

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
    if not args.quiet and payload.get("markdown"):
        off = [ax for ax in payload["markdown"] if ax["direction"]]
        print("markdown vs corpus:")
        if off:
            for ax in sorted(off, key=lambda a: -abs(a["z"])):
                print(f"  - {ax['direction']:26s} (z {ax['z']:+.2f}, {ax['axis'][7:]})")
        else:
            print("  - on-target: every structure axis within corpus spread")
    if not args.quiet and payload.get("hedge"):
        hoff = [ax for ax in payload["hedge"] if ax["direction"]]
        print("hedge/booster stance:")
        if hoff:
            for ax in sorted(hoff, key=lambda a: -abs(a["z"])):
                print(f"  - {ax['direction']:38s} (z {ax['z']:+.2f}, {ax['axis']})")
        else:
            print("  - on-target: within the reference spread")
    if not args.quiet and payload.get("fw"):
        foff = [ax for ax in payload["fw"] if ax["direction"]]
        print("function words vs reference:")
        if foff:
            for ax in sorted(foff, key=lambda a: -abs(a["z"])):
                print(f"  - {ax['direction']:38s} (z {ax['z']:+.2f}, {ax['axis']})")
        else:
            print("  - on-target: within the reference spread")
    if not args.quiet and payload.get("concreteness"):
        coff = [ax for ax in payload["concreteness"] if ax["direction"]]
        print("concreteness:")
        if coff:
            for ax in sorted(coff, key=lambda a: -abs(a["z"])):
                print(f"  - {ax['direction']:38s} (z {ax['z']:+.2f}, {ax['axis']})")
        else:
            print("  - on-target: within the reference spread")
    if not args.quiet and payload.get("politeness"):
        pol = payload["politeness"]
        print(f"politeness strategies (reporting only, {pol['total']} fired):")
        for name, n in sorted(pol["strategies"].items(), key=lambda kv: -kv[1]):
            print(f"  - {name}: {n}")
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
