"""Verdicts become exit codes (issue #142): a FAIL `check` and a rejected
`accept` exit 3; WARN/PASS checks and accepted rewrites keep exit 0. Printed
output is unchanged in both commands.

The stdout pins below are byte-identical to the pre-change output, with
PYTHONHASHSEED=0. The subprocess style follows tests/test_cli_user_errors.py;
every run is sandboxed under tmp dirs (TIMBRO_HOME, TIMBRO_PROFILE_ROOT,
XDG_DATA_HOME), never the real ~/.timbro. The accept pins were re-captured
after merging origin/dev: #163 replaced the packaged sample corpus, which the
style distances are measured against, so they moved while every gate field
(verdict, similarity, exit code) stayed the same.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# The FAIL fixture from tests/test_cli_check.py ExitCodeTests: verdict FAIL
# (schimel fails it) under the full rubric set.
_FAIL_DRAFT = (
    "Let's delve into the seamless tapestry of robust solutions — "
    "it's not just a tool, it's a paradigm. In conclusion, the future is bright."
)
# WARN under `--rubric slop` (overall 0.675, no full-fail).
_WARN_DRAFT = (
    "Honestly, great question — let's delve into it. It's not just a tool, it's a paradigm. "
    "In order to succeed, we must leverage the tapestry. The answer is thin. We ship. It works. "
    "In conclusion, the future looks bright. Hope this helps. "
)
# PASS under `--rubric slop,density`, and the original of both accept pairs.
_PASS_DRAFT = "I fixed the parser today. It dropped the last row, so I added a guard and a test."
# Closer to the packaged sample voice + meaning kept: accepted.
_REVISED_OK = (
    "This morning I fixed the parser. It had dropped the last row, so I added a guard and a test."
)
# Semantically unrelated: content gate rejects it.
_REVISED_BAD = "A cat slept on the warm windowsill all afternoon while it rained outside."

# Byte-identical pre-change stdout (base 9428ef6, PYTHONHASHSEED=0).
_CHECK_FAIL_TEXT_OUT = 'verdict: FAIL\n\nschimel: FAIL (0.84)\n\nopening      0.75\nchallenge    0.75\nresolution   0.75\nflow         1.00\nparagraphs   1.00\nsentences    0.80\nclarity      0.90\n\nTop findings\n- P1: opening_problem_present; Opening does not clearly frame an important problem.\n- challenge: challenge_present; No concrete challenge paragraph was detected.\n- P1: challenge_answered; Resolution does not appear to answer the challenge.\n- sentences: nominalization_density; Uses heavy nominalization density that can flatten action.\n- P1: comma_splice; A comma joins two independent clauses (run-on); use a period, a semicolon, or a conjunction.\n\nslop: PASS (0.79)\n\ndiction      0.75\nconstruction 0.65\nrhythm       1.00\nformatting   0.75\n\nTop findings\n- formatting: dash; 1× em/en dashes — a deterministic AI-writing tell; cut or vary it.\n- diction: diction; 4× AI-tell diction (delve, tapestry, leverage, …) — a deterministic AI-writing tell; cut or vary it.\n- construction: not_x_y; 1× "it\'s not X, it\'s Y" / "not only … but also" constructions — a deterministic AI-writing tell; cut or vary it.\n- construction: conclusion; 1× wrap-up phrases (in conclusion, the future looks bright) — a deterministic AI-writing tell; cut or vary it.\n\ndensity: PASS (1.00)\n\ndensity      1.00\njargon       1.00\n'
_CHECK_FAIL_JSON_OUT = '{\n  "verdict": "fail",\n  "rubrics": {\n    "schimel": {\n      "rubric": "schimel",\n      "version": "v3",\n      "overall": 0.845,\n      "verdict": "fail",\n      "dimensions": {\n        "opening": 0.75,\n        "challenge": 0.75,\n        "resolution": 0.75,\n        "flow": 1.0,\n        "paragraphs": 1.0,\n        "sentences": 0.8,\n        "clarity": 0.9\n      },\n      "sections": {\n        "opening_paragraphs": [\n          0\n        ],\n        "challenge_paragraph": null,\n        "resolution_paragraphs": [\n          0\n        ],\n        "body_paragraphs": []\n      },\n      "findings": [\n        {\n          "severity": "high",\n          "dimension": "opening",\n          "rule": "opening_problem_present",\n          "paragraph": 1,\n          "sentence": null,\n          "span": "Let\'s delve into the seamless tapestry of robust solutions \\u2014 it\'s not just a tool, it\'s a paradigm. In conclusion, the future is bright.",\n          "message": "Opening does not clearly frame an important problem."\n        },\n        {\n          "severity": "high",\n          "dimension": "challenge",\n          "rule": "challenge_present",\n          "paragraph": null,\n          "sentence": null,\n          "span": "",\n          "message": "No concrete challenge paragraph was detected."\n        },\n        {\n          "severity": "high",\n          "dimension": "resolution",\n          "rule": "challenge_answered",\n          "paragraph": 1,\n          "sentence": null,\n          "span": "Let\'s delve into the seamless tapestry of robust solutions \\u2014 it\'s not just a tool, it\'s a paradigm. In conclusion, the future is bright.",\n          "message": "Resolution does not appear to answer the challenge."\n        },\n        {\n          "severity": "medium",\n          "dimension": "sentences",\n          "rule": "nominalization_density",\n          "paragraph": null,\n          "sentence": null,\n          "span": "",\n          "message": "Uses heavy nominalization density that can flatten action."\n        },\n        {\n          "severity": "medium",\n          "dimension": "sentences",\n          "rule": "comma_splice",\n          "paragraph": 1,\n          "sentence": 1,\n          "span": "Let\'s delve into the seamless tapestry of robust solutions \\u2014 it\'s not just a tool, it\'s a paradigm.",\n          "message": "A comma joins two independent clauses (run-on); use a period, a semicolon, or a conjunction."\n        },\n        {\n          "severity": "medium",\n          "dimension": "clarity",\n          "rule": "defensive_claim",\n          "paragraph": 1,\n          "sentence": 1,\n          "span": "Let\'s delve into the seamless tapestry of robust solutions \\u2014 it\'s not just a tool, it\'s a paradigm.",\n          "message": "First-person sentence framed around a negation (\'we do not\\u2026\', \'we make no\\u2026\', \'we lack\\u2026\'); state what the work does, positively, instead of pre-emptively conceding."\n        }\n      ]\n    },\n    "slop": {\n      "rubric": "slop",\n      "version": "v1",\n      "overall": 0.787,\n      "verdict": "pass",\n      "dimensions": {\n        "diction": 0.75,\n        "construction": 0.65,\n        "rhythm": 1.0,\n        "formatting": 0.75\n      },\n      "sections": {},\n      "findings": [\n        {\n          "severity": "high",\n          "dimension": "formatting",\n          "rule": "dash",\n          "paragraph": null,\n          "sentence": null,\n          "span": "\\u2014",\n          "message": "1\\u00d7 em/en dashes \\u2014 a deterministic AI-writing tell; cut or vary it."\n        },\n        {\n          "severity": "high",\n          "dimension": "diction",\n          "rule": "diction",\n          "paragraph": null,\n          "sentence": null,\n          "span": "delve",\n          "message": "4\\u00d7 AI-tell diction (delve, tapestry, leverage, \\u2026) \\u2014 a deterministic AI-writing tell; cut or vary it."\n        },\n        {\n          "severity": "high",\n          "dimension": "construction",\n          "rule": "not_x_y",\n          "paragraph": null,\n          "sentence": null,\n          "span": "it\'s not just a tool, it\'s",\n          "message": "1\\u00d7 \\"it\'s not X, it\'s Y\\" / \\"not only \\u2026 but also\\" constructions \\u2014 a deterministic AI-writing tell; cut or vary it."\n        },\n        {\n          "severity": "medium",\n          "dimension": "construction",\n          "rule": "conclusion",\n          "paragraph": null,\n          "sentence": null,\n          "span": "In conclusion",\n          "message": "1\\u00d7 wrap-up phrases (in conclusion, the future looks bright) \\u2014 a deterministic AI-writing tell; cut or vary it."\n        }\n      ]\n    },\n    "density": {\n      "rubric": "density",\n      "version": "v1",\n      "overall": 1.0,\n      "verdict": "pass",\n      "dimensions": {\n        "density": 1.0,\n        "jargon": 1.0\n      },\n      "sections": {\n        "opening_paragraphs": [\n          0\n        ],\n        "challenge_paragraph": null,\n        "resolution_paragraphs": [\n          0\n        ],\n        "body_paragraphs": []\n      },\n      "findings": []\n    }\n  }\n}\n'
_ACCEPT_REJECT_TEXT_OUT = 'rejected: distance 56.8 -> 155.7 (improved=False), content similarity 0.031 (content_ok=False)\n'


def _run_cli(argv: list[str]) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory() as tmp:
        fail = Path(tmp) / "fail.md"
        fail.write_text(_FAIL_DRAFT, encoding="utf-8")
        warn = Path(tmp) / "warn.md"
        warn.write_text(_WARN_DRAFT, encoding="utf-8")
        clean = Path(tmp) / "clean.md"
        clean.write_text(_PASS_DRAFT, encoding="utf-8")
        rev_ok = Path(tmp) / "rev_ok.md"
        rev_ok.write_text(_REVISED_OK, encoding="utf-8")
        rev_bad = Path(tmp) / "rev_bad.md"
        rev_bad.write_text(_REVISED_BAD, encoding="utf-8")
        files = {"@FAIL": fail, "@WARN": warn, "@PASS": clean, "@REVOK": rev_ok, "@REVBAD": rev_bad}
        argv = [str(files.get(a, a)) for a in argv]
        env = dict(os.environ)
        env.update(
            {
                "PYTHONHASHSEED": "0",
                "TIMBRO_HOME": str(Path(tmp) / "home"),
                "TIMBRO_PROFILE_ROOT": str(Path(tmp) / "profiles"),
                "XDG_DATA_HOME": str(Path(tmp) / "xdg"),
            }
        )
        return subprocess.run(
            [sys.executable, "-m", "timbro.cli", *argv],
            capture_output=True,
            text=True,
            timeout=600,
            env=env,
            check=False,
        )


class CheckFailExitsThreeTests(unittest.TestCase):
    def test_text_mode_fail_verdict_exits_3_with_byte_identical_stdout(self):
        proc = _run_cli(["check", "@FAIL"])
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertEqual(proc.stdout, _CHECK_FAIL_TEXT_OUT)
        self.assertEqual(proc.stderr, "")

    def test_json_mode_fail_verdict_exits_3_with_byte_identical_stdout(self):
        proc = _run_cli(["check", "@FAIL", "--json"])
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertEqual(proc.stdout, _CHECK_FAIL_JSON_OUT)


class CheckWarnAndPassStillExitZeroTests(unittest.TestCase):
    def test_text_mode_warn_verdict_exits_0(self):
        proc = _run_cli(["check", "@WARN", "--rubric", "slop"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.startswith("verdict: WARN"), proc.stdout)

    def test_json_mode_warn_verdict_exits_0(self):
        proc = _run_cli(["check", "@WARN", "--rubric", "slop", "--json"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["verdict"], "warn")

    def test_text_mode_pass_verdict_exits_0(self):
        proc = _run_cli(["check", "@PASS", "--rubric", "slop,density"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.startswith("verdict: PASS"), proc.stdout)

    def test_json_mode_pass_verdict_exits_0(self):
        proc = _run_cli(["check", "@PASS", "--rubric", "slop,density", "--json"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["verdict"], "pass")


class AcceptRejectedExitsThreeTests(unittest.TestCase):
    def test_text_mode_rejected_exits_3_with_byte_identical_stdout(self):
        proc = _run_cli(["accept", "@PASS", "@REVBAD"])
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertEqual(proc.stdout, _ACCEPT_REJECT_TEXT_OUT)

    def test_json_mode_rejected_exits_3(self):
        # The JSON payload carries full-precision model floats, so bytes are
        # pinned only structurally: the booleans must match the pre-change
        # output exactly. The distance floats are corpus-dependent model
        # output (#163 changed them), so they are not pinned here;
        # byte-identity of the full payload is proven by the round's
        # base/head snapshot comparison.
        proc = _run_cli(["accept", "@PASS", "@REVBAD", "--json"])
        self.assertEqual(proc.returncode, 3, proc.stderr)
        payload = json.loads(proc.stdout)
        expected = json.loads('{\n  "accepted": false,\n  "content_ok": false,\n  "similarity": 0.03138686716556549,\n  "improved": false\n}\n')
        self.assertEqual(payload["accepted"], expected["accepted"])
        self.assertEqual(payload["content_ok"], expected["content_ok"])
        self.assertEqual(payload["improved"], expected["improved"])
        self.assertAlmostEqual(payload["similarity"], expected["similarity"], places=6)


class AcceptAcceptedStillExitsZeroTests(unittest.TestCase):
    def test_text_mode_accepted_exits_0(self):
        proc = _run_cli(["accept", "@PASS", "@REVOK"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(proc.stdout.startswith("accepted:"), proc.stdout)

    def test_json_mode_accepted_exits_0(self):
        proc = _run_cli(["accept", "@PASS", "@REVOK", "--json"])
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIs(json.loads(proc.stdout)["accepted"], True)


if __name__ == "__main__":
    unittest.main()
