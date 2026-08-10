"""Shared en_core_web_sm loader.

PyPI rejects packages whose metadata carries a direct-URL dependency, so the
wheel pin (`en_core_web_sm @ https://...`) can only live in a dev/extra group
that never ships in the published sdist/wheel metadata (see pyproject.toml).
For a `pip install timbro` / `uvx timbro` cold-start, the model is instead
fetched on first use -- same model, same version, just deferred to runtime
with a printed progress message instead of failing.

Installs go through an explicit ``--python <interpreter>`` target rather than
spaCy's own ``spacy.cli.download()``: a bare ``uv pip install`` (spaCy's
fallback when ``pip`` isn't importable, which it isn't inside a ``uvx``
venv) resolves its target venv from ``VIRTUAL_ENV``/``PATH``, and a stray
``VIRTUAL_ENV`` left over from an unrelated activated venv in the invoking
shell outranks the running interpreter -- installing the model somewhere
`spacy.load` can't see it (issue #65).
"""

from __future__ import annotations

import shutil
import subprocess
import sys

_MODEL = "en_core_web_sm"


def _model_wheel_url() -> str:
    from spacy import about
    from spacy.cli.download import get_compatibility, get_model_filename, get_version

    compat = get_compatibility()
    version = get_version(_MODEL, compat)
    filename = get_model_filename(_MODEL, version)
    return f"{about.__download_url__.rstrip('/')}/{filename}"


def _install_model() -> None:
    wheel_url = _model_wheel_url()
    uv_path = shutil.which("uv")
    if uv_path:
        cmd = [uv_path, "pip", "install", "--python", sys.executable, wheel_url]
    else:
        cmd = [sys.executable, "-m", "pip", "install", wheel_url]
    subprocess.run(cmd, check=True)


def load_spacy(**kwargs) -> "spacy.language.Language":  # noqa: F821
    """spacy.load(_MODEL, **kwargs), downloading the model first if missing."""
    import spacy

    try:
        return spacy.load(_MODEL, **kwargs)
    except OSError:
        print(
            f"timbro: downloading spaCy model '{_MODEL}' (first run only)...",
            file=sys.stderr,
        )
        _install_model()
        return spacy.load(_MODEL, **kwargs)
