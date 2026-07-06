from __future__ import annotations

import contextlib
import io
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from timbro.analyze import analyze_text, run_analyze

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


class AnalyzeStructTests(unittest.TestCase):
    """Fixture has 2 headings, 1 code block, 2 frontmatter fields, 2 list items,
    3 real sentences + 2 unpunctuated list-item fragments in the stripped prose."""

    def setUp(self):
        self.features = analyze_text(FIXTURE)

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

    def test_desc_and_read_present_and_sane(self):
        self.assertGreater(self.features["desc_tokens"], 0)
        self.assertGreater(self.features["desc_sentences"], 0)
        self.assertIsInstance(self.features["read_flesch_kincaid_grade"], float)
        self.assertIsInstance(self.features["syn_mean_dependency_distance"], float)

    def test_syn_custom_features_sane(self):
        self.assertGreater(self.features["syn_mean_tree_depth"], 0)
        self.assertGreaterEqual(self.features["syn_clausal_per_sentence"], 0)

    def test_posdep_families_sum_to_one(self):
        pos_sum = sum(v for k, v in self.features.items() if k.startswith("posdep_pos_"))
        dep_sum = sum(v for k, v in self.features.items() if k.startswith("posdep_dep_"))
        self.assertAlmostEqual(pos_sum, 1.0, places=6)
        self.assertAlmostEqual(dep_sum, 1.0, places=6)

    def test_lex_features_sane(self):
        self.assertGreaterEqual(self.features["lex_mtld"], 0)
        self.assertGreaterEqual(self.features["lex_hdd"], 0)
        self.assertIsInstance(self.features["lex_zipf_mean"], float)


class AnalyzeEdgeCaseTests(unittest.TestCase):
    def test_empty_file_never_crashes(self):
        features = analyze_text("")
        self.assertEqual(features["desc_tokens"], 0)
        self.assertIsNone(features["struct_code_char_ratio"])
        self.assertIsNone(features["struct_prose_ratio"])
        self.assertIsNone(features["struct_list_item_ratio"])
        self.assertEqual(features["struct_heading_count"], 0)
        self.assertEqual(features["struct_frontmatter_field_count"], 0)

    def test_code_only_file_never_crashes(self):
        text = "```python\nx = 1\ny = 2\n```\n"
        features = analyze_text(text)
        self.assertEqual(features["desc_tokens"], 0)
        self.assertEqual(features["struct_prose_ratio"], 0.0)
        pos_sum = sum(v for k, v in features.items() if k.startswith("posdep_pos_"))
        self.assertEqual(pos_sum, 0.0)

    def test_empty_file_dict_and_coh_features_never_crash(self):
        features = analyze_text("")
        self.assertIsNone(features["dict_imperative_ratio"])
        self.assertIsNone(features["dict_conditional_clauses_per_sentence"])
        self.assertIsNone(features["coh_lemma_overlap_adj"])
        self.assertEqual(features["dict_hedge_per_1k"], 0.0)
        self.assertEqual(features["dict_booster_per_1k"], 0.0)
        self.assertEqual(features["dict_negation_per_1k"], 0.0)
        self.assertEqual(features["dict_conditional_per_1k"], 0.0)


class DictFeatureTests(unittest.TestCase):
    """Hand-checked fixtures from issue #18's implementer spec."""

    def test_imperative_sentences_ratio_one(self):
        features = analyze_text("Run the tests. Then commit.")
        self.assertEqual(features["dict_imperative_ratio"], 1.0)

    def test_non_imperative_sentence_ratio_zero(self):
        features = analyze_text("You should perhaps run them.")
        self.assertEqual(features["dict_imperative_ratio"], 0.0)

    def test_hedge_detected(self):
        # Issue #18's worked example says "1 hedge" for this sentence, but Hyland's (2005)
        # verbatim hedge list (see lexicons/hedges.txt header) also lists "should" as a
        # modal hedge alongside "perhaps" -- 2 matches once the sourced list is applied literally.
        features = analyze_text("You should perhaps run them.")
        self.assertEqual(features["dict_hedge_per_1k"], 1000 / 3)

    def test_negation_and_conditional_clause_detected(self):
        features = analyze_text("If it fails, do not retry.")
        self.assertEqual(features["dict_negation_per_1k"], 1000 / 8)
        self.assertEqual(features["dict_conditional_clauses_per_sentence"], 1.0)

    def test_lemma_overlap_adjacent_sentences(self):
        features = analyze_text("The cat chased the mouse. The cat bit the mouse.")
        self.assertAlmostEqual(features["coh_lemma_overlap_adj"], 0.5)

    def test_lemma_overlap_null_below_two_sentences(self):
        features = analyze_text("Only one sentence here.")
        self.assertIsNone(features["coh_lemma_overlap_adj"])

    def test_booster_detected(self):
        # "certainly" and "true" are both Hyland boosters -- 2 matches / 5 tokens.
        features = analyze_text("This is certainly true.")
        self.assertEqual(features["dict_booster_per_1k"], 1000 * 2 / 5)

    def test_conditional_connective_detected(self):
        # "because" is the one connective match / 8 tokens.
        features = analyze_text("We left early because it was raining.")
        self.assertEqual(features["dict_conditional_per_1k"], 1000 / 8)


class RunAnalyzeTests(unittest.TestCase):
    def test_missing_file_skipped_not_crashed(self):
        with TemporaryDirectory() as tmp:
            real = Path(tmp) / "real.md"
            real.write_text("Hello world. This is prose.")
            out = Path(tmp) / "out.jsonl"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = run_analyze(
                    [str(real), str(Path(tmp) / "missing.md")], out_path=str(out)
                )
            self.assertEqual(exit_code, 0)
            self.assertIn("missing.md", stderr.getvalue())
            self.assertIn("no such file", stderr.getvalue())
            lines = out.read_text().strip().splitlines()
            self.assertEqual(len(lines), 1)

    def test_all_paths_missing_exits_nonzero(self):
        with TemporaryDirectory() as tmp:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                exit_code = run_analyze([str(Path(tmp) / "missing.md")])
            self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
