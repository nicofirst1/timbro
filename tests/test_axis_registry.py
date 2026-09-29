"""Axis registry (#108): one _axis_stats dict, one axis_report method, hint_axes/z_tol
on each Metric, one AxisReport dataclass. The zero-growth proof is the last test: a
sixth blend-style metric registered from the test file reports with zero model.py
changes (and is removed from REGISTRY again via addCleanup).
"""
from __future__ import annotations

import math
import unittest

import numpy as np

import timbro
import timbro.report as report_module
from timbro.axes.concreteness import CONCRETENESS_METRIC
from timbro.axes.fw import FUNCTION_WORD_METRIC
from timbro.axes.hedge import HEDGE_BOOSTER_METRIC
from timbro.axes.richness import RICHNESS_METRIC
from timbro.metric import REGISTRY, Reference
from timbro.model import VoiceModel
from timbro.report import AxisReport

# _MarkdownMetric lives in model.py; import via the registered singleton's class.
from timbro.model import MARKDOWN_METRIC

METRICS = [MARKDOWN_METRIC, HEDGE_BOOSTER_METRIC, FUNCTION_WORD_METRIC, CONCRETENESS_METRIC, RICHNESS_METRIC]

_CORPUS = [
    "I think this might work, though it could possibly fail. It seems fine.",
    "This clearly works. It is obviously correct and must succeed. Of course.",
    "The cat sat by the door. It was small and grey outside today.",
]

# Zero-variance: every doc identical -> raw std 0 on every axis of every metric.
_ZV_DOC = "# Same\n\nThe cat sat by the door. It was small and grey.\n\n```python\nx = 1\n```\n"


def _bare_model() -> VoiceModel:
    """A VoiceModel built without corpus stats (axis_stats=None), like a --check call."""
    return VoiceModel(
        ["pos_NOUN"], np.array([1.0]), np.array([1.0]), np.zeros((1, 1)), np.array([1.0]),
        np.zeros(1), np.ones(1), np.zeros((1, 1)), 6, 1, 1, 0, 3000, 4, "ok", None, 1.0, 0.5, None,
    )


class AxisReportTest(unittest.TestCase):
    def test_fields(self):
        self.assertEqual(
            [f for f in AxisReport.__dataclass_fields__],
            ["axis", "value", "reference_mean", "z", "direction"],
        )

    def test_to_dict_has_reference_mean_not_corpus_mean(self):
        d = AxisReport("a", 1.0, 2.0, 3.0, "up").to_dict()
        self.assertIn("reference_mean", d)
        self.assertNotIn("corpus_mean", d)

    def test_top_level_export(self):
        self.assertIs(timbro.AxisReport, AxisReport)
        self.assertFalse(hasattr(timbro, "MarkdownAxis"))


class MetricSelfDescriptionTest(unittest.TestCase):
    def test_every_metric_carries_hint_axes_and_z_tol(self):
        for m in METRICS:
            self.assertTrue(hasattr(m, "hint_axes"), m.name)
            self.assertEqual(m.z_tol, 0.5, m.name)
            self.assertEqual(m.axes, tuple(a for a, _, _ in m.hint_axes), m.name)
            for triple in m.hint_axes:
                self.assertEqual(len(triple), 3, m.name)

    def test_report_module_no_longer_defines_axis_tables(self):
        for name in (
            "MARKDOWN_AXES", "HEDGE_AXES", "FW_AXES", "CONCRETENESS_AXES", "RICHNESS_AXES",
            "MARKDOWN_Z_TOL", "HEDGE_Z_TOL", "FW_Z_TOL", "CONCRETENESS_Z_TOL", "RICHNESS_Z_TOL",
            "MarkdownAxis", "HedgeAxis", "FwAxis", "ConcretenessAxis", "RichnessAxis",
        ):
            self.assertFalse(hasattr(report_module, name), name)


