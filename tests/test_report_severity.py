from __future__ import annotations

import unittest

from timbro.rubrics.base import RubricFinding
from timbro.rubrics.report import build_result


def _finding(severity: str, rule: str, paragraph: int) -> RubricFinding:
    return RubricFinding(
        severity=severity,
        dimension="clarity",
        rule=rule,
        paragraph=paragraph,
        sentence=None,
        span="",
        message="",
    )


class BuildResultSeverityOrderTests(unittest.TestCase):
    def test_findings_are_sorted_high_medium_low_stable_within_severity(self):
        findings = [
            _finding("low", "rule_low_a", 1),
            _finding("high", "rule_high_a", 2),
            _finding("medium", "rule_medium_a", 3),
            _finding("high", "rule_high_b", 4),
            _finding("low", "rule_low_b", 5),
            _finding("medium", "rule_medium_b", 6),
        ]
        result = build_result(rubric="schimel", version="v3", sections={}, findings=findings)
        self.assertEqual(
            [f.rule for f in result.findings],
            [
                "rule_high_a",
                "rule_high_b",
                "rule_medium_a",
                "rule_medium_b",
                "rule_low_a",
                "rule_low_b",
            ],
        )


if __name__ == "__main__":
    unittest.main()
