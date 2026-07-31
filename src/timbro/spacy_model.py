"""Shared en_core_web_sm loader.

PyPI rejects packages whose metadata carries a direct-URL dependency, so the
wheel pin (`en_core_web_sm @ https://...`) can only live in a dev/extra group
that never ships in the published sdist/wheel metadata (see pyproject.toml).
For a `pip install timbro` / `uvx timbro` cold-start, the model is instead
fetched on first use via spaCy's own downloader -- same model, same version,
just deferred to runtime with a printed progress message instead of failing.
"""

from __future__ import annotations

import sys

_MODEL = "en_core_web_sm"


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
        spacy.cli.download(_MODEL)
        return spacy.load(_MODEL, **kwargs)
