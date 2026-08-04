from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_MODULE_PATH = Path(__file__).parents[1] / "eval" / "slop_benchmark.py"
_spec = importlib.util.spec_from_file_location("slop_benchmark", _MODULE_PATH)
slop_benchmark = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(slop_benchmark)


class SlopBenchmarkCorpusTest(unittest.TestCase):
    """Corpus layout: HC3 subsample under eval/slop_bench/hc3/{human,llm}, held out
    from the rule-tuning sample (src/timbro/sample/exemplars)."""

    def test_human_and_llm_dirs_exist_and_are_disjoint_from_tuning_corpus(self):
        human_dir = slop_benchmark.HUMAN_DIR
        llm_dir = slop_benchmark.LLM_DIR
        self.assertTrue(human_dir.is_dir())
        self.assertTrue(llm_dir.is_dir())

        from timbro.model import DEFAULT_EXEMPLARS

        tuning_files = {f.name for f in Path(DEFAULT_EXEMPLARS).glob("*.md")}
        human_files = {f.name for f in human_dir.glob("*.md")}
        self.assertTrue(human_files, "HC3 human corpus must not be empty")
        self.assertEqual(
            human_files & tuning_files,
            set(),
            "benchmark human corpus must not reuse rule-tuning sample filenames",
        )
        self.assertNotEqual(str(human_dir.resolve()), str(Path(DEFAULT_EXEMPLARS).resolve()))

    def test_corpus_read_by_shared_read_corpus(self):
        from timbro.model import read_corpus

        human_docs = read_corpus(slop_benchmark.HUMAN_DIR)
        llm_docs = read_corpus(slop_benchmark.LLM_DIR)
        self.assertGreater(len(human_docs), 0)
        self.assertGreater(len(llm_docs), 0)


class FlagRateTest(unittest.TestCase):
    def test_flag_rate_counts_paragraphs_with_findings(self):
        flagged, total = slop_benchmark.flag_rate(["clean text with no tells at all here"])
        self.assertEqual(total, 1)
        self.assertIn(flagged, (0, 1))

    def test_flag_rate_empty_list(self):
        flagged, total = slop_benchmark.flag_rate([])
        self.assertEqual((flagged, total), (0, 0))


class MainOutputTest(unittest.TestCase):
    def test_main_json_reports_rates_in_unit_interval(self):
        import io
        import json
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = slop_benchmark.main(["--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(buf.getvalue())
        self.assertIn("hit_rate", payload)
        self.assertIn("false_positive_rate", payload)
        self.assertGreaterEqual(payload["hit_rate"], 0.0)
        self.assertLessEqual(payload["hit_rate"], 1.0)
        self.assertGreaterEqual(payload["false_positive_rate"], 0.0)
        self.assertLessEqual(payload["false_positive_rate"], 1.0)
        self.assertGreater(payload["llm_paragraphs"], 0)
        self.assertGreater(payload["human_paragraphs"], 0)


if __name__ == "__main__":
    unittest.main()
