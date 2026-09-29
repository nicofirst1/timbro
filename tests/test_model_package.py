"""`timbro/model/` is a package (#106): the two lenses get their own modules
(embedding = "how far", direction = "which way"), the orchestrator stays on
__init__, the markdown metric moves to `timbro/axes/markdown.py`, and the
generic stats primitives `_knn`/`_confidence` move to `timbro.metric`.
"""
from __future__ import annotations

import subprocess
import sys
import unittest


class ModelPackageTest(unittest.TestCase):
    def test_model_is_a_package(self):
        import timbro.model

        self.assertTrue(hasattr(timbro.model, "__path__"), "timbro.model must be a package")

    def test_embedding_module_exposes_the_how_far_lens(self):
        from timbro.model import embedding

        for name in ("_style_vec", "_style_model", "_loo_exemplar_distances", "fit_embedding"):
            self.assertTrue(callable(getattr(embedding, name)), f"embedding.{name}")

    def test_direction_module_exposes_the_which_way_lens(self):
        from timbro.model import direction

        for name in ("POS_TAGS", "features", "feature_matrix", "_pos_rates", "_nlp"):
            self.assertTrue(hasattr(direction, name), f"direction.{name}")

    def test_markdown_metric_lives_in_axes(self):
        from timbro.axes import markdown
        from timbro.metric import REGISTRY

        self.assertEqual(markdown.MARKDOWN_METRIC.name, "markdown")
        self.assertIn(markdown.MARKDOWN_METRIC, REGISTRY)
        self.assertEqual(markdown.STRUCT_AXIS_NAMES, markdown.MARKDOWN_METRIC.axes)

    def test_metric_has_the_shared_stats_primitives(self):
        from timbro import metric

        for name in ("_knn", "_confidence"):
            self.assertTrue(callable(getattr(metric, name)), f"metric.{name}")

    def test_voice_model_keeps_pos_dist(self):
        from timbro.model import VoiceModel

        self.assertTrue(callable(VoiceModel._pos_dist))

    def test_python_m_timbro_model_smoke_test(self):
        r = subprocess.run(
            [sys.executable, "-m", "timbro.model"],
            capture_output=True, text=True, timeout=600, check=False,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("ok:"), r.stdout)


if __name__ == "__main__":
    unittest.main()
