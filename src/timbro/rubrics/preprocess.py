"""Markdown/markup preprocessing (#16): strip non-prose markup before rubric analysis.

Rubrics analyze raw file text. On real markdown posts, a large share of findings
anchor on non-prose (YAML frontmatter, HTML comments, fenced code, table syntax,
footnote markers, ...) rather than prose quality. `strip_markup` removes that markup
so the checks in schimel/density see prose only. Stdlib/regex only, no markdown
parser -- this is a best-effort textual cleanup, not a spec-compliant markdown AST.

Paragraph/sentence indices in findings refer to the *cleaned* text (acceptable per
#16: the consumer is an LLM holding the span text, not a line-number lookup against
the original file).
"""

from __future__ import annotations

import re

# 1. YAML frontmatter: `---` at the very start of the doc through the closing `---` line.
_FRONTMATTER = re.compile(r"\A---[ \t]*\n.*?\n---[ \t]*\n?", re.S)

# 2. Fenced code blocks: ``` or ~~~, with or without a language tag. Non-greedy match
# between two occurrences of the same fence handles both the standard multi-line block
# and a malformed same-line open/close.
_FENCE = re.compile(r"(```|~~~).*?\1", re.S)

# 3. HTML comments (possibly multiline).
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)

# 4. Inline code spans: single backticks, content included, bounded to one line so a
# stray unmatched backtick can't swallow the rest of the document.
_INLINE_CODE = re.compile(r"`[^`\n]+`")

# 5. HTML tags: strip the tag, keep inner text. Anchored to a tag-name start
# (`</p>`, `<div ...>`, `<!DOCTYPE ...>`) so prose inequalities like "x < 3 and y > 2"
# are left alone.
_HTML_TAG = re.compile(r"</?[a-zA-Z!][^>]*>")

# 6. Images (dropped) and links (unwrapped to their text).
_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
_LINK = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")

# 7. Footnotes: definition lines keep the text (as their own paragraph, since a
# footnote definition already sits on its own line); inline refs are dropped.
_FOOTNOTE_DEF = re.compile(r"(?m)^[ \t]*\[\^[^\]]+\]:[ \t]*")
_FOOTNOTE_REF = re.compile(r"\[\^[^\]]+\]")

# 8. ATX headings: navigation, not prose -- drop the whole line.
_HEADING = re.compile(r"(?m)^[ \t]*#{1,6}[ \t]+.*$\n?")

# 9. Blockquote / list / emphasis markers: unwrap, keep the text.
_BLOCKQUOTE = re.compile(r"(?m)^[ \t]*>+[ \t]?")
_BULLET_LIST = re.compile(r"(?m)^[ \t]*[-*+][ \t]+")
_ORDERED_LIST = re.compile(r"(?m)^[ \t]*\d+\.[ \t]+")
_BOLD_STAR = re.compile(r"\*\*(.+?)\*\*", re.S)
_BOLD_UNDERSCORE = re.compile(r"__(.+?)__", re.S)
_STRIKE = re.compile(r"~~(.+?)~~", re.S)
# Italic marks follow the usual markdown emphasis rule: the opening mark must not be
# preceded by a word character and must be followed by non-space; the closing mark must
# be preceded by non-space and not followed by a word character. This keeps prose
# arithmetic ("4*7 and 3*5") and snake_case identifiers ("user_id_field") intact.
_ITALIC_STAR = re.compile(r"(?<![\w*])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![\w*])")
_ITALIC_UNDERSCORE = re.compile(r"(?<![\w_])_(?!\s)([^_\n]+?)(?<!\s)_(?![\w_])")

# 10. Table rows: `|...|` lines and separator rows (`---|---`, `:--|--:`, ...). The
# separator pattern requires at least one `|` so a bare `---` thematic break (not a
# table construct at all) is left alone.
_TABLE_ROW = re.compile(r"(?m)^[ \t]*\|.*\|[ \t]*$\n?")
_TABLE_SEPARATOR = re.compile(
    r"(?m)^[ \t]*:?-{2,}:?(?:[ \t]*\|[ \t]*:?-{2,}:?)+[ \t]*$\n?"
)

# 11. Collapse 3+ consecutive newlines to a paragraph boundary (2).
_EXCESS_BLANK_LINES = re.compile(r"\n{3,}")
_TRAILING_LINE_WHITESPACE = re.compile(r"[ \t]+$", re.M)


def strip_markup(text: str) -> str:
    """Strip markdown/markup so rubric checks see prose only.

    Applies the #16 transformations in order: frontmatter, fenced code, HTML
    comments, inline code, HTML tags, images/links, footnotes, ATX headings,
    blockquote/list/emphasis markers, table rows, then collapses blank-line runs.
    """
    text = _FRONTMATTER.sub("", text)
    text = _FENCE.sub("", text)
    text = _HTML_COMMENT.sub("", text)
    text = _INLINE_CODE.sub("", text)
    text = _HTML_TAG.sub("", text)
    text = _IMAGE.sub("", text)
    text = _LINK.sub(r"\1", text)
    text = _FOOTNOTE_DEF.sub("", text)
    text = _FOOTNOTE_REF.sub("", text)
    text = _HEADING.sub("", text)
    text = _BLOCKQUOTE.sub("", text)
    text = _BULLET_LIST.sub("", text)
    text = _ORDERED_LIST.sub("", text)
    text = _BOLD_STAR.sub(r"\1", text)
    text = _BOLD_UNDERSCORE.sub(r"\1", text)
    text = _STRIKE.sub(r"\1", text)
    text = _ITALIC_STAR.sub(r"\1", text)
    text = _ITALIC_UNDERSCORE.sub(r"\1", text)
    text = _TABLE_SEPARATOR.sub("", text)
    text = _TABLE_ROW.sub("", text)
    text = _TRAILING_LINE_WHITESPACE.sub("", text)
    text = _EXCESS_BLANK_LINES.sub("\n\n", text)
    return text.strip()
