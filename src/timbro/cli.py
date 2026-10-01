"""One-shot CLI so a coding agent (or you) can score a draft without a running server.

    uv run timbro score draft.md
    cat draft.md | uv run timbro score -        # stdin
    uv run timbro score draft.md --json         # raw payload
    uv run timbro profiles list

Corpus comes from TIMBRO_EXEMPLARS / TIMBRO_CONTRAST (falls back to the packaged sample).
"""

import argparse
import json
import math
import sys
import traceback

from timbro.errors import UserError
from timbro.model import VoiceModel, default_model
from timbro.profiles import (
    add_file,
    diagnose_profile,
    get_profile,
    init_profile,
    learn,
    list_profiles,
    profile_root,
    sync_profiles,
)
from timbro.report import voice_report
from timbro.rewrite import evaluate_rewrite
from timbro.rubrics import check_text
from timbro.rubrics.registry import RUBRIC_NAMES
from timbro.rubrics.report import combine_verdicts, render_text
from timbro.settings import debug


def cmd_score(args):
    if args.file == "-":
        text = sys.stdin.read()
    else:
        text = _read_text(args.file)
    _require_draft_text(text, "draft")

    if args.profile:
        names = [name.strip() for name in args.profile.split(",") if name.strip()]
        rows = []
        for name in names:
            prof = get_profile(name)
            model = VoiceModel.from_dir(prof.exemplars_dir, contrast=prof.contrast_dir)
            rows.append({"profile_name": name, **voice_report(model, text)})
        if args.json:
            print(_dump_json(rows if len(rows) > 1 else rows[0], indent=2))
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
        print(_dump_json(payload, indent=2))
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
                sat = " (saturated)" if ax["saturated"] else ""
                print(f"  - {ax['direction']:26s} (z {ax['z']:+.2f}{sat}, {ax['axis'][7:]})")
        else:
            print("  - on-target: every structure axis within corpus spread")
    if not args.quiet and payload.get("hedge"):
        hoff = [ax for ax in payload["hedge"] if ax["direction"]]
        print("hedge/booster stance:")
        if hoff:
            for ax in sorted(hoff, key=lambda a: -abs(a["z"])):
                sat = " (saturated)" if ax["saturated"] else ""
                print(f"  - {ax['direction']:38s} (z {ax['z']:+.2f}{sat}, {ax['axis']})")
        else:
            print("  - on-target: within the reference spread")
    if not args.quiet and payload.get("fw"):
        foff = [ax for ax in payload["fw"] if ax["direction"]]
        print("function words vs reference:")
        if foff:
            for ax in sorted(foff, key=lambda a: -abs(a["z"])):
                sat = " (saturated)" if ax["saturated"] else ""
                print(f"  - {ax['direction']:38s} (z {ax['z']:+.2f}{sat}, {ax['axis']})")
        else:
            print("  - on-target: within the reference spread")
    if not args.quiet and payload.get("concreteness"):
        coff = [ax for ax in payload["concreteness"] if ax["direction"]]
        print("concreteness:")
        if coff:
            for ax in sorted(coff, key=lambda a: -abs(a["z"])):
                sat = " (saturated)" if ax["saturated"] else ""
                print(f"  - {ax['direction']:38s} (z {ax['z']:+.2f}{sat}, {ax['axis']})")
        else:
            print("  - on-target: within the reference spread")
    if not args.quiet and payload.get("richness"):
        roff = [ax for ax in payload["richness"] if ax["direction"]]
        print("readability/richness/entropy:")
        if roff:
            for ax in sorted(roff, key=lambda a: -abs(a["z"])):
                sat = " (saturated)" if ax["saturated"] else ""
                print(f"  - {ax['direction']:38s} (z {ax['z']:+.2f}{sat}, {ax['axis']})")
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


