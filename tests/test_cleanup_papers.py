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

    def test_whitespace_only_blank_line_before_punctuation_is_kept(self):
        # A blank line made of spaces is still a paragraph break for
        # _paragraphs (it splits on \n\s*\n), so the collapse must keep it.
        self.assertEqual(clean_extracted_text("para.\n \n!!!"), "para.\n \n!!!")

    def test_tab_only_blank_line_before_punctuation_is_kept(self):
        # Same, with the blank line made of a tab.
        self.assertEqual(clean_extracted_text("para.\n\t\n!!!"), "para.\n\t\n!!!")

    def test_paragraph_break_before_open_paren_is_kept(self):
        # The (\s+ rule has the same paragraph-fusing flaw (#179).
        self.assertEqual(clean_extracted_text("(\n\nfoo"), "(\n\nfoo")

    def test_paragraph_break_before_close_paren_is_kept(self):
        # The \s+) rule has the same paragraph-fusing flaw (#179).
        self.assertEqual(clean_extracted_text("foo\n\n)"), "foo\n\n)")


class ExtractProseExcerptPunctuationBlockTests(unittest.TestCase):
    """Issue #179: a punctuation block after a paragraph must not eat the paragraph."""

    def test_repro_paragraph_survives_punctuation_block(self):
        text = REPRO_PARAGRAPH + "\n\n" + "!!!???...,;;:" * 20
        self.assertEqual(extract_prose_excerpt(text), REPRO_PARAGRAPH + "\n")

    def test_repro_paragraph_survives_block_after_space_blank_line(self):
        # A blank line made of whitespace still separates the paragraphs (#179).
        text = REPRO_PARAGRAPH + "\n \n" + "!!!???...,;;:" * 20
        self.assertEqual(extract_prose_excerpt(text), REPRO_PARAGRAPH + "\n")


if __name__ == "__main__":
    unittest.main()
