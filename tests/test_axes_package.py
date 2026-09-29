"""The `timbro.axes` package (#117): the six axis modules live under timbro/axes/,
the old top-level homes are gone (migrate-not-shim), the package __init__ is empty,
and the concreteness norms still load from the package data (now one dir up).
"""
from __future__ import annotations

import importlib
import importlib.util
import unittest

AXES = ("concreteness", "fw", "hedge", "politeness", "richness", "tells")

SINGLETONS = {
    "hedge": "HEDGE_BOOSTER_METRIC",
    "fw": "FUNCTION_WORD_METRIC",
    "concreteness": "CONCRETENESS_METRIC",
    "tells": "TELL_METRIC",
    "richness": "RICHNESS_METRIC",
    "politeness": "POLITENESS_METRIC",
}


class AxesPackageTest(unittest.TestCase):
    def test_six_axis_modules_import_and_expose_their_metric(self):
        from timbro.metric import REGISTRY

        for axis, singleton in SINGLETONS.items():
            module = importlib.import_module(f"timbro.axes.{axis}")
            metric = getattr(module, singleton)
            self.assertEqual(metric.name, axis, axis)
            self.assertIn(metric, REGISTRY, axis)

    def test_old_top_level_modules_are_gone(self):
        for axis in AXES:
            spec = importlib.util.find_spec(f"timbro.{axis}")
            self.assertIsNone(spec, f"timbro.{axis} should no longer exist")

    def test_axes_init_exports_nothing_public(self):
        import timbro.axes

        self.assertFalse(hasattr(timbro.axes, "__all__"))
        public = {n for n in vars(timbro.axes) if not n.startswith("_")}
        self.assertEqual(public, set(AXES))  # only the imported submodules themselves

    def test_concreteness_norms_load_after_the_move(self):
        from timbro.axes.concreteness import concreteness_stats

        value, spread = concreteness_stats("The hammer hit the wooden table.")
        self.assertGreater(value, 0.0)
        self.assertGreater(spread, 0.0)


if __name__ == "__main__":
    unittest.main()
