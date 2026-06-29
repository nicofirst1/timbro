"""Utilities for converting LaTeX sources into Timbro-ready plain text."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from timbro.cleanup.papers import clean_extracted_text, cleanup_paper_markdown


def _normalize_detex_output(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(?i)\.abstract\b", ".", text)
    text = re.sub(r"(?i)^abstract\s*", "Abstract\n\n", text)
    text = re.sub(r"\b(?:sub)*section([A-Z])", r"\n\n\1", text)
    text = re.sub(r"\b(?:cite|ref|label)[A-Za-z0-9:_-]*\b", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def has_detex() -> bool:
    return shutil.which("detex") is not None


def looks_like_latex(text: str) -> bool:
    markers = [
        r"\\begin\{",
        r"\\end\{",
        r"\\section\*?\{",
        r"\\subsection\*?\{",
        r"\\title\{",
        r"\\author\{",
        r"\\cite\{",
        r"\\ref\{",
        r"\\label\{",
        r"\\documentclass",
    ]
    hits = sum(bool(re.search(pat, text)) for pat in markers)
    return hits >= 1 or "\\begin{document}" in text or "\\end{document}" in text


def detex_text(text: str, *, replace_math: bool = True) -> str:
    """Strip LaTeX commands from raw `.tex` content using the external `detex` tool.

    Raises `RuntimeError` if `detex` is not installed or returns a non-zero exit code.
    """
    exe = shutil.which("detex")
    if exe is None:
        raise RuntimeError("detex is not installed. Install opendetex to ingest .tex files.")

    cmd = [exe, "-n"]
    if replace_math:
        cmd.append("-r")
    proc = subprocess.run(
        cmd,
        input=text,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "detex failed")
    return _normalize_detex_output(proc.stdout)


def detex_file(path: str | Path, *, replace_math: bool = True) -> str:
    file_path = Path(path)
    return detex_text(file_path.read_text(encoding="utf-8", errors="ignore"), replace_math=replace_math)


def tex_to_markdown(path: str | Path, *, replace_math: bool = True) -> str:
    return cleanup_paper_markdown(detex_file(path, replace_math=replace_math))


def preprocess_runtime_text(text: str) -> str:
    """Normalize text before scoring.

    If the input looks like raw LaTeX and `detex` is available, strip the TeX markup
    and run lightweight cleanup on the result while preserving the original order.
    Otherwise, return the text with only lightweight whitespace normalization.
    """
    if looks_like_latex(text) and has_detex():
        return clean_extracted_text(detex_text(text))
    return clean_extracted_text(text)
