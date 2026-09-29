from __future__ import annotations

import importlib
import unittest
from unittest.mock import MagicMock, call, patch

from timbro import spacy_model

# (module, function, disable, extra_pipes) per issue #114's call-site table.
SITES = [
    ("timbro.model", "_nlp", ("ner", "lemmatizer", "parser"), ()),
    ("timbro.axes.tells", "_nlp", ("ner", "lemmatizer", "parser"), ("sentencizer",)),
    ("timbro.metric", "_nlp", ("ner", "parser"), ("sentencizer",)),
    (
        "timbro.axes.richness",
        "_nlp",
        ("ner", "parser"),
        ("sentencizer", "textdescriptives/readability"),
    ),
    ("timbro.rubrics.features", "_rubric_nlp", ("ner",), ()),
    (
        "timbro.analyze",
        "_analyze_nlp",
        ("ner",),
        (
            "textdescriptives/descriptive_stats",
            "textdescriptives/readability",
            "textdescriptives/dependency_distance",
            "textdescriptives/coherence",
        ),
    ),
]


class CachedPipelineTest(unittest.TestCase):
    def setUp(self):
        # the helper's cache is process-global; keep tests independent of call order
        helper = getattr(spacy_model, "cached_pipeline", None)
        if helper is not None and hasattr(helper, "cache_clear"):
            helper.cache_clear()
            self.addCleanup(helper.cache_clear)

    def test_cached_pipeline_exists(self):
        self.assertIsNotNone(getattr(spacy_model, "cached_pipeline", None))

    def test_same_config_returns_same_object_and_loads_once(self):
        loads = iter(range(100))

        def fake_load(**kwargs):
            return MagicMock(name=f"pipeline-{next(loads)}", disable=kwargs.get("disable"))

        with patch.object(spacy_model, "load_spacy", side_effect=fake_load) as mock_load:
            first = spacy_model.cached_pipeline(("ner", "parser"), ("sentencizer",))
            second = spacy_model.cached_pipeline(("ner", "parser"), ("sentencizer",))

        self.assertIs(first, second)
        self.assertEqual(mock_load.call_count, 1)
        # load_spacy receives the disable list, not the tuple
        self.assertEqual(mock_load.call_args.kwargs["disable"], ["ner", "parser"])

    def test_different_configs_are_distinct_objects(self):
        loads = iter(range(100))

        def fake_load(**kwargs):
            return MagicMock(name=f"pipeline-{next(loads)}", disable=kwargs.get("disable"))

        with patch.object(spacy_model, "load_spacy", side_effect=fake_load) as mock_load:
            a = spacy_model.cached_pipeline(("ner", "parser"), ())
            b = spacy_model.cached_pipeline(("ner",), ())
            c = spacy_model.cached_pipeline(("ner", "parser"), ("sentencizer",))

        self.assertIsNot(a, b)
        self.assertIsNot(a, c)
        self.assertIsNot(b, c)
        self.assertEqual(mock_load.call_count, 3)

    def test_adds_extra_pipes_in_order(self):
        pipeline = MagicMock(name="pipeline")
        with patch.object(spacy_model, "load_spacy", return_value=pipeline):
            spacy_model.cached_pipeline(
                ("ner",), ("sentencizer", "textdescriptives/readability")
            )
        self.assertEqual(
            pipeline.add_pipe.call_args_list,
            [call("sentencizer"), call("textdescriptives/readability")],
        )

    def test_no_extra_pipes_adds_none(self):
        pipeline = MagicMock(name="pipeline")
        with patch.object(spacy_model, "load_spacy", return_value=pipeline):
            spacy_model.cached_pipeline(("ner",), ())
        pipeline.add_pipe.assert_not_called()


class CallSiteDelegationTest(unittest.TestCase):
    def test_each_call_site_delegates_with_its_config(self):
        with (
            patch("timbro.spacy_model.cached_pipeline") as mock_cached,
            # RED-phase safety net: the old wrappers still call load_spacy directly;
            # keep this test from doing six real spaCy loads while it fails.
            patch("timbro.spacy_model.load_spacy", return_value=MagicMock(name="pipeline")),
        ):
            for mod_name, fn_name, disable, pipes in SITES:
                with self.subTest(site=f"{mod_name}.{fn_name}"):
                    mock_cached.reset_mock()
                    module = importlib.import_module(mod_name)
                    getattr(module, fn_name)()
                    mock_cached.assert_called_once_with(disable, pipes)


if __name__ == "__main__":
    unittest.main()
