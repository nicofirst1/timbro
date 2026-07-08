"""Pure-logic tests for parse_weekly_installs.

Seam: parse_weekly_series(html) -> list[int] | None ; series_mean ; build_row(html, url).
No cache/disk I/O. Ground truth is transcribed from the LEDGER 2026-07-08 inspection: the
sparkline aria-label is ALWAYS an 8-week series, and the value separator is ", " (comma +
whitespace), so a value >=1,000 like "1,901" is ONE value, not two. The thousands-separator
case is the load-bearing one — a naive split(",") would corrupt every series with a value
>=1,000 (and inflate the mean).
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from parse_weekly_installs import build_row, parse_weekly_series, series_mean  # noqa: E402


def _aria(content):
    return f'<svg aria-label="Weekly installs: {content}"></svg>'


def test_plain_series_parses_to_eight_ints():
    assert parse_weekly_series(_aria("87, 88, 91, 139, 78, 54, 79, 70")) == [87, 88, 91, 139, 78, 54, 79, 70]


def test_thousands_separator_is_not_a_value_boundary():
    # Real n=9 page: 8 values, last is 1,901 -> must parse as one value 1901.
    assert parse_weekly_series(_aria("586, 437, 220, 145, 205, 177, 235, 1,901")) == \
        [586, 437, 220, 145, 205, 177, 235, 1901]


def test_all_values_over_thousand_still_eight_values():
    # Real n=16 page: every value >=1,000 -> naive split(",") would give 16 tokens.
    got = parse_weekly_series(_aria("1,086, 1,581, 3,486, 3,154, 2,415, 1,934, 2,327, 1,985"))
    assert got == [1086, 1581, 3486, 3154, 2415, 1934, 2327, 1985]
    assert len(got) == 8


def test_all_zero_series():
    assert parse_weekly_series(_aria("0, 0, 0, 0, 0, 0, 0, 0")) == [0, 0, 0, 0, 0, 0, 0, 0]


def test_no_aria_label_returns_none():
    assert parse_weekly_series("<html><body>no sparkline here</body></html>") is None


def test_series_mean_is_mean_of_full_series():
    assert series_mean([586, 437, 220, 145, 205, 177, 235, 1901]) == sum([586, 437, 220, 145, 205, 177, 235, 1901]) / 8


def test_series_mean_all_zero_is_zero():
    assert series_mean([0, 0, 0, 0, 0, 0, 0, 0]) == 0.0


def test_build_row_keys_off_url_and_carries_series_and_mean():
    url = "https://www.skills.sh/accesslint/claude-marketplace/audit"
    row = build_row(_aria("10, 20, 30, 40, 50, 60, 70, 80"), url)
    assert (row["owner"], row["repo"], row["skill"]) == ("accesslint", "claude-marketplace", "audit")
    assert row["weekly_installs"] == [10, 20, 30, 40, 50, 60, 70, 80]
    assert row["installs_wk_mean"] == 45.0


def test_build_row_none_when_url_not_three_segments():
    # An owner/repo listing page (2 segments) is not a skill detail page.
    assert build_row(_aria("1, 2, 3, 4, 5, 6, 7, 8"), "https://www.skills.sh/accesslint/claude-marketplace") is None


def test_build_row_none_when_no_aria():
    assert build_row("<html></html>", "https://www.skills.sh/a/b/c") is None
