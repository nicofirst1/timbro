from __future__ import annotations

from timbro.rubrics.base import RubricFinding, RubricResult

_PENALTY = {"high": 0.25, "medium": 0.10, "low": 0.05}
_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}
_WEIGHTS = {
    "opening": 1.25,
    "challenge": 1.25,
    "resolution": 1.25,
    "flow": 1.25,
    "paragraphs": 1.0,
    "sentences": 1.0,
    "clarity": 1.0,
}


def build_result(
    *,
    rubric: str,
    version: str,
    sections: dict,
    findings: list[RubricFinding],
    weights: dict[str, float] = _WEIGHTS,
) -> RubricResult:
    dims = {name: 1.0 for name in weights}
    # A rule that reports N occurrences (M1: one finding per occurrence) still costs one
    # penalty, not N — dedup on the rule name before applying the per-severity penalty.
    seen_rules: set[str] = set()
    for finding in findings:
        if finding.rule in seen_rules:
            continue
        seen_rules.add(finding.rule)
        dims[finding.dimension] = max(0.0, dims[finding.dimension] - _PENALTY[finding.severity])
    total_weight = sum(weights.values())
    overall = sum(dims[name] * weights[name] for name in dims) / total_weight
    verdict = "fail" if overall < 0.55 or any(f.severity == "high" for f in findings if f.dimension in {"challenge", "resolution", "opening"}) else "warn" if overall < 0.75 else "pass"
    ranked_findings = sorted(findings, key=lambda f: _SEVERITY_RANK[f.severity])
    return RubricResult(rubric, version, round(overall, 3), verdict, {k: round(v, 3) for k, v in dims.items()}, sections, ranked_findings)


def render_text(result: RubricResult) -> str:
    lines = [f"{result.rubric}: {result.verdict.upper()} ({result.overall:.2f})", ""]
    for name, score in result.dimensions.items():
        lines.append(f"{name:12s} {score:.2f}")
    if result.findings:
        lines.extend(["", "Top findings"])
        for finding in result.findings[:5]:
            loc = f"P{finding.paragraph}" if finding.paragraph else finding.dimension
            lines.append(f"- {loc}: {finding.rule}; {finding.message}")
    return "\n".join(lines)
