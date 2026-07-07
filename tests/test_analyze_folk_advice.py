"""Folk-advice exploratory features (#21): struct_*, fm_desc_*, and new dict_*.

Hand-computed expected values mirror the #18 fixture style. The public seam is
`analyze_text(raw)` -> feature dict; every new feature is an additive key on it.
"""

from __future__ import annotations

import unittest

from timbro.analyze import analyze_text

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


class StructFeatureTests(unittest.TestCase):
    def setUp(self):
        self.f = analyze_text(STRUCT_FIXTURE)

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
        f = analyze_text(NAME_FAIL_FIXTURE)
        self.assertEqual(f["struct_name_format_valid"], 0)


class FmDescFeatureTests(unittest.TestCase):
    def setUp(self):
        self.f = analyze_text(STRUCT_FIXTURE)

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
        self.f = analyze_text("")

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


class DictFeatureTests(unittest.TestCase):
    def test_allcaps_directive_per_1k(self):
        # "ALWAYS" + "NEVER" are in the directive set; 9 prose tokens.
        f = analyze_text("ALWAYS run tests. NEVER skip the build.")
        self.assertAlmostEqual(f["dict_allcaps_directive_per_1k"], 2 / 9 * 1000)

    def test_contrastive_example_count(self):
        # "Do:" + "Don't:" word-markers + a lone "✅" symbol line = 3.
        f = analyze_text("Do: run it.\nDon't: skip it.\n✅ tests pass.")
        self.assertEqual(f["dict_contrastive_example_count"], 3)

    def test_first_person_ratio_all(self):
        f = analyze_text("I will run the tests. We should check the output.")
        self.assertEqual(f["dict_first_person_subject_ratio"], 1.0)

    def test_first_person_ratio_mixed(self):
        f = analyze_text("I will run the tests. The build passed.")
        self.assertEqual(f["dict_first_person_subject_ratio"], 0.5)


class DictEmptyFileTests(unittest.TestCase):
    def setUp(self):
        self.f = analyze_text("")

    def test_allcaps_zero(self):
        self.assertEqual(self.f["dict_allcaps_directive_per_1k"], 0.0)

    def test_contrastive_zero(self):
        self.assertEqual(self.f["dict_contrastive_example_count"], 0)

    def test_first_person_none_like_imperative(self):
        self.assertIsNone(self.f["dict_first_person_subject_ratio"])


if __name__ == "__main__":
    unittest.main()
