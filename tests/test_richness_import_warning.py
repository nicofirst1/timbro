"""The lexical_diversity import behind the richness axis must stay silent (#140).

Every CLI run printed `UserWarning: pkg_resources is deprecated as an API...`
from lexical_diversity/lex_div.py:4 to stderr: the library imports
pkg_resources at module scope. The fix scopes an `ignore` filter to that one
import; this test pins the behavior cold, in a fresh subprocess with
`-W default` (re-enabling the warning exactly the way each CLI run sees it).
"""
from __future__ import annotations

import subprocess
import sys
import unittest


class PkgResourcesImportWarningTest(unittest.TestCase):
    def test_richness_import_emits_no_pkg_resources_warning(self):
        r = subprocess.run(
            [sys.executable, "-W", "default", "-c",
             ("from timbro.axes.richness import richness_stats; "
              "richness_stats('The cat sat on the mat. The dog ran in the yard.')")],
            capture_output=True, text=True, timeout=600, check=False,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn("pkg_resources is deprecated", r.stderr)


if __name__ == "__main__":
    unittest.main()
