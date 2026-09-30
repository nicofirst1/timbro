from __future__ import annotations

import unittest
from unittest.mock import MagicMock, call, patch

from timbro import text
from timbro.model import embedding

# Both loaders import SentenceTransformer lazily inside their bodies, so patching
# the source module intercepts both call sites (issue #139: local-first loads).
ST = "sentence_transformers.SentenceTransformer"
TEXT_MODEL = "all-MiniLM-L6-v2"
STYLE_MODEL = "StyleDistance/styledistance"


class LoaderTestBase(unittest.TestCase):
    def setUp(self):
        # the loaders' caches are process-global; keep tests independent of call order
        for fn in (text._model, embedding._style_model):
            fn.cache_clear()
            self.addCleanup(fn.cache_clear)


class ModelOfflineFirstTests(LoaderTestBase):
    def test_cached_path_makes_one_local_only_call(self):
        model = MagicMock(name="model")
        with patch(ST, return_value=model) as mock_st:
            result = text._model()

        self.assertIs(result, model)
        self.assertEqual(mock_st.call_count, 1)
        self.assertEqual(mock_st.call_args, call(TEXT_MODEL, local_files_only=True))

    def test_local_failure_falls_back_online(self):
        model = MagicMock(name="model")

        def fake_st(name, **kwargs):
            if kwargs.get("local_files_only"):
                raise OSError("model not in cache")
            return model

        with patch(ST, side_effect=fake_st) as mock_st:
            result = text._model()

        self.assertIs(result, model)
        self.assertEqual(mock_st.call_count, 2)
        # first attempt: local-only; second: the unchanged online call
        self.assertEqual(mock_st.call_args_list[0], call(TEXT_MODEL, local_files_only=True))
        self.assertEqual(mock_st.call_args_list[1], call(TEXT_MODEL))


class StyleModelOfflineFirstTests(LoaderTestBase):
    def test_cached_path_makes_one_local_only_call(self):
        model = MagicMock(name="model")
        with patch(ST, return_value=model) as mock_st:
            result = embedding._style_model()

        self.assertIs(result, model)
        self.assertEqual(mock_st.call_count, 1)
        self.assertEqual(mock_st.call_args, call(STYLE_MODEL, local_files_only=True))

    def test_local_failure_falls_back_online(self):
        model = MagicMock(name="model")

        def fake_st(name, **kwargs):
            if kwargs.get("local_files_only"):
                raise OSError("model not in cache")
            return model

        with patch(ST, side_effect=fake_st) as mock_st:
            result = embedding._style_model()

        self.assertIs(result, model)
        self.assertEqual(mock_st.call_count, 2)
        # first attempt: local-only; second: the unchanged online call
        self.assertEqual(mock_st.call_args_list[0], call(STYLE_MODEL, local_files_only=True))
        self.assertEqual(mock_st.call_args_list[1], call(STYLE_MODEL))


if __name__ == "__main__":
    unittest.main()
