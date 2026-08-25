"""Best-effort per-profile telemetry: one JSONL line per `profiles.learn()` outcome.

Purpose: let a later analysis ask "across many accepted edits, did following the
advice on axis X actually shrink |z| from draft to final?" -- so every axis is
recorded, not just the ones that fired as `direction` moves. No raw text is
stored, only a content hash for correlation.

Logging must never break `learn()`: any failure here is swallowed and reported
as `None`, not raised.

Opt out with `TIMBRO_NO_LOG=1` in the environment (a user/test switch, read here,
not set anywhere in code).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from timbro.report import voice_report

if TYPE_CHECKING:
    from timbro.model import VoiceModel
    from timbro.profiles import Profile


def _sha12(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]


def _axis_z(entries: list[dict]) -> dict:
    return {e["axis"]: e["z"] for e in entries}


def _summary(model: VoiceModel, text: str) -> dict:
    report = voice_report(model, text)
    return {
        "sha": _sha12(text),
        "distance": report.get("distance"),
        "distance_z": report.get("distance_z"),
        "on_voice": report.get("on_voice"),
        "direction": [
            {"feature": m["feature"], "z": m["current_z"], "confidence": m["confidence"]}
            for m in report.get("direction", [])
        ],
        "markdown": _axis_z(report.get("markdown", [])),
        "hedge": _axis_z(report.get("hedge", [])),
        "fw": _axis_z(report.get("fw", [])),
        "concreteness": _axis_z(report.get("concreteness", [])),
        "flow": report.get("flow"),
    }


def log_learn(
    profile: Profile,
    model: VoiceModel | None,
    draft_text: str,
    final_text: str,
    *,
    title: str,
    outcome: str,
    guard: dict | None,
) -> Path | None:
    """Append one JSONL record of a learn() event to <profile_dir>/runs.jsonl.

    Best-effort: never raises into the caller. Returns the path written, or None
    if logging is disabled (TIMBRO_NO_LOG) or anything went wrong.
    """
    if os.environ.get("TIMBRO_NO_LOG"):
        return None
    try:
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "profile": profile.name,
            "title": title,
            "outcome": outcome,
            "guard": guard,
            "draft": _summary(model, draft_text) if model is not None else None,
            "final": _summary(model, final_text) if model is not None else None,
        }
        log_path = profile.path / "runs.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # ponytail: append with no file lock -- fine for a single-user local CLI;
        # upgrade only if concurrent writers to one profile become real.
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return log_path
    except Exception as exc:  # noqa: BLE001 -- best-effort: never break learn()
        print(f"timbro: run log skipped ({exc})", file=sys.stderr)
        return None
