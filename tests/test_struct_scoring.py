"""Structure axis group (#28): z-score vs corpus + named revision direction.

Struct scoring is a SEPARATE axis group from the embedding/POS composite -- these tests
never assert on `distance`/`direction`, only on the new `struct_report` / `structure`
surface. Corpora are tiny hand-built markdown so the assertions are exact.
"""
from __future__ import annotations

import unittest

from timbro.model import STRUCT_AXIS_NAMES, STRUCT_Z_TOL, VoiceModel


# Three docs with two headings each and no code -> heading axis has variance,
# code axis is zero-variance (degenerate).
_EXEMPLARS = [
    "# One\n\ntext here.\n\n## Two\n\nmore text in this section.",
    "# Alpha\n\nsome words.\n\n## Beta\n\n### Gamma\n\ndeeper section text.",
    "# Solo\n\njust a bit.\n\n## Second\n\nanother chunk of prose to read.",
]


def _model() -> VoiceModel:
    return VoiceModel.fit(_EXEMPLARS)


class StructScoringTests(unittest.TestCase):
    def test_axes_cover_every_named_struct_axis(self):
        axes = _model().struct_report(_EXEMPLARS[0])
        self.assertEqual([a.axis for a in axes], list(STRUCT_AXIS_NAMES))

    def test_normal_variance_axis_z_and_direction(self):
        # A draft with far more headings than the corpus sits above the mean on the
        # heading axis and is told to merge headings (move back toward the mean).
        model = _model()
        draft = "# A\n## B\n### C\n#### D\n##### E\n###### F\n\nlots of headings."
        axes = {a.axis: a for a in model.struct_report(draft)}
        hc = axes["struct_heading_count"]
        self.assertGreater(hc.z, STRUCT_Z_TOL)  # clearly above corpus mean
        self.assertEqual(hc.direction, "merge section headings")

    def test_zero_variance_axis_is_finite_and_ontarget(self):
        # Every exemplar has zero code -> code axis has zero variance. A draft that also
        # has no code must get a finite z (0.0), never inf/NaN, and no direction.
        model = _model()
        axes = {a.axis: a for a in model.struct_report(_EXEMPLARS[0])}
        code = axes["struct_code_char_ratio"]
        self.assertEqual(code.z, 0.0)
        self.assertEqual(code.direction, "")
        # And nothing anywhere in the report is non-finite.
        import math

        for a in model.struct_report(_EXEMPLARS[0]):
            self.assertTrue(math.isfinite(a.z))
            self.assertTrue(math.isfinite(a.value))

    def test_draft_with_no_markdown_structure(self):
        # Plain prose, no headings/lists/code at all. Must not crash; ratio axes read 0,
        # and where the corpus HAS structure (headings) the draft is told to add it.
        model = _model()
        axes = {a.axis: a for a in model.struct_report("just a sentence of plain prose.")}
        self.assertEqual(axes["struct_heading_count"].value, 0.0)
        self.assertEqual(axes["struct_code_char_ratio"].value, 0.0)
        # corpus has headings, draft has none -> below mean -> "add section headings"
        self.assertLess(axes["struct_heading_count"].z, 0.0)
        self.assertEqual(axes["struct_heading_count"].direction, "add section headings")

    def test_no_struct_stats_yields_empty(self):
        model = _model()
        model.smean = None
        self.assertEqual(model.struct_report("# anything"), [])


if __name__ == "__main__":
    unittest.main()
