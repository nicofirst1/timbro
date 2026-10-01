"""Issue #132: `_TABLE_SEPARATOR` must also count GFM separator rows with
optional leading/trailing pipes (the form nearly every markdown writer and LLM
produces). Bare separator rows keep counting; horizontal rules (lone `---`, lone
`| --- |`) and single-column tables stay uncounted."""

from __future__ import annotations

import unittest


def _table_count(text: str) -> int:
    from timbro.axes.markdown import _struct_features

    return _struct_features(text)[0]["struct_table_count"]


class GfmTableCountTests(unittest.TestCase):
    def test_piped_separator_row_counts(self):
        # `| --- | --- |` matched nothing before #132 (the regex had to start with
        # dashes), so a one-table draft read as zero tables.
        self.assertEqual(_table_count("| a | b |\n| --- | --- |\n| 1 | 2 |\n"), 1)

    def test_bare_separator_row_still_counts(self):
        self.assertEqual(_table_count("a | b\n--- | ---\n1 | 2\n"), 1)

    def test_lone_horizontal_rule_not_counted(self):
        # A separator row needs at least two cells: a bare `---` rule is prose markup.
        self.assertEqual(_table_count("Intro.\n\n---\n\nMore prose.\n"), 0)

    def test_lone_piped_horizontal_rule_not_counted(self):
        # Same guard with pipes: a single-column `| --- |` stays uncounted.
        self.assertEqual(_table_count("Intro.\n\n| --- |\n\nMore prose.\n"), 0)


if __name__ == "__main__":
    unittest.main()
