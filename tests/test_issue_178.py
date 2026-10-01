"""Issue #178: near-duplicate corpora gave absurd standalone-axis z-scores.

A corpus whose two exemplars differ by one character has a real but tiny
markdown std (~1e-6): not float noise, so #160's exact-zero spread guard never
fires and a far-off draft z-scored into the 1e5-1e6 range. The owner decision
(#178) is option 3: cap every blend-style axis z at |z| = 10 (`_Z_SATURATION`)
and mark the row saturated; the direction logic consumes the clamped z. The
embedding path (distance/distance_z, #160's fix) is untouched.
"""
from __future__ import annotations

import contextlib
import io
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from timbro.cli import main
from timbro.model import VoiceModel, default_model
from timbro.report import AxisReport

_PARA = (
    "The team reviewed the deployment pipeline and agreed that the rollback path "
    "needed a clearer owner. Every incident this quarter started with an ambiguous "
    "handoff between the on-call engineer and the release manager, so we wrote the "
    "checklist down and pinned it to the runbook. "
)
# Two exemplars one character apart ("reviewed" -> "previewed"): every markdown
# metric value moves by a hair, so the corpus std is tiny but real.
_DOC = (
    "# Runbook\n\n" + _PARA * 6 + "\n\n## Escalation\n\n" + _PARA * 6
    + "\n\n```python\nstatus = deploy.check()\n```\n\n" + _PARA * 6
)
_DOC_ONE_CHAR_OFF = _DOC.replace("reviewed", "previewed", 1)
# Draft with no prose and all code: struct_code_char_ratio / struct_prose_ratio sit
# far from the corpus mean while the corpus std is tiny -- the issue's repro shape.
_REPRO_DRAFT = "# Draft\n\n```python\nx = deploy.check()\n```\n\n```python\ny = deploy.roll()\n```\n"

# A draft near the packaged sample voice: prose with one heading, no code blocks.
_SAMPLE_DRAFT = """# The quiet fix

We shipped the cache fix on Tuesday and nothing caught fire. The bug was
a stale entry behind the load balancer, and the health check kept passing
because it never read through the cache itself. One engineer traced it in
an afternoon once we stopped blaming the network.

The lesson is small. Write down where state enters the system, and make
the write path log the keys it touches. The next incident should take
minutes instead of days, and nobody will need a heroic debugging session
to find a single stale row hiding in plain sight.

We also agreed to keep the runbook short. A checklist nobody reads is
worse than a paragraph everybody does, so the escalation page now starts
with one sentence that names the owner of the rollback. It is the least
glamorous documentation work, and it is the work that pays off at three
in the morning when the pager goes off and the release manager is asleep.
"""


class NearDuplicateReproTests(unittest.TestCase):
    """The issue's 2-file repro: worst markdown row clamps to exactly +-10."""

    def test_worst_markdown_row_clamps_to_ten_and_saturates(self):
        model = VoiceModel.fit([_DOC, _DOC_ONE_CHAR_OFF])
        rows = model.axis_report("markdown", _REPRO_DRAFT)
        worst = max(rows, key=lambda r: abs(r.z))
        self.assertEqual(worst.z, 10.0)  # +1150363.98 pre-fix
        self.assertIs(worst.saturated, True)
        self.assertNotEqual(worst.direction, "")

    def test_issue_evidence_axis_saturates(self):
        # The issue's evidence row (struct_prose_ratio z = 3040 there, -741597.24 here).
        model = VoiceModel.fit([_DOC, _DOC_ONE_CHAR_OFF])
        rows = {r.axis: r for r in model.axis_report("markdown", _REPRO_DRAFT)}
        self.assertIs(rows["struct_prose_ratio"].saturated, True)
        self.assertEqual(rows["struct_prose_ratio"].z, -10.0)
        self.assertEqual(rows["struct_prose_ratio"].direction, "add prose")

    def test_unsaturated_row_keeps_raw_z_and_default_flag(self):
        model = VoiceModel.fit([_DOC, _DOC_ONE_CHAR_OFF])
        rows = {r.axis: r for r in model.axis_report("markdown", _REPRO_DRAFT)}
        # -1.0 is real and far below the cap: printed exactly as before, flag False.
        self.assertEqual(rows["struct_heading_count"].z, -1.0)
        self.assertIs(rows["struct_heading_count"].saturated, False)

    def test_normal_corpus_rows_stay_unsaturated(self):
        # Packaged sample voice, fixed draft: no row saturates, no row reaches the cap.
        model = default_model()
        for group in ("markdown", "hedge", "fw", "concreteness", "richness"):
            for row in model.axis_report(group, _SAMPLE_DRAFT):
                self.assertIs(row.saturated, False, f"{group}/{row.axis}")
                self.assertLess(abs(row.z), 10.0, f"{group}/{row.axis}")


class AxisReportSaturatedFieldTests(unittest.TestCase):
    def test_saturated_defaults_false_for_positional_constructions(self):
        row = AxisReport("axis", 1.0, 2.0, 3.0, "up")
        self.assertIs(row.saturated, False)

    def test_to_dict_carries_saturated(self):
        d = AxisReport("axis", 1.0, 2.0, 3.0, "up", True).to_dict()
        self.assertIs(d["saturated"], True)


class CliSaturatedMarkerTests(unittest.TestCase):
    def _run_score(self) -> str:
        stdout = io.StringIO()
        with TemporaryDirectory() as tmp:
            corpus = Path(tmp) / "corpus"
            corpus.mkdir()
            (corpus / "a.md").write_text(_DOC, encoding="utf-8")
            (corpus / "b.md").write_text(_DOC_ONE_CHAR_OFF, encoding="utf-8")
            draft = Path(tmp) / "draft.md"
            draft.write_text(_REPRO_DRAFT, encoding="utf-8")
            with (
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(io.StringIO()),
                patch.dict(os.environ, {"TIMBRO_EXEMPLARS": str(corpus)}),
                patch("sys.argv", ["timbro", "score", str(draft)]),
            ):
                try:
                    main()
                except SystemExit as exc:  # pragma: no cover - success path
                    self.assertEqual(exc.code, 0)
        return stdout.getvalue()

    def test_saturated_marker_only_on_clamped_rows(self):
        out = self._run_score()
        # Both far-off rows saturate (z +1.15e6 and -7.4e5 pre-fix); every other
        # row prints exactly as before, with no marker.
        self.assertEqual(out.count("(saturated)"), 2, out)
        self.assertIn("(z +10.00 (saturated), code_char_ratio)", out)
        self.assertIn("(z -10.00 (saturated), prose_ratio)", out)
        # Unchanged print for an unsaturated row (pinned against the pre-change output).
        self.assertIn("  - add section headings       (z -1.00, heading_count)", out)


if __name__ == "__main__":
    unittest.main()
