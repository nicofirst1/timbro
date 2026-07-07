from __future__ import annotations

import unittest

from timbro.text import strip_markup


class StripMarkupTests(unittest.TestCase):
    """One test per #16 transformation, plus an integration fixture combining them."""

    def test_yaml_frontmatter_dropped(self):
        text = '---\ntitle: "Hello"\ndate: 2026-01-01\n---\n\nActual prose here.'
        self.assertEqual(strip_markup(text), "Actual prose here.")

    def test_frontmatter_only_stripped_at_document_start(self):
        # A `---` later in the body is not frontmatter and must survive untouched
        # (aside from the generic newline collapse).
        text = "Intro paragraph.\n\n---\n\nMore prose."
        out = strip_markup(text)
        self.assertIn("---", out)
        self.assertIn("Intro paragraph.", out)
        self.assertIn("More prose.", out)

    def test_fenced_code_block_dropped_with_language_tag(self):
        text = "Before.\n\n```python\nx = 1\ny = 2\n```\n\nAfter."
        out = strip_markup(text)
        self.assertNotIn("x = 1", out)
        self.assertNotIn("```", out)
        self.assertIn("Before.", out)
        self.assertIn("After.", out)

    def test_fenced_code_block_dropped_without_language_tag(self):
        text = "Before.\n\n~~~\nraw block\n~~~\n\nAfter."
        out = strip_markup(text)
        self.assertNotIn("raw block", out)
        self.assertNotIn("~~~", out)

    def test_html_comment_dropped(self):
        text = "Prose before.\n\n<!-- VIZ: a chart description that spans\nmultiple lines -->\n\nProse after."
        out = strip_markup(text)
        self.assertNotIn("VIZ", out)
        self.assertIn("Prose before.", out)
        self.assertIn("Prose after.", out)

    def test_inline_code_span_dropped_with_content(self):
        text = "Run the `timbro score draft.md` command to check."
        out = strip_markup(text)
        self.assertNotIn("timbro score draft.md", out)
        self.assertNotIn("`", out)

    def test_html_tags_stripped_keep_inner_text(self):
        text = "<p>Some prose <strong>emphasized</strong> here.</p>"
        out = strip_markup(text)
        self.assertEqual(out, "Some prose emphasized here.")

    def test_pure_embed_html_tag_disappears(self):
        text = 'Before.\n\n<div data-viz="collection" style="margin: 1rem;"></div>\n\nAfter.'
        out = strip_markup(text)
        self.assertNotIn("<div", out)
        self.assertNotIn("data-viz", out)
        self.assertIn("Before.", out)
        self.assertIn("After.", out)

    def test_image_dropped_entirely(self):
        text = "Before. ![a bike lock](/assets/lock.png) After."
        out = strip_markup(text)
        self.assertNotIn("bike lock", out)
        self.assertNotIn("![", out)

    def test_link_keeps_text_drops_url(self):
        text = "See [Distill.pub](https://distill.pub/) for details."
        out = strip_markup(text)
        self.assertIn("Distill.pub", out)
        self.assertNotIn("https://distill.pub/", out)
        self.assertNotIn("[", out)
        self.assertNotIn("(", out)

    def test_footnote_inline_ref_dropped(self):
        text = "Should be safe, right?[^meme]"
        out = strip_markup(text)
        self.assertNotIn("[^meme]", out)
        self.assertEqual(out, "Should be safe, right?")

    def test_footnote_definition_keeps_text(self):
        text = "Body text.\n\n[^meme]: This is the footnote body text."
        out = strip_markup(text)
        self.assertNotIn("[^meme]:", out)
        self.assertIn("This is the footnote body text.", out)

    def test_atx_heading_line_dropped(self):
        text = "## The Scene of the Crime\n\nActual prose paragraph follows."
        out = strip_markup(text)
        self.assertNotIn("Scene of the Crime", out)
        self.assertIn("Actual prose paragraph follows.", out)

    def test_blockquote_marker_unwrapped(self):
        text = "> A quoted line of real prose."
        out = strip_markup(text)
        self.assertNotIn(">", out)
        self.assertIn("A quoted line of real prose.", out)

    def test_list_markers_unwrapped(self):
        text = "- first item\n* second item\n1. third item"
        out = strip_markup(text)
        self.assertNotIn("- ", out)
        self.assertNotIn("* ", out)
        self.assertNotIn("1. ", out)
        self.assertIn("first item", out)
        self.assertIn("second item", out)
        self.assertIn("third item", out)

    def test_emphasis_markers_unwrapped(self):
        text = "This is **bold**, this is *italic*, this is _also italic_, this is ~~struck~~."
        out = strip_markup(text)
        self.assertNotIn("*", out)
        self.assertNotIn("_", out)
        self.assertNotIn("~~", out)
        self.assertIn("bold", out)
        self.assertIn("italic", out)
        self.assertIn("also italic", out)
        self.assertIn("struck", out)

    def test_table_rows_dropped(self):
        text = "Before.\n\n| A | B |\n| --- | --- |\n| 1 | 2 |\n\nAfter."
        out = strip_markup(text)
        self.assertNotIn("|", out)
        self.assertNotIn("---", out)
        self.assertIn("Before.", out)
        self.assertIn("After.", out)

    def test_bare_horizontal_rule_is_not_treated_as_table_separator(self):
        text = "Intro.\n\n---\n\nMore prose."
        out = strip_markup(text)
        self.assertIn("---", out)

    def test_excess_blank_lines_collapsed(self):
        text = "Para one.\n\n\n\n\nPara two."
        out = strip_markup(text)
        self.assertEqual(out, "Para one.\n\nPara two.")

    def test_plain_prose_nearly_unchanged(self):
        text = "This is a plain sentence. It has no markup at all, just words."
        self.assertEqual(strip_markup(text), text)

    def test_inequality_prose_survives_html_tag_stripping(self):
        text = "Values where x < 3 and y > 2 hold."
        self.assertEqual(strip_markup(text), text)

    def test_two_multiplications_are_not_paired_as_italics(self):
        text = "Compute 4*7 and 3*5 here."
        self.assertEqual(strip_markup(text), text)

    def test_snake_case_identifier_with_two_underscores_survives(self):
        text = "The user_id_field maps to the primary key."
        self.assertEqual(strip_markup(text), text)

    def test_technical_prose_with_operators_and_identifiers_unchanged(self):
        text = (
            "If retry_count < max_retries and backoff > 0, multiply delay by 2*factor. "
            "The response_time_ms column stays below p99 when batch_size*workers is small."
        )
        self.assertEqual(strip_markup(text), text)

    def test_integration_fixture_combining_all_transformations(self):
        text = (
            "---\n"
            'title: "Test post"\n'
            "---\n\n"
            "# A Heading\n\n"
            "> **TL;DR;** short summary of the post.\n\n"
            "Some *emphasized* and **bold** prose with a [link](https://example.com) "
            "and an inline `code_token()` call.\n\n"
            "```python\n"
            "dropped_code = True\n"
            "```\n\n"
            "<!-- VIZ: chart notes -->\n"
            "<div data-viz=\"x\"></div>\n\n"
            "![an image](https://example.com/img.png)\n\n"
            "- bullet one\n"
            "- bullet two\n\n"
            "| col1 | col2 |\n"
            "| --- | --- |\n"
            "| a | b |\n\n"
            "A closing paragraph with a footnote ref.[^note]\n\n"
            "[^note]: The footnote body survives as prose."
        )
        out = strip_markup(text)
        for gone in (
            "title:",
            "# A Heading",
            "```",
            "dropped_code",
            "VIZ",
            "<div",
            "data-viz",
            "an image",
            "https://example.com/img.png",
            "code_token()",
            "[^note]",
            "- bullet",
            "|",
        ):
            self.assertNotIn(gone, out)
        for present in (
            "short summary of the post.",
            "emphasized",
            "bold",
            "link",
            "bullet one",
            "bullet two",
            "The footnote body survives as prose.",
        ):
            self.assertIn(present, out)


if __name__ == "__main__":
    unittest.main()
