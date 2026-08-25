from __future__ import annotations

import contextlib
import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from timbro.cli import main
from timbro.rubrics import check_text
from timbro.rubrics.report import combine_verdicts

_CLEAN = "I fixed the parser today. It dropped the last row, so I added a guard and a test."


def _run(argv: list[str]) -> tuple[str, str, int]:
    stdout, stderr = io.StringIO(), io.StringIO()
    code = 0
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            with patch("sys.argv", ["timbro", *argv]):
                main()
        except SystemExit as exc:
            code = exc.code or 0
    return stdout.getvalue(), stderr.getvalue(), code


class BareCheckRunsAllRubricsTests(unittest.TestCase):
    def test_bare_check_runs_all_three_rubrics(self):
        with TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            draft.write_text(_CLEAN)
            out, err, code = _run(["check", str(draft), "--json"])
        self.assertEqual(err, "")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(set(payload["rubrics"]), {"schimel", "slop", "density"})


class CommaListNarrowsTests(unittest.TestCase):
    def test_comma_list_narrows_to_named_rubrics(self):
        with TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            draft.write_text(_CLEAN)
            out, err, code = _run(["check", str(draft), "--rubric", "slop,density", "--json"])
        self.assertEqual(err, "")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(set(payload["rubrics"]), {"slop", "density"})


class UnknownRubricTests(unittest.TestCase):
    def test_unknown_rubric_errors_with_available_list_and_nonzero_exit(self):
        with TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            draft.write_text(_CLEAN)
            out, err, code = _run(["check", str(draft), "--rubric", "bogus"])
        self.assertNotEqual(code, 0)
        self.assertIn("bogus", err)
        for name in ("schimel", "slop", "density"):
            self.assertIn(name, err)


class JsonShapeTests(unittest.TestCase):
    def test_json_shape_for_a_single_rubric(self):
        with TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            draft.write_text(_CLEAN)
            out, _, _ = _run(["check", str(draft), "--rubric", "slop", "--json"])
        payload = json.loads(out)
        self.assertEqual(set(payload), {"verdict", "rubrics"})
        self.assertEqual(set(payload["rubrics"]), {"slop"})
        self.assertEqual(payload["verdict"], payload["rubrics"]["slop"]["verdict"])

    def test_json_shape_for_many_rubrics(self):
        with TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            draft.write_text(_CLEAN)
            out, _, _ = _run(["check", str(draft), "--json"])
        payload = json.loads(out)
        self.assertEqual(set(payload), {"verdict", "rubrics"})
        self.assertEqual(set(payload["rubrics"]), {"schimel", "slop", "density"})
        for name, result in payload["rubrics"].items():
            self.assertEqual(result["rubric"], name)


class ExitCodeTests(unittest.TestCase):
    def test_successful_run_exits_zero_regardless_of_verdict(self):
        with TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            draft.write_text(_CLEAN)
            _, _, code = _run(["check", str(draft), "--json"])
        self.assertEqual(code, 0)

    def test_slop_command_no_longer_exists(self):
        with TemporaryDirectory() as tmp:
            draft = Path(tmp) / "draft.md"
            draft.write_text(_CLEAN)
            _, err, code = _run(["slop", str(draft)])
        self.assertNotEqual(code, 0)


class CombineVerdictsTests(unittest.TestCase):
    def test_worst_of_fail_beats_warn_beats_pass(self):
        results = check_text(_CLEAN, rubrics=["schimel", "slop", "density"])
        by_rubric = {r.rubric: r for r in results}

        class _Fake:
            def __init__(self, verdict):
                self.verdict = verdict

        self.assertEqual(combine_verdicts([_Fake("pass"), _Fake("warn"), _Fake("pass")]), "warn")
        self.assertEqual(combine_verdicts([_Fake("fail"), _Fake("warn"), _Fake("pass")]), "fail")
        self.assertEqual(combine_verdicts([_Fake("pass"), _Fake("pass")]), "pass")
        # sanity: real results still expose a valid verdict this helper can combine
        self.assertIn(combine_verdicts(list(by_rubric.values())), {"pass", "warn", "fail"})


if __name__ == "__main__":
    unittest.main()
