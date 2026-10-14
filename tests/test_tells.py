from __future__ import annotations

import unittest

from timbro.axes.tells import (
    TELL_LABEL,
    TELL_NAMES,
    TELL_PRIOR,
    tell_occurrences,
    tell_rates,
)
from timbro.rubrics import check_text


class TellRegistryTest(unittest.TestCase):
    def test_label_prior_names_stay_aligned(self):
        # every label has a prior, and the feature vector covers every label
        self.assertEqual(set(TELL_LABEL), set(TELL_PRIOR))
        self.assertEqual(set(TELL_NAMES), set(TELL_LABEL))

    def test_five_new_tells_registered(self):
        for name in ("quote_punct", "colon_list", "empty_punch",
                     "dropped_subject", "staccato_run"):
            self.assertIn(name, TELL_LABEL, name)
            self.assertIn(name, TELL_PRIOR, name)
            self.assertIn(name, TELL_NAMES, name)


class QuotePunctTest(unittest.TestCase):
    def test_slop_trips(self):
        r = tell_rates('He said the plan was "at stake," and then left the room.')
        self.assertGreater(r["tell_quote_punct"], 0)

    def test_clean_zero(self):
        # logical/British: punctuation OUTSIDE the closing quote
        r = tell_rates('He said the plan was "at stake", and then left the room.')
        self.assertEqual(r["tell_quote_punct"], 0)


class ColonListTest(unittest.TestCase):
    def test_slop_trips(self):
        r = tell_rates("The build has three stages: compile, link, and run.")
        self.assertGreater(r["tell_colon_list"], 0)

    def test_single_item_clean(self):
        # a colon with one item is not the tell
        r = tell_rates("The build has one stage: compilation.")
        self.assertEqual(r["tell_colon_list"], 0)


class EmptyPunchTest(unittest.TestCase):
    def test_slop_trips(self):
        r = tell_rates("The answer is thin. We looked at it for a while.")
        self.assertGreater(r["tell_empty_punch"], 0)

    def test_clean_zero(self):
        r = tell_rates("The parser dropped a row so I added a guard and a test.")
        self.assertEqual(r["tell_empty_punch"], 0)


class DroppedSubjectTest(unittest.TestCase):
    def test_slop_trips(self):
        # bare finite verb opener, missing the subject. Note: the issue's own
        # example "Sat with this..." mis-tags as NNP (spaCy capitalization
        # artifact), so this uses a VBZ opener the tagger handles. See report.
        r = tell_rates("Sits alone with this report for hours. It was dense.")
        self.assertGreater(r["tell_dropped_subject"], 0)

    def test_imperative_clean(self):
        # base-form VB imperative is legitimate, must not flag
        r = tell_rates("Consider the following. Stop that.")
        self.assertEqual(r["tell_dropped_subject"], 0)


class StaccatoRunTest(unittest.TestCase):
    def test_slop_trips(self):
        r = tell_rates("It was an agent. It never said so. It admitted it later.")
        self.assertGreater(r["tell_staccato_run"], 0)

    def test_long_sentences_clean(self):
        r = tell_rates(
            "It was an agent that had been running quietly for a long time. "
            "It never said so to anyone who happened to be listening in. "
            "It admitted the whole thing later on when the logs were reviewed."
        )
        self.assertEqual(r["tell_staccato_run"], 0)


class SelfNarrationTest(unittest.TestCase):
    def test_slop_trips(self):
        # essay announcing its own move (#34)
        r = tell_rates("Which brings me to the second point. Here the story stops.")
        self.assertGreater(r["tell_self_narration"], 0)

    def test_clean_zero(self):
        # plain narrative prose that does not talk about itself
        r = tell_rates("The parser dropped a row so I added a guard and a test.")
        self.assertEqual(r["tell_self_narration"], 0)


class ApologeticTest(unittest.TestCase):
    def test_slop_trips(self):
        # performed-humility / self-negation frame (#37)
        r = tell_rates("What I cannot do, with this data, is tell you it is better.")
        self.assertGreater(r["tell_apologetic"], 0)

    def test_clean_zero(self):
        # a single flat statement of fact is not the tell
        r = tell_rates("The result did not hold. I moved on to the next test.")
        self.assertEqual(r["tell_apologetic"], 0)


class FencedCodeExclusionTest(unittest.TestCase):
    """#226: fenced code blocks are not prose (#16 preprocessing rule) -- no tell may
    match inside one. The exclusion lives in the occurrence scanner, so every tell
    (regex and POS-based alike) inherits it."""

    # The issue's exact repro: an otherwise clean document whose only
    # quote_punct-shaped text is a placeholder inside a fenced python block.
    REPRO = (
        "# T\n\n"
        "```python\n"
        'app.add_middleware(SessionMiddleware, secret_key="...")\n'
        "```\n"
    )

    def test_issue_repro_has_no_quote_punct(self):
        occ = tell_occurrences(self.REPRO)
        self.assertEqual(occ["quote_punct"], [])

    def test_issue_repro_passes_check_clean(self):
        # end to end through the `check` path: the slop rubric lists no quote_punct
        (result,) = check_text(self.REPRO, ["slop"])
        self.assertNotIn("quote_punct", [f.rule for f in result.findings])

    def test_same_pattern_in_prose_still_flagged(self):
        prose = 'He said the plan was "at stake," and then left the room.'
        self.assertEqual(len(tell_occurrences(prose)["quote_punct"]), 1)

    def test_prose_around_fence_fully_scanned(self):
        doc = (
            'He said the plan was "at stake," and then left the room.\n\n'
            "```python\n"
            'app.add_middleware(SessionMiddleware, secret_key="...")\n'
            "```\n\n"
            'She called the fix "done," and closed the ticket.'
        )
        # both prose hits found, the fenced placeholder ignored
        self.assertEqual(len(tell_occurrences(doc)["quote_punct"]), 2)

    def test_no_tell_family_fires_inside_fence(self):
        # every tell family, lexical and POS-based, stays silent on fence content
        fenced = (
            "```text\n"
            "Let's dive in. It's not just a tool, it's a vibrant tapestry — a testament.\n"
            'He called it "the whole point," and moved on: speed, scale, and cost.\n'
            "---\n"
            "The answer is thin. It sat alone.\n"
            "```\n"
        )
        occ = tell_occurrences(fenced)
        for name, spans in occ.items():
            self.assertEqual(spans, [], f"{name} fired inside a fence: {spans}")

    def test_tilde_fence_excluded_too(self):
        doc = '~~~python\nsecret_key="..."\n~~~\n'
        self.assertEqual(tell_occurrences(doc)["quote_punct"], [])


if __name__ == "__main__":
    unittest.main()
