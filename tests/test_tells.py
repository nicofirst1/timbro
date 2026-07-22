from __future__ import annotations

import unittest

from timbro.tells import TELL_LABEL, TELL_NAMES, TELL_PRIOR, tell_rates


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


if __name__ == "__main__":
    unittest.main()