def cmd_check(args):
    names = []
    if args.rubric:
        names = [name.strip() for name in args.rubric.split(",") if name.strip()]
    if not names:
        names = list(RUBRIC_NAMES)
    unknown = [name for name in names if name not in RUBRIC_NAMES]
    if unknown:
        print(
            f"timbro: error: unknown rubric(s) {', '.join(unknown)}; available rubrics: {', '.join(RUBRIC_NAMES)}",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.file == "-":
        text = sys.stdin.read()
    else:
        text = _read_text(args.file)
    _require_draft_text(text, "draft")
    results = check_text(text, rubrics=names, profile=args.profile)
    verdict = combine_verdicts(results)

    # A verdict is a gate (issue #142): FAIL exits 3 so `check` can gate CI;
    # the printed payload and verdict line are unchanged. WARN and PASS exit 0.
    if args.json:
        payload = {
            "verdict": verdict,
            "rubrics": {result.rubric: result.to_dict() for result in results},
        }
        print(_dump_json(payload, indent=2))
        if verdict == "fail":
            sys.exit(3)
        return
    print(f"verdict: {verdict.upper()}")
    for result in results:
        print()
        print(render_text(result))
    if verdict == "fail":
        sys.exit(3)
    return


def cmd_accept(args):
    # A threshold outside [0, 1] can never be meaningful (#158): -1 always
    # passes and 2 always fails. Checked as the first statements, before any
    # file read or model load, as a direct print/exit like _require_draft_text
    # (an argparse type would exit 2 with argparse's own wording).
    if not 0.0 <= args.threshold <= 1.0:
        print("timbro: error: --threshold must be between 0 and 1", file=sys.stderr)
        sys.exit(1)
    original = _read_text(args.original)
    _require_draft_text(original, args.original)
    revised = _read_text(args.revised)
    _require_draft_text(revised, args.revised)
    if args.profile:
        prof = get_profile(args.profile)
        model = VoiceModel.from_dir(prof.exemplars_dir, contrast=prof.contrast_dir)
    else:
        model = default_model()
    result = evaluate_rewrite(model, original, revised, threshold=args.threshold)
    # A rejected rewrite is a verdict gate failure (issue #142): exit 3 after
    # the payload/verdict line, which stay unchanged. Accepted exits 0.
    if args.json:
        print(_dump_json(result, indent=2))
        if not result["accepted"]:
            sys.exit(3)
        return
    verdict = "accepted" if result["accepted"] else "rejected"
    print(
        f"{verdict}: distance {result['distance_before']:.1f} -> {result['distance_after']:.1f} "
        f"(improved={result['improved']}), content similarity {result['similarity']:.3f} "
        f"(content_ok={result['content_ok']})"
    )
    if not result["accepted"]:
        sys.exit(3)
    return


def cmd_profiles_list(args):
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
        print(_dump_json(payload, indent=2))
        return
    for prof in payload:
        summary = f" - {prof['summary']}" if prof["summary"] else ""
        print(f"{prof['name']}{summary}")
    return


def cmd_profiles_init(args):
    root = profile_root()
    configured = (root / ".git").exists()
    had_profiles = any(
        child.is_dir() and not child.name.startswith(".") for child in root.iterdir()
    ) if root.exists() else False
    prof = init_profile(args.name, about=args.about)
    if not configured and not had_profiles:
        print(
            "tip: using Timbro on another machine? run 'timbro profiles sync --init <url>' "
            "before creating profiles",
            file=sys.stderr,
        )
    print(prof.path)


def cmd_profiles_sync(args):
    try:
        result = sync_profiles(init_remote=args.init)
    except (RuntimeError, OSError, ValueError) as exc:
        _fail(f"sync failed: {exc}", code=2)
    if not args.json and "previous_remote" in result:
        print(
            f"warning: sync --init repointed origin from {result['previous_remote']} to {args.init}",
            file=sys.stderr,
        )
    if args.json:
        print(_dump_json(result))
    elif result["status"] == "ok":
        print("synced")
    elif result["status"] == "not-configured":
        print("profile sync not configured")
    elif result["status"] == "conflict":
        files = ", ".join(result.get("files", []))
        print(f'conflict in: {files}; see README "Resolving a sync conflict"', file=sys.stderr)
    else:
        # git stderr is often multi-line; the human output is one line.
        message = " ".join(result.get("message", "unknown error").split())
        print(f"sync failed: {message}", file=sys.stderr)
    if result["status"] == "conflict":
        sys.exit(1)
    if result["status"] == "error":
        sys.exit(2)


def cmd_profiles_add_file(args):
    dst = add_file(
        args.name,
        args.source,
        bucket=args.to,
        dest_name=args.dest_name,
        overwrite=args.overwrite,
    )
    print(dst)


def cmd_profiles_env(args):
    prof = get_profile(args.name)
    payload = prof.env
    if args.json:
        print(_dump_json(payload, indent=2))
        return
    print(f"TIMBRO_EXEMPLARS={payload['TIMBRO_EXEMPLARS']}")
    print(f"TIMBRO_CONTRAST={payload['TIMBRO_CONTRAST']}")
    return


def cmd_profiles_diagnose(args):
    payload = diagnose_profile(args.name)
    if args.json:
        print(_dump_json(payload, indent=2))
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


def cmd_profiles_learn(args):
    result = learn(
        args.name,
        args.draft,
        args.final,
        title=args.title,
        force=args.force,
    )

    if args.json:
        print(_dump_json(result))
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


def _dump_json(payload, indent=None) -> str:
    """Serialize a command payload, mapping non-finite floats to null.

    NaN or Infinity anywhere in a payload makes json.dumps emit literal
    NaN/Infinity tokens, which a strict parser rejects (issue #152). Every
    json.dumps call in this module goes through here: non-finite floats are
    recursively mapped to None, then the dump itself forbids them as a
    backstop. Each call site keeps its own indent choice.
    """

    def _clean(value):
        if isinstance(value, float):
            finite = math.isfinite(value)
            return value if finite else None
        if isinstance(value, dict):
            return {key: _clean(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [_clean(item) for item in value]
        return value

    safe = _clean(payload)
    return json.dumps(safe, indent=indent, allow_nan=False)


def _require_draft_text(text: str, name: str) -> None:
    """Exit 1 with one clean line when the draft text is empty.

    An empty draft is a user error, not a result (issue #152): score, check
    and accept call this right after reading the text and never reach the
    scoring layer. `name` is "draft" for score/check and the failing file's
    path for accept. Exits directly instead of via _fail, which must only be
    called from inside an `except` block (it prints the active traceback in
    debug mode), and there is no exception to show here.
    """
    stripped = text.strip()
    if stripped == "":
        print(f"timbro: error: {name} is empty", file=sys.stderr)
        sys.exit(1)


def _read_text(path: str) -> str:
    """Read a UTF-8 text file, attaching the path to any decode error.

    UnicodeDecodeError carries no filename of its own; attaching it here means
    the CLI's error handler can name the exact file that failed to decode and
    nothing else.
    """
    with open(path, encoding="utf-8") as f:
        try:
            return f.read()
        except UnicodeDecodeError as e:
            e.filename = path
            raise


def _fail(message: str, code: int = 1):
    """Print a one-line error and exit; call only from an `except` block.

    With debug on (`TIMBRO_DEBUG` or `"debug": true` in settings.json), the
    traceback of the exception being handled is printed first. A broken
    settings file must not mask the original error, so it counts as debug off.
    """
    try:
        show_trace = debug()
    except (ValueError, OSError):
        show_trace = False
    if show_trace:
        traceback.print_exc()
    print(message, file=sys.stderr)
    sys.exit(code)


def _user_error_message(exc: Exception) -> str:
    """One-line message for an expected user error, naming only sure files.

    OSError embeds its own filename in str() whenever it has one, and the
    manual raise sites put the path inside their message text. A
    UnicodeDecodeError carries no filename, so it may name a file only when a
    read site attached the failing path (see _read_text); otherwise the codec
    detail is printed without a path. Never guess the file from parsed args.
    """
    if isinstance(exc, UnicodeDecodeError):
        filename = getattr(exc, "filename", None)
        if filename:
            return f"{filename} is not UTF-8 text ({exc})"
    return str(exc)


def main():
    ap = argparse.ArgumentParser(prog="timbro", description="Score a draft against your voice.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("score", help="distance + named revision direction for a draft")
    s.add_argument("file", help="path to the draft, or - for stdin")
    s.add_argument("--json", action="store_true", help="raw JSON payload")
    s.add_argument("--profile", help="named profile, or comma-separated profiles to compare")
    s.add_argument("--quiet", action="store_true", help="suppress explanatory prose")
    s.set_defaults(func=cmd_score)

    c = sub.add_parser("check", help="run one or more deterministic writing rubrics (default: all)")
    c.add_argument("file", help="path to the draft, or - for stdin")
    c.add_argument("--rubric", help=f"comma-separated rubric names ({', '.join(RUBRIC_NAMES)}); default: all")
    c.add_argument("--profile", help="for the slop rubric: baseline tells against this profile's corpus")
    c.add_argument("--json", action="store_true", help="raw JSON payload")
    c.set_defaults(func=cmd_check)

    ac = sub.add_parser("accept", help="judge a candidate rewrite: closer to voice + meaning preserved?")
    ac.add_argument("original", help="path to the original draft")
    ac.add_argument("revised", help="path to the candidate rewrite")
    ac.add_argument("--profile", help="named profile to score against")
    ac.add_argument("--threshold", type=float, default=0.85, help="content-similarity gate (default 0.85)")
    ac.add_argument("--json", action="store_true", help="raw JSON payload")
    ac.set_defaults(func=cmd_accept)

    p = sub.add_parser("profiles", help="manage named exemplar/contrast profiles")
    psub = p.add_subparsers(dest="profiles_cmd", required=True)

    pl = psub.add_parser("list", help="list available profiles")
    pl.add_argument("--json", action="store_true", help="raw JSON payload")
    pl.set_defaults(func=cmd_profiles_list)

    pi = psub.add_parser("init", help="create a profile with README + folders")
    pi.add_argument("name")
    pi.add_argument("--about", default="", help="one-paragraph description for the profile README")
    pi.set_defaults(func=cmd_profiles_init)

    pa = psub.add_parser("add-file", help="copy a .md/.txt file into a profile bucket")
    pa.add_argument("name")
    pa.add_argument("source")
    pa.add_argument("--to", required=True, choices=["exemplars", "contrast"], help="bucket to add the file to")
    pa.add_argument("--dest-name", default=None, help="override destination filename")
    pa.add_argument("--overwrite", action="store_true", help="replace an existing destination file")
    pa.set_defaults(func=cmd_profiles_add_file)

    pe = psub.add_parser("env", help="print env vars for a profile")
    pe.add_argument("name")
    pe.add_argument("--json", action="store_true", help="raw JSON payload")
    pe.set_defaults(func=cmd_profiles_env)

    pd = psub.add_parser("diagnose", help="diagnose profile coherence and outliers")
    pd.add_argument("name")
    pd.add_argument("--json", action="store_true", help="raw JSON payload")
    pd.set_defaults(func=cmd_profiles_diagnose)

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
    pn.set_defaults(func=cmd_profiles_learn)

    ps = psub.add_parser("sync", help="sync the profile root with a git remote")
    ps.add_argument(
        "--init",
        metavar="remote-url",
        default=None,
        help="first-time setup on this machine: point the profile root at a (private) git repo and sync",
    )
    ps.add_argument("--json", action="store_true", help="raw JSON payload")
    ps.set_defaults(func=cmd_profiles_sync)

    args = ap.parse_args()
    try:
        args.func(args)
    except (OSError, UnicodeDecodeError, UserError) as e:
        # Expected user errors: one clean line, not a traceback. Issue #137
        # covered missing files, non-UTF-8 text, duplicate add-file and unknown
        # profiles; #154 widens the catch to OSError, so the other filesystem
        # refusals (PermissionError, ENAMETOOLONG, EROFS) are one line too.
        # #191 adds timbro.errors.UserError as the one class for every expected
        # error, so the per-command catches are gone and every user error (from
        # any command) prints the same `timbro: error: ` prefix through _fail.
        # Full traces come from the debug switch. Every other exception must
        # still traceback, because bugs should stay loud.
        _fail(f"timbro: error: {_user_error_message(e)}")


if __name__ == "__main__":
    main()
