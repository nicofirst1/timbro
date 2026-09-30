from __future__ import annotations

import unittest

from timbro.cleanup import clean_extracted_text, extract_prose_excerpt

REPRO_PARAGRAPH = (
    "We shipped the parser on Tuesday after three days of debugging, and the fix was a stale "
    "cache that nobody had invalidated. The measurement surprised us: latency dropped by forty "
    "percent, but only for documents under two thousand words. I keep notes in one file per "
    "project, because search beats structure when the structure is only a week old."
)


class CleanExtractedTextParagraphBreakTests(unittest.TestCase):
    """Issue #179: the whitespace-collapsing rules must not fuse paragraphs."""

    def test_line_wrap_before_punctuation_still_collapses(self):
        # A single newline (PDF line wrap) before punctuation still collapses.
        self.assertEqual(clean_extracted_text("word\n, next"), "word, next")

    def test_paragraph_break_before_punctuation_is_kept(self):
        # A blank line between paragraphs must not be swallowed by the collapse.
        self.assertEqual(clean_extracted_text("a\n\n, b"), "a\n\n, b")


class ExtractProseExcerptPunctuationBlockTests(unittest.TestCase):
    """Issue #179: a punctuation block after a paragraph must not eat the paragraph."""

    def test_repro_paragraph_survives_punctuation_block(self):
        text = REPRO_PARAGRAPH + "\n\n" + "!!!???...,;;:" * 20
        self.assertEqual(extract_prose_excerpt(text), REPRO_PARAGRAPH + "\n")


if __name__ == "__main__":
    unittest.main()
