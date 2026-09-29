"""The markdown axis owns `_struct_features` end to end (issue #120).

The extractor moved verbatim out of the deleted analyze module, so the
`struct_*`/`fm_desc_*` features live beside the `MARKDOWN_METRIC` that scores them.
The fm-description token count must stay identical to the deleted pipeline's
`len(doc)`: only the tokenizer is run, and pipeline components never retokenize.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

import timbro


def _moved():
    """The moved extractor, imported lazily so a pre-#120 tree fails with an
    ImportError naming the missing implementation, not a collection error."""
    from timbro.axes.markdown import _struct_features

    return _struct_features


# The exact key set of the moved extractor: the 20 scored/exploratory keys plus
# `frontmatter_json`, moved whole per #120 (nothing trimmed).
EXPECTED_KEYS = {
    "struct_heading_count",
    "struct_max_heading_depth",
    "struct_code_char_ratio",
    "struct_list_item_ratio",
    "struct_table_count",
    "struct_prose_ratio",
    "struct_frontmatter_field_count",
    "struct_line_count",
    "struct_inline_code_char_ratio",
    "struct_ordered_list_ratio",
    "struct_bullet_list_ratio",
    "struct_external_ref_count",
    "struct_named_section_present",
    "struct_name_format_valid",
    "struct_long_paragraph_ratio",
    "fm_desc_present",
    "fm_desc_tokens",
    "fm_desc_when_clause",
    "fm_desc_or_count",
    "fm_desc_wildcard_per_token",
    "frontmatter_json",
}

# fm_desc_tokens per description, captured on the pre-move code (base 71aa1c9) with
# the deleted four-pipe feature pipeline over the raw description. The moved extractor
# must produce the same counts with the shared tokenizer alone.
EXPECTED_FM_TOKENS = (
    ('', 0),
    ('Short one.', 3),
    ('Use this skill when you need to test things or verify any output.', 14),
    ("It's a tool that doesn't sleep; you're expected to run it nightly.", 17),
    ('Hyphen-ated world-class state-of-the-art descriptions work, too.', 18),
    ('Unicode: naïve café résumé — 中文 too 🎉✅.', 11),
    ('Visit https://example.com/docs?a=1&b=2 for help, or email me@example.com.', 9),
    ('Emoji-heavy: 🚀🚀🚀 launch it! 🎯', 11),
    ('A description with\ttabs\nand newlines inside.', 10),
    ('"Quoted" and \'single-quoted\' text with braces {json: like} and [brackets].', 22),
    ('Mr. Smith Jr. went to Washington D.C. on Jan. 5th — e.g. the U.S. capitol.', 16),
    ('    leading and trailing whitespace    ', 6),
    ('ALLCAPS WORDS EVERYWHERE ALWAYS', 4),
    ("Don't stop believing; hold on to that feelin'.", 12),
    ('3.14159 plus 42 equals 45.14159 (roughly).', 9),
    ('CamelCaseIdentifiers and snake_case_identifiers and kebab-case-ids', 9),
    ('A very long description that goes on and on, repeating itself, padding the token count well past thirty tokens so the tokenizer has real work to do, with commas, semicolons; and more clauses.', 39),
    ('<html><body>markup-ish</body></html>', 7),
    ('math: 2 < 3 > 1, x = y * z / w, a % b # c $ d @ e & f', 27),
    ('संस्कृत and العربية and עברית scripts', 6),
    ('one', 1),
    ('Ends with a newline\n', 5),
)

FIXTURE = (
    "---\n"
    "title: Test Skill\n"
    "tags: [a, b]\n"
    "---\n"
    "\n"
    "# Heading One\n"
    "\n"
    "## Heading Two\n"
    "\n"
    "This is the first sentence. This is the second sentence, with more words. "
    "This is the third and final sentence.\n"
    "\n"
    "```python\n"
    "x = 1\n"
    "```\n"
    "\n"
    "- item one\n"
    "- item two\n"
)

# 20 physical lines (no trailing newline). Frontmatter with a valid `name` and a
# `description`; a named-section heading ("Usage Guidelines"); inline code
# ("inline_code" = 11 chars); a fenced block (19 chars: "```python\nx = 1\n```");
# a scripts/ markdown link + a bare references/ mention; a 2-item ordered list and
# a 1-item bullet list. 14 non-blank lines.
STRUCT_FIXTURE = (
    "---\n"
    "name: my-skill\n"
    "description: Use this skill when you need to test things or verify any output.\n"
    "---\n"
    "\n"
    "# Title\n"
    "\n"
    "## Usage Guidelines\n"
    "\n"
    "Here is some prose with `inline_code` in it.\n"
    "\n"
    "See [the script](scripts/foo.py) for details, or references/bar.md directly.\n"
    "\n"
    "```python\n"
    "x = 1\n"
    "```\n"
    "\n"
    "1. first step\n"
    "2. second step\n"
    "- bullet one"
)

NAME_FAIL_FIXTURE = "---\nname: My-Skill\ndescription: short\n---\n\nbody\n"


def _fm_doc(description: str) -> str:
    # json.dumps with ensure_ascii=False doubles as a YAML double-quoted scalar,
    # so any description (newlines, tabs, quotes, emoji) embeds and parses back
    # verbatim.
    return f"---\ndescription: {json.dumps(description, ensure_ascii=False)}\n---\n\nbody\n"


class StructExtractorTests(unittest.TestCase):
    def test_struct_features_exists_and_returns_all_keys(self):
        struct, prose = _moved()(STRUCT_FIXTURE)
        self.assertEqual(set(struct), EXPECTED_KEYS)
        self.assertIsInstance(struct, dict)
        self.assertIsInstance(prose, str)
        # A spot check on the fixture's own frontmatter, exercising the tokenizer path.
        self.assertEqual(struct["fm_desc_present"], 1)
        self.assertEqual(struct["fm_desc_tokens"], 14)


class RemovedModuleTests(unittest.TestCase):
    def test_analyze_module_gone(self):
        self.assertIsNone(importlib.util.find_spec("timbro.analyze"))

    def test_lexicons_dir_gone(self):
        self.assertFalse((Path(timbro.__file__).parent / "lexicons").exists())

    def test_analyze_subcommand_invalid_choice(self):
        proc = subprocess.run(
            [sys.executable, "-m", "timbro.cli", "analyze", "--help"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("invalid choice", proc.stderr)


class FmDescTokenCountTests(unittest.TestCase):
    def test_fm_desc_tokens_match_base_pipeline(self):
        for description, expected in EXPECTED_FM_TOKENS:
            with self.subTest(description=description[:48] or "<empty>"):
                struct, _ = _moved()(_fm_doc(description))
                self.assertEqual(struct["fm_desc_present"], 1 if description else 0)
                self.assertEqual(struct["fm_desc_tokens"], expected)


class StructTests(unittest.TestCase):
    """Fixture has 2 headings, 1 code block, 2 frontmatter fields, 2 list items,
    3 real sentences + 2 unpunctuated list-item fragments in the stripped prose."""

    def setUp(self):
        self.features, _ = _moved()(FIXTURE)

    def test_heading_count_and_depth(self):
        self.assertEqual(self.features["struct_heading_count"], 2)
        self.assertEqual(self.features["struct_max_heading_depth"], 2)

    def test_code_char_ratio(self):
        self.assertAlmostEqual(self.features["struct_code_char_ratio"], 19 / 227)

    def test_list_item_ratio(self):
        self.assertAlmostEqual(self.features["struct_list_item_ratio"], 2 / 12)

    def test_table_count_zero(self):
        self.assertEqual(self.features["struct_table_count"], 0)

    def test_prose_ratio(self):
        prose_len = len(
            "This is the first sentence. This is the second sentence, with more words. "
            "This is the third and final sentence.\n\nitem one\nitem two"
        )
        self.assertAlmostEqual(self.features["struct_prose_ratio"], prose_len / 227)

    def test_frontmatter_field_count_and_json(self):
        self.assertEqual(self.features["struct_frontmatter_field_count"], 2)
        self.assertIn('"title": "Test Skill"', self.features["frontmatter_json"])

    def test_frontmatter_date_scalars_do_not_crash(self):
        fixture = (
            "---\n"
            "title: Test Skill\n"
            "created: 2025-03-01\n"
            "updated: 2025-03-01 12:00:00\n"
            "---\n"
            "\n"
            "Some prose sentence here.\n"
        )
        features, _ = _moved()(fixture)
        frontmatter = json.loads(features["frontmatter_json"])
        self.assertEqual(frontmatter["created"], "2025-03-01")
        self.assertEqual(frontmatter["updated"], "2025-03-01 12:00:00")


class StructEdgeCaseTests(unittest.TestCase):
    def test_empty_file_never_crashes(self):
        features, _ = _moved()("")
        self.assertIsNone(features["struct_code_char_ratio"])
        self.assertIsNone(features["struct_prose_ratio"])
        self.assertIsNone(features["struct_list_item_ratio"])
        self.assertEqual(features["struct_heading_count"], 0)
        self.assertEqual(features["struct_frontmatter_field_count"], 0)

    def test_code_only_file_never_crashes(self):
        text = "```python\nx = 1\ny = 2\n```\n"
        features, _ = _moved()(text)
        self.assertEqual(features["struct_prose_ratio"], 0.0)


class LongParagraphTests(unittest.TestCase):
    """Long-paragraph ratio (#22): struct_long_paragraph_ratio cases from the
    pre-#120 suite (their dict_/read_ siblings died with the deleted module)."""

    def test_long_paragraph_ratio(self):
        # Para 1 has 7 sentence terminators (> 6); para 2 has 1. -> 1 of 2 paragraphs long.
        text = "A. B. C. D. E. F. G.\n\nOnly one sentence."
        features, _ = _moved()(text)
        self.assertEqual(features["struct_long_paragraph_ratio"], 0.5)

    def test_long_paragraph_ignores_code_fence(self):
        # A fenced block full of periods must not count as a long prose paragraph.
        text = "```\na. b. c. d. e. f. g. h.\n```\n\nJust one.\n"
        features, _ = _moved()(text)
        self.assertEqual(features["struct_long_paragraph_ratio"], 0.0)

    def test_empty_file_new_features_zero(self):
        # Issue #22 contract: empty file -> struct_long_paragraph_ratio is 0.0,
        # never None, never crash.
        f, _ = _moved()("")
        self.assertEqual(f["struct_long_paragraph_ratio"], 0.0)


class StructFeatureTests(unittest.TestCase):
    def setUp(self):
        self.f, _ = _moved()(STRUCT_FIXTURE)

    def test_line_count(self):
        self.assertEqual(self.f["struct_line_count"], 20)

    def test_inline_code_char_ratio(self):
        # "inline_code" (11 chars) inside single backticks, fenced block removed first.
        self.assertAlmostEqual(
            self.f["struct_inline_code_char_ratio"], 11 / len(STRUCT_FIXTURE)
        )

    def test_ordered_and_bullet_split(self):
        self.assertAlmostEqual(self.f["struct_ordered_list_ratio"], 2 / 14)
        self.assertAlmostEqual(self.f["struct_bullet_list_ratio"], 1 / 14)

    def test_list_item_ratio_backward_compat(self):
        # bullet + ordered combined, unchanged from before this issue.
        self.assertAlmostEqual(self.f["struct_list_item_ratio"], 3 / 14)

    def test_external_ref_count(self):
        # 1 scripts/ link target + 1 bare references/ mention.
        self.assertEqual(self.f["struct_external_ref_count"], 2)

    def test_named_section_present(self):
        self.assertEqual(self.f["struct_named_section_present"], 1)

    def test_name_format_valid(self):
        self.assertEqual(self.f["struct_name_format_valid"], 1)

    def test_name_format_invalid_when_uppercase(self):
        f, _ = _moved()(NAME_FAIL_FIXTURE)
        self.assertEqual(f["struct_name_format_valid"], 0)


class FmDescFeatureTests(unittest.TestCase):
    def setUp(self):
        self.f, _ = _moved()(STRUCT_FIXTURE)

    def test_present(self):
        self.assertEqual(self.f["fm_desc_present"], 1)

    def test_tokens(self):
        # spaCy tokens of the description incl. trailing "." -> 14.
        self.assertEqual(self.f["fm_desc_tokens"], 14)

    def test_when_clause(self):
        self.assertEqual(self.f["fm_desc_when_clause"], 1)

    def test_or_count(self):
        self.assertEqual(self.f["fm_desc_or_count"], 1)

    def test_wildcard_per_token(self):
        # one wildcard word ("any") / 14 tokens.
        self.assertAlmostEqual(self.f["fm_desc_wildcard_per_token"], 1 / 14)


class StructFmEmptyFileTests(unittest.TestCase):
    def setUp(self):
        self.f, _ = _moved()("")

    def test_line_count_is_zero(self):
        # 0-byte file reads 0 lines (edge-case "everything 0" over the literal
        # len(raw.split("\n")) == 1).
        self.assertEqual(self.f["struct_line_count"], 0)

    def test_zero_valued_struct_features(self):
        self.assertEqual(self.f["struct_external_ref_count"], 0)
        self.assertEqual(self.f["struct_named_section_present"], 0)
        self.assertEqual(self.f["struct_name_format_valid"], 0)

    def test_inline_ratio_is_zero(self):
        self.assertEqual(self.f["struct_inline_code_char_ratio"], 0.0)

    def test_list_ratios_zero_on_empty(self):
        self.assertEqual(self.f["struct_ordered_list_ratio"], 0.0)
        self.assertEqual(self.f["struct_bullet_list_ratio"], 0.0)

    def test_fm_desc_all_zero(self):
        self.assertEqual(self.f["fm_desc_present"], 0)
        self.assertEqual(self.f["fm_desc_tokens"], 0)
        self.assertEqual(self.f["fm_desc_when_clause"], 0)
        self.assertEqual(self.f["fm_desc_or_count"], 0)
        self.assertEqual(self.f["fm_desc_wildcard_per_token"], 0)


if __name__ == "__main__":
    unittest.main()
