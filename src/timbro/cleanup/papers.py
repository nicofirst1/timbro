"""Helpers for turning extracted papers into style-usable prose.

These routines are intentionally conservative: strip obvious PDF noise, keep the
frontmatter intact, and reduce a paper to prose-heavy sections such as the
abstract and introduction. Timbro's POS features are sensitive to layout
artifacts, figures, tables, and reference blocks, so this module prefers a
clean excerpt over raw full-text dumps.
"""

from __future__ import annotations

import re
from pathlib import Path

_ABSTRACT = re.compile(r"^abstract\b[:.]?\s*", re.I)
_INTRO = re.compile(r"^(?:\d+(?:\.\d+)*)?\s*introduction\b[:.]?\s*", re.I)
_HEADING = re.compile(r"^(?:\d+(?:\.\d+)*)?\s*[A-Z][A-Za-z0-9\-&,/() ]{1,80}$")
_METADATA_PREFIXES = (
    "edited by:",
    "reviewed by:",
    "correspondence:",
    "*correspondence:",
    "current address:",
    "keywords:",
    "contents",
    "manuscript received",
    "for reprints",
    "downloaded from",
    "reports",
    "appendix",
    "index",
)


def split_frontmatter(text: str) -> tuple[str, str]:
    if text.startswith("---\n"):
        parts = text.split("\n---\n", 1)
        if len(parts) == 2:
            return parts[0] + "\n---\n", parts[1].strip()
    return "", text.strip()


