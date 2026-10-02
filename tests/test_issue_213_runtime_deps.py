"""lexical-diversity and the setuptools<81 pin must be dev-only, not runtime (#213).

HD-D is computed locally since #123, so no src/timbro module imports
lexical_diversity any more, and setuptools was only declared for
lexical-diversity's pkg_resources import. Both must live in the dev group
only: the HD-D parity test (tests/test_richness_hdd_determinism.py) still
compares against the library, and that library still needs setuptools<81.
"""
from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def _canonical(dep: str) -> str:
    name = dep.split(";")[0].split(">")[0].split("<")[0].split("=")[0].strip()
    return name.lower().replace("_", "-")


class RuntimeDepsTest(unittest.TestCase):
    def setUp(self):
        data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
        self.runtime_raw = list(data["project"]["dependencies"])
        self.runtime = {_canonical(d) for d in self.runtime_raw}
        self.dev_raw = list(data["dependency-groups"]["dev"])
        self.dev = {_canonical(d) for d in self.dev_raw}

    def test_lexical_diversity_not_a_runtime_dependency(self):
        self.assertNotIn("lexical-diversity", self.runtime,
                         f"runtime deps: {self.runtime_raw}")

    def test_setuptools_not_a_runtime_dependency(self):
        self.assertNotIn("setuptools", self.runtime,
                         f"runtime deps: {self.runtime_raw}")

    def test_lexical_diversity_kept_as_dev_reference(self):
        # test_richness_hdd_determinism.py imports lexical_diversity as the
        # reference implementation; the dev group must keep it installed.
        self.assertIn("lexical-diversity", self.dev, f"dev group: {self.dev_raw}")

    def test_setuptools_pin_kept_in_dev_for_pkg_resources(self):
        # lexical-diversity imports pkg_resources, which setuptools>=81 dropped,
        # so the dev copy of lexical-diversity needs setuptools<81.
        self.assertIn("setuptools<81", self.dev_raw, f"dev group: {self.dev_raw}")


if __name__ == "__main__":
    unittest.main()