class AxisStatsTest(unittest.TestCase):
    def test_fit_stores_one_dict_keyed_by_metric_name(self):
        model = VoiceModel.fit(_CORPUS)
        self.assertEqual(
            set(model._axis_stats),
            {"markdown", "hedge", "fw", "concreteness", "richness"},
        )
        for mean, std, n in model._axis_stats.values():
            self.assertEqual(n, len(_CORPUS))
            self.assertEqual(len(mean), len(std))
            self.assertTrue(all(math.isfinite(x) for x in mean))
            self.assertTrue(all(math.isfinite(x) for x in std))

    def test_fit_raw_std_no_zero_guard(self):
        # The zero-std->1 guard lives in the report (spread or 1.0), not at fit time.
        model = VoiceModel.fit([_ZV_DOC] * 3)
        for mean, std, _n in model._axis_stats.values():
            self.assertTrue(any(s == 0.0 for s in std))

    def test_old_per_axis_attributes_gone(self):
        model = VoiceModel.fit(_CORPUS)
        for attr in (
            "smean", "sstd", "hmean", "hstd", "hn",
            "fmean", "fstd", "fn", "cmean", "cstd", "cn",
            "rmean", "rstd", "rn",
        ):
            self.assertFalse(hasattr(model, attr), attr)


class AxisReportMethodTest(unittest.TestCase):
    def test_equals_wrappers_for_all_five(self):
        model = VoiceModel.fit(_CORPUS)
        text = "I think this might work. # Heading\n\n```python\ncode = 1\n```"
        for name in ("markdown", "hedge", "fw", "concreteness", "richness"):
            self.assertEqual(model.axis_report(name, text), getattr(model, f"{name}_report")(text), name)

    def test_unknown_name_raises_key_error(self):
        model = VoiceModel.fit(_CORPUS)
        with self.assertRaises(KeyError):
            model.axis_report("no-such-axis", "text")

    def test_non_blend_registered_metric_raises_key_error(self):
        # tells/politeness are registered but not blend-style (no hint_axes); axis_report
        # must reject them like unknown names, not return [] (round-2 fix list, F2).
        model = VoiceModel.fit(_CORPUS)
        with self.assertRaises(KeyError):
            model.axis_report("tells", "text")
        with self.assertRaises(KeyError):
            model.axis_report("politeness", "text")

    def test_no_stats_strength_zero_returns_empty(self):
        model = VoiceModel.fit(_CORPUS)
        del model._axis_stats["markdown"]  # owner decision 1: the old `model.smean = None`
        self.assertEqual(model.axis_report("markdown", "# anything"), [])

    def test_no_stats_positive_strength_uses_prior(self):
        model = _bare_model()  # axis_stats=None: nothing fitted
        rows = model.axis_report("hedge", "It might work.")
        self.assertEqual([r.axis for r in rows], list(HEDGE_BOOSTER_METRIC.axes))
        self.assertAlmostEqual(rows[0].reference_mean, HEDGE_BOOSTER_METRIC.prior.mean[0])
        self.assertAlmostEqual(rows[1].reference_mean, HEDGE_BOOSTER_METRIC.prior.mean[1])


class ZeroVarianceTest(unittest.TestCase):
    def test_markdown_z_finite_on_degenerate_corpus(self):
        model = VoiceModel.fit([_ZV_DOC] * 3)
        for row in model.axis_report("markdown", _ZV_DOC):
            self.assertTrue(math.isfinite(row.z), row.axis)


class ZeroGrowthProofTest(unittest.TestCase):
    def test_sixth_metric_needs_zero_model_changes(self):
        class _ThrowawayMetric:
            name = "throwaway"
            axes = ("vibe_rate",)
            hint_axes = (("vibe_rate", "add vibes", "reduce vibes"),)
            z_tol = 0.5
            prior = Reference(mean=(1.0,), spread=(1.0,), strength=2.0)

            def extract(self, text: str) -> tuple[float, ...]:
                return (len(text.split()) / 10.0,)

        metric = _ThrowawayMetric()
        REGISTRY.append(metric)
        self.addCleanup(REGISTRY.remove, metric)

        model = VoiceModel.fit(_CORPUS)  # untouched model.py must pick the metric up
        self.assertIn("throwaway", model._axis_stats)
        rows = model.axis_report("throwaway", "some words here")
        self.assertEqual([r.axis for r in rows], ["vibe_rate"])
        self.assertTrue(all(isinstance(r, AxisReport) for r in rows))
        # direction label comes from the metric's own hint_axes
        self.assertIn(rows[0].direction, ("", "add vibes", "reduce vibes"))


if __name__ == "__main__":
    unittest.main()