def clean_extracted_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x0c", "\n").replace("\u00ad", "")
    text = re.sub(r"([A-Za-z])\-\n([a-z])", r"\1\2", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"\s+([,.;:?!])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)
    return text.strip()


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _looks_like_metadata_line(line: str) -> bool:
    lower = line.lower().strip()
    if not lower:
        return True
    if lower.startswith(_METADATA_PREFIXES):
        return True
    if "@" in line and len(line) < 300:
        return True
    if "copyright" in lower or "all rights reserved" in lower:
        return True
    if "created from" in lower or "proquest" in lower:
        return True
    if "tel.:" in lower or "fax:" in lower:
        return True
    if len(line) < 120 and re.fullmatch(r"[A-Za-z0-9*†‡◁⋄ ,()\-:/&.]+", line):
        words = line.split()
        if words and sum(word[:1].isupper() for word in words) >= max(2, len(words) * 0.6):
            if not line.endswith("."):
                return True
    return False


def _normalize_paragraph(paragraph: str) -> str:
    lines = [line.strip() for line in paragraph.split("\n") if line.strip()]
    while lines and _looks_like_metadata_line(lines[0]) and not (_ABSTRACT.match(lines[0]) or _INTRO.match(lines[0])):
        lines.pop(0)
    lines = [line for line in lines if not _looks_like_metadata_line(line)]
    paragraph = " ".join(lines)
    paragraph = re.sub(r"\bShared first authorship\.\s*", "", paragraph, flags=re.I)
    paragraph = re.sub(r"\bKeywords:\s*[^.]+\.?", "", paragraph, flags=re.I)
    paragraph = re.sub(r"[∗*†‡]+\s*Equal contribution\.\s*", "", paragraph, flags=re.I)
    paragraph = re.sub(r"[∗*†‡]+\s*Corresponding author:.*", "", paragraph, flags=re.I)
    paragraph = re.sub(r"^\d+(?:\.\d+)*\.\s+Introduction\s+", "", paragraph, flags=re.I)
    paragraph = re.sub(r"\b\d+\s+The workshop(?:['’]s)? website is available at https?://\S+\.?", "", paragraph, flags=re.I)
    paragraph = re.sub(r"\b\d+\s+Meta restricts commercial use[^.]*\.\s*", "", paragraph, flags=re.I)
    paragraph = re.sub(r"\s+\*\s*$", "", paragraph)
    paragraph = paragraph.replace("plug-andplay", "plug-and-play")
    if not re.search(r"[.!?][\]\)\"']?$", paragraph):
        last_stop = max(paragraph.rfind("."), paragraph.rfind("!"), paragraph.rfind("?"))
        if last_stop > 0:
            paragraph = paragraph[: last_stop + 1]
    return re.sub(r"\s{2,}", " ", paragraph).strip()


def _is_heading(paragraph: str) -> bool:
    return len(paragraph) <= 100 and bool(_HEADING.match(paragraph)) and not paragraph.endswith(".")


def _looks_like_prose(paragraph: str) -> bool:
    if len(paragraph) < 180:
        return False
    lower = paragraph.lower()
    if lower.startswith((
        "figure ",
        "fig. ",
        "table ",
        "keywords:",
        "contents",
        "permission to make",
        "proceedings of",
        "pages ",
        "reports ",
    )):
        return False
    letters = sum(ch.isalpha() for ch in paragraph)
    chars = sum(not ch.isspace() for ch in paragraph) or 1
    if letters / chars < 0.6:
        return False
    short_tokens = sum(1 for tok in paragraph.split() if len(tok) == 1)
    if short_tokens > max(12, len(paragraph.split()) // 5):
        return False
    return True


def _looks_like_metadata(paragraph: str) -> bool:
    lower = paragraph.lower()
    if lower.startswith(_METADATA_PREFIXES):
        return True
    if lower.startswith(("fig. ", "figure ")):
        return True
    if "downloaded from" in lower or "all rights reserved" in lower:
        return True
    if "created from" in lower or "proquest" in lower:
        return True
    if "manuscript received" in lower or "corresponding editor" in lower:
        return True
    if lower.startswith("reports "):
        return True
    if "@" in paragraph and len(paragraph) < 500:
        return True
    if paragraph.count(",") >= 5 and paragraph.count(".") <= 2 and len(paragraph) < 500:
        return True
    institutions = ("university", "department", "institute", "school", "center", "centre", "laboratory")
    if sum(word in lower for word in institutions) >= 3 and paragraph.count(",") >= 4:
        return True
    if re.fullmatch(r"[A-Za-z0-9*†‡◁⋄ ,()\-]+", paragraph) and len(paragraph.split()) < 30:
        return True
    return False


def _strip_title_and_author_preamble(paragraph: str, title: str) -> str:
    if not paragraph:
        return paragraph
    if title:
        title_pattern = re.escape(title.strip())
        paragraph = re.sub(rf"^{title_pattern}\s*", "", paragraph, flags=re.I)
    abstract_pos = paragraph.lower().find("abstract ")
    if abstract_pos > 0:
        return paragraph[abstract_pos:]
    sentence_start = re.search(
        r"[A-Z][a-z]+(?: [a-z][A-Za-z\-]+){1,8} (?:is|are|was|were|has|have|can|may|will|should|could|would|must)\b",
        paragraph,
    )
    if sentence_start and sentence_start.start() > 0:
        prefix = paragraph[: sentence_start.start()]
        if any(ch.isdigit() for ch in prefix) or prefix.count(",") >= 3:
            return paragraph[sentence_start.start() :]
    return paragraph


def extract_prose_excerpt(text: str, title: str = "", max_intro_paragraphs: int = 6) -> str:
    paragraphs = [_normalize_paragraph(p) for p in _paragraphs(clean_extracted_text(text))]
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        return ""
    paragraphs[0] = _strip_title_and_author_preamble(paragraphs[0], title).strip()

    while paragraphs and not (
        _ABSTRACT.match(paragraphs[0])
        or _INTRO.match(paragraphs[0])
        or _looks_like_prose(paragraphs[0])
    ):
        paragraphs.pop(0)

    paragraphs = [p for p in paragraphs if not _looks_like_metadata(p)]
    if not paragraphs:
        return ""

    excerpt: list[str] = []
    abstract_taken = 0
    intro_taken = 0
    intro_start = None

    for i, paragraph in enumerate(paragraphs):
        if _ABSTRACT.match(paragraph):
            cleaned = _ABSTRACT.sub("", paragraph, count=1).strip()
            if cleaned:
                excerpt.append(cleaned)
                abstract_taken += 1
            continue
        if abstract_taken and _INTRO.match(paragraph):
            intro_start = i
            break
        if abstract_taken and abstract_taken < 2 and _looks_like_prose(paragraph):
            excerpt.append(paragraph)
            abstract_taken += 1

    if intro_start is None:
        for i, paragraph in enumerate(paragraphs):
            if _INTRO.match(paragraph):
                intro_start = i
                break

    if intro_start is not None:
        for paragraph in paragraphs[intro_start:]:
            if _INTRO.match(paragraph):
                cleaned = _INTRO.sub("", paragraph, count=1).strip()
                if cleaned and _looks_like_prose(cleaned):
                    excerpt.append(cleaned)
                    intro_taken += 1
                continue
            if _is_heading(paragraph):
                break
            if _looks_like_prose(paragraph):
                excerpt.append(paragraph)
                intro_taken += 1
            if intro_taken >= max_intro_paragraphs:
                break

    if not excerpt:
        excerpt = [p for p in paragraphs if _looks_like_prose(p)][: max_intro_paragraphs + 2]

    if not excerpt and paragraphs:
        excerpt = sorted(paragraphs, key=len, reverse=True)[: max_intro_paragraphs]

    return "\n\n".join(excerpt).strip() + "\n"


def cleanup_paper_markdown(text: str) -> str:
    frontmatter, body = split_frontmatter(text)
    title_match = re.search(r"^title:\s*(.+)$", frontmatter, flags=re.M)
    title = title_match.group(1).strip() if title_match else ""
    excerpt = extract_prose_excerpt(body, title=title)
    if not excerpt:
        excerpt = clean_extracted_text(body) + "\n"
    return frontmatter + "\n" + excerpt if frontmatter else excerpt


def cleanup_markdown_file(path: str | Path) -> None:
    file_path = Path(path)
    file_path.write_text(
        cleanup_paper_markdown(file_path.read_text(encoding="utf-8", errors="ignore")),
        encoding="utf-8",
    )
