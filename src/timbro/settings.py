"""User settings: `<TIMBRO_HOME>/settings.json`, with env-var overrides.

`TIMBRO_HOME` (default `~/.timbro`) is the root for settings and profiles. A
missing settings file is seeded with defaults on first read; a malformed or
invalid one raises `ValueError` naming the file, never a silent default.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path


@dataclass
class Settings:
    no_log: bool = False


def timbro_home() -> Path:
    env = os.environ.get("TIMBRO_HOME")
    return Path(env).expanduser() if env else Path.home() / ".timbro"


def settings_path() -> Path:
    return timbro_home() / "settings.json"


def load_settings() -> Settings:
    path = settings_path()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(Settings()), indent=2) + "\n", encoding="utf-8")
        return Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: malformed JSON ({exc})") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a JSON object")  # noqa: TRY004
    known = {f.name: f for f in fields(Settings)}
    for key, value in data.items():
        if key not in known:
            raise ValueError(f"{path}: unknown setting {key!r}")
        expected = type(getattr(Settings(), key))
        if not isinstance(value, expected):
            raise ValueError(f"{path}: {key!r} must be {expected.__name__}, got {value!r}")  # noqa: TRY004
    return Settings(**data)


def no_log() -> bool:
    """`TIMBRO_NO_LOG` (any non-empty value) wins, else the `no_log` setting."""
    if os.environ.get("TIMBRO_NO_LOG"):
        return True
    return load_settings().no_log
