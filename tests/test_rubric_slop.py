from __future__ import annotations

import unittest

from timbro.rubrics import check_text, get_rubric
from timbro.rubrics.slop.checks import DIMENSION, DIMENSIONS, tell_findings
from timbro.tells import TELL_NAMES, tell_baseline

# Lights up tells across all four dimensions; a clean sentence lights up none.
_SLOP = (
    "Honestly? Let's dive in. It's not just a tool, it's a vibrant tapestry. "
    "We delve into the landscape — a testament to seamless, robust design. \U0001F680\n\n"
    "The answer is thin. It has three parts: speed, scale, and cost. "
    'He called it "the whole point," and moved on.\n'
    "- **Key:** in conclusion, the future looks bright. Great question!"
)
_CLEAN = "I fixed the parser today. It dropped the last row, so I added a guard and a test."


class SlopRubricTest(unittest.TestCase):
    def test_registered(self):
        self.assertEqual(get_rubric("slop").name, "slop")
        self.assertEqual(check_text(_SLOP, rubric="slop").rubric, "slop")

    def test_every_tell_has_a_dimension(self):
        self.assertEqual(set(DIMENSION), set(TELL_NAMES))
        self.assertEqual(set(DIMENSION.values()), set(DIMENSIONS))

    def test_slop_fails_clean_passes(self):
        slop = check_text(_SLOP, rubric="slop")
        clean = check_text(_CLEAN, rubric="slop")
        self.assertIn(slop.verdict, ("warn", "fail"))
        self.assertEqual(clean.verdict, "pass")
        self.assertEqual(clean.findings, [])

    def test_one_finding_per_tell_with_count_in_message(self):
        findings = tell_findings(_SLOP)
        rules = [f.rule for f in findings]
        self.assertEqual(len(rules), len(set(rules)), "a tell should surface at most once")
        # the diction tell fires several times; the count must ride in the message
        diction = next(f for f in findings if f.rule == "diction")
        self.assertRegex(diction.message, r"^\d+×")
        self.assertTrue(diction.span, "finding should quote an example span")


class RelativeSlopTest(unittest.TestCase):
    # A corpus whose voice legitimately runs em-dashes at a steady, varied rate.
    _CORPUS = [
        "The plan was simple — we shipped it fast. It held up well enough for a first week.",
        "We kept the design small on purpose — nobody wanted another sprawling framework.",
        "Testing came first — always — and the habit paid off when the big refactor landed.",
    ]

    def test_normal_usage_not_flagged(self):
        baseline = tell_baseline(self._CORPUS)
        # one em-dash in a normal-length sentence: within this voice's norm
        draft = "We built the thing over a week — then tested it thoroughly before releasing it widely."
        dash = [f for f in tell_findings(draft, baseline) if f.rule == "dash"]
        self.assertEqual(dash, [], "an on-norm em-dash should not flag in relative mode")

    def test_overuse_flagged(self):
        baseline = tell_baseline(self._CORPUS)
        draft = "We built it — tested it — shipped it — fixed it — praised it — and then — finally — rested."
        dash = [f for f in tell_findings(draft, baseline) if f.rule == "dash"]
        self.assertEqual(len(dash), 1)
        self.assertIn("your corpus norm", dash[0].message)

    def test_absolute_mode_would_flag_the_same_on_norm_draft(self):
        # contrast: without a baseline, the single on-norm em-dash IS slop
        draft = "We built the thing over a week — then tested it thoroughly before releasing it widely."
        dash = [f for f in tell_findings(draft) if f.rule == "dash"]
        self.assertEqual(len(dash), 1)

    def test_empty_corpus_rejected(self):
        with self.assertRaises(ValueError):
            tell_baseline([])

    def test_profile_only_valid_for_slop(self):
        with self.assertRaises(ValueError):
            check_text(_CLEAN, rubric="schimel", profile="anything")


if __name__ == "__main__":
    unittest.main()
