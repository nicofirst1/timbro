from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from timbro.analyze import _hype_entries, _lexicon, analyze_text, run_analyze

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
        features = analyze_text(fixture)
        frontmatter = json.loads(features["frontmatter_json"])
        self.assertEqual(frontmatter["created"], "2025-03-01")
        self.assertEqual(frontmatter["updated"], "2025-03-01 12:00:00")

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


class PlainLanguageFeatureTests(unittest.TestCase):
    """Hand-checked fixtures for issue #22's exploratory plain-language features."""

    def test_second_person_per_1k(self):
        # "You take your time." -> 5 non-space tokens (You take your time .);
        # forms {you, your} match -> 2 / 5 * 1000.
        features = analyze_text("You take your time.")
        self.assertEqual(features["dict_second_person_per_1k"], 2 / 5 * 1000)

    def test_long_sentence_ratio(self):
        # One 26-word sentence (> 25 tokens) + one 2-word sentence -> 1 of 2 sentences long.
        long_sent = (
            "The quick brown fox jumps over the lazy dog and then runs across the "
            "wide green field before it finally stops to rest near the river."
        )
        features = analyze_text(long_sent + " It rained.")
        self.assertEqual(features["read_long_sentence_ratio"], 0.5)

    def test_cross_reference_per_1k(self):
        # "See also" is one cross-reference phrase; 6 non-space tokens (See also the other file .).
        features = analyze_text("See also the other file.")
        self.assertEqual(features["dict_cross_reference_per_1k"], 1000 / 6)

    def test_plain_replacement_detected_and_annotated(self):
        # "utilize" is the one complex-word match; 5 non-space tokens (We utilize the tool .).
        features = analyze_text("We utilize the tool.")
        self.assertEqual(features["dict_plain_replacement_per_1k"], 1000 / 5)
        pairs = json.loads(features["dict_plain_replacements_json"])
        self.assertIn(["utilize", "use"], pairs)

    def test_long_paragraph_ratio(self):
        # Para 1 has 7 sentence terminators (> 6); para 2 has 1. -> 1 of 2 paragraphs long.
        text = "A. B. C. D. E. F. G.\n\nOnly one sentence."
        features = analyze_text(text)
        self.assertEqual(features["struct_long_paragraph_ratio"], 0.5)

    def test_long_paragraph_ignores_code_fence(self):
        # A fenced block full of periods must not count as a long prose paragraph.
        text = "```\na. b. c. d. e. f. g. h.\n```\n\nJust one.\n"
        features = analyze_text(text)
        self.assertEqual(features["struct_long_paragraph_ratio"], 0.0)

    def test_hype_detected_distinct_from_boosters(self):
        # "exceptional" is hype, "certainly" is a booster; 5 tokens (This is certainly exceptional .).
        # Each lexicon counts only its own token -> no double-counting.
        features = analyze_text("This is certainly exceptional.")
        self.assertEqual(features["dict_hype_per_1k"], 1000 / 5)
        self.assertEqual(features["dict_booster_per_1k"], 1000 / 5)

    def test_hype_matches_participial_and_hyphenated(self):
        # Regression: form-matching must catch "groundbreaking" (lemma is mangled to
        # "groundbreake") and "world-class" (spaCy splits it into world - class).
        # Tokens: A world - class , groundbreaking result . = 8 non-space tokens; 2 hype hits.
        features = analyze_text("A world-class, groundbreaking result.")
        self.assertEqual(features["dict_hype_per_1k"], 2 / 8 * 1000)

    def test_hype_and_boosters_lexicons_disjoint(self):
        # Gap #1's "explicitly distinct from boosters.txt": no shared word between the lists.
        hype_words = {w for entry in _hype_entries() for w in entry if w != "-"}
        booster_words = {w for entry in _lexicon("boosters.txt") for w in entry}
        self.assertTrue(hype_words.isdisjoint(booster_words))

    def test_empty_file_new_features_zero(self):
        # Issue #22 contract: empty file -> every new feature is 0/0.0, never None, never crash.
        f = analyze_text("")
        self.assertEqual(f["dict_hype_per_1k"], 0.0)
        self.assertEqual(f["dict_second_person_per_1k"], 0.0)
        self.assertEqual(f["dict_cross_reference_per_1k"], 0.0)
        self.assertEqual(f["dict_plain_replacement_per_1k"], 0.0)
        self.assertEqual(f["dict_plain_replacements_json"], "[]")
        self.assertEqual(f["read_long_sentence_ratio"], 0.0)
        self.assertEqual(f["struct_long_paragraph_ratio"], 0.0)


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
