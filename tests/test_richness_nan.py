"""A punctuation-only corpus file must not poison the richness axis with NaN (#177).

textdescriptives returns NaN (0/0) for a doc with no words, and the extractor's
`... or 0.0` never fired because NaN is truthy. One signature line, separator
row, or detexed LaTeX fragment in a profile's exemplars therefore made the
readability axis NaN for every draft scored against that profile: `VoiceModel.fit`
averaged the NaN into the corpus reference, and `timbro score --json` printed a
literal NaN (invalid JSON for strict parsers). The extractor must fall back to
0.0 for any missing or non-finite index.
"""
from __future__ import annotations

import math
import unittest

from timbro.axes.richness import richness_stats
from timbro.model import VoiceModel

# 50 punctuation chars: the issue's minimal repro (a signature/separator line).
_PUNCT = "!" * 50

# >42 content-word tokens: lexical_diversity's hdd() samples a fixed 42-token
# window (see test_richness.py).
_NORMAL = ("Epistemological frameworks underpinning contemporary jurisprudence "
           "necessitate a multifaceted reconsideration of adjudicative precedent, "
           "particularly where constitutional ambiguity intersects procedural "
           "heterodoxy across divergent federalist jurisdictions. Subsequent "
           "scholarship interrogates these entrenched assumptions, proposing "
           "alternative taxonomies that destabilize orthodox categorization "
           "while foregrounding marginalized interpretive traditions. Critics "
           "counter that such revisionism, however illuminating, risks eroding "
           "the doctrinal coherence upon which adjudicative legitimacy depends.")

_DRAFT = "We shipped it. The bug was a stale cache. The fix landed on Tuesday."


class PunctuationOnlyExtractorTest(unittest.TestCase):
    def test_punctuation_only_text_returns_finite_stats(self):
        stats = richness_stats(_PUNCT)
        for value in stats:
            self.assertTrue(math.isfinite(value), f"non-finite in {stats}")


class PunctuationOnlyCorpusTest(unittest.TestCase):
    def test_punctuation_only_exemplar_keeps_reference_and_z_finite(self):
        model = VoiceModel.fit([_PUNCT, _NORMAL])
        axes = {a.axis: a for a in model.richness_report(_DRAFT)}
        for axis, report in axes.items():
            self.assertTrue(math.isfinite(report.reference_mean), f"{axis}: {report}")
            self.assertTrue(math.isfinite(report.z), f"{axis}: {report}")


if __name__ == "__main__":
    unittest.main()
