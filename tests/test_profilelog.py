from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from timbro.profiles import init_profile, learn
from timbro.profilelog import log_learn

FINAL_TEXT = (
    "The committee reviewed the annual budget with care. Members raised concerns about "
    "research funding and asked for a revised proposal. After careful deliberation, the "
    "board approved the plan and scheduled a follow-up meeting for next quarter. Staff "
    "will circulate the finalized figures before the next session begins."
)

DRAFT_TEXT = (
    "The committee reviewed the annual budget. Members raised concerns about research "
    "funding and asked for a revised proposal. After a lot of back and forth, the board "
    "agreed to the plan and scheduled a follow-up meeting for next quarter. Staff will "
    "send out the finalized figures before the next session begins."
)


def _seed(root: Path, name: str = "demo") -> None:
    init_profile(name, root=root)
    exemplars_dir = root / name / "exemplars"
    for i in range(3):
        (exemplars_dir / f"seed{i}.md").write_text(FINAL_TEXT, encoding="utf-8")


def _read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class LearnLoggingTests(unittest.TestCase):
    def test_saved_pair_logs_one_line_with_full_record(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            _seed(root)
            draft_path = Path(td) / "draft.md"
            final_path = Path(td) / "final.md"
            draft_path.write_text(DRAFT_TEXT, encoding="utf-8")
            final_path.write_text(FINAL_TEXT, encoding="utf-8")

            learn("demo", draft_path, final_path, title="budget-memo", root=root)

            log_path = root / "demo" / "runs.jsonl"
            self.assertTrue(log_path.exists())
            lines = _read_lines(log_path)
            self.assertEqual(len(lines), 1)
            record = lines[0]
            self.assertEqual(
                set(record.keys()), {"ts", "profile", "title", "outcome", "guard", "draft", "final"}
            )
            self.assertEqual(record["outcome"], "saved")
            self.assertIn("flow", record["draft"])
            self.assertTrue(record["draft"]["markdown"])

    def test_two_learn_calls_append_two_lines(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            _seed(root)
            draft_path = Path(td) / "draft.md"
            final_path = Path(td) / "final.md"
            draft_path.write_text(DRAFT_TEXT, encoding="utf-8")
            final_path.write_text(FINAL_TEXT, encoding="utf-8")

            learn("demo", draft_path, final_path, title="pair-one", root=root)
            learn("demo", draft_path, final_path, title="pair-two", root=root)

            log_path = root / "demo" / "runs.jsonl"
            self.assertEqual(len(_read_lines(log_path)), 2)

    def test_refused_pair_logs_refused_outcome(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            _seed(root)
            draft_path = Path(td) / "draft.md"
            final_path = Path(td) / "final.md"
            draft_path.write_text(FINAL_TEXT, encoding="utf-8")
            final_path.write_text(FINAL_TEXT, encoding="utf-8")

            learn("demo", draft_path, final_path, title="identical", root=root)

            log_path = root / "demo" / "runs.jsonl"
            lines = _read_lines(log_path)
            self.assertEqual(len(lines), 1)
            self.assertEqual(lines[0]["outcome"], "refused")

    def test_no_log_env_var_disables_logging(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            _seed(root)
            draft_path = Path(td) / "draft.md"
            final_path = Path(td) / "final.md"
            draft_path.write_text(DRAFT_TEXT, encoding="utf-8")
            final_path.write_text(FINAL_TEXT, encoding="utf-8")

            with patch.dict(os.environ, {"TIMBRO_NO_LOG": "1"}, clear=False):
                learn("demo", draft_path, final_path, title="budget-memo", root=root)

            log_path = root / "demo" / "runs.jsonl"
            self.assertFalse(log_path.exists())

    def test_logging_failure_is_swallowed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "profiles"
            profile = init_profile("demo", root=root)

            class ExplodingModel:
                pass

            result = log_learn(
                profile,
                ExplodingModel(),
                "draft text",
                "final text",
                title="t",
                outcome="saved",
                guard={},
            )
            self.assertIsNone(result)
            self.assertFalse((profile.path / "runs.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
