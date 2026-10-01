"""HD-D (the richness axis value) must not depend on PYTHONHASHSEED (#123).

`hdd()` used to sum one hypergeometric term per type in `list(set(text))` order
inside lexical_diversity: Python randomizes string hashing per process, so the
float additions happened in a different order each run and the result moved by
~1 ULP. The axis now computes HD-D locally in a deterministic order (sorted
types, math.fsum); these tests pin byte-identical output across hash seeds and
agreement with the library formula.
"""
from __future__ import annotations

import ast
import os
import subprocess
import sys
import tempfile
import unittest

from timbro.axes.richness import RICHNESS_METRIC

# >42 content-word tokens each -- hdd() samples a fixed 42-token window and
# returns 0.0 below that (see test_richness.py). This exact text moves in the
# last digit between PYTHONHASHSEED=5 and PYTHONHASHSEED=9 on pre-#123 code.
_TEXT = ("The cat sat on the mat. The cat was happy. The cat liked the mat. "
         "The cat sat there all day. The mat was soft and the cat liked it. "
         "The dog ran in the yard. The dog was happy. The dog liked the yard. "
         "The dog ran there all day. The yard was big and the dog liked it. "
         "The cat and the dog were friends. They sat in the yard on the mat. "
         "They liked the sun and the soft grass. The day was long and warm.")


class SubprocessDeterminismTest(unittest.TestCase):
    """The acceptance pin: one text, two processes, two hash seeds, one output."""

    def _extract_repr_stdout(self, seed: str) -> tuple[bytes, float]:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        env["TIMBRO_HOME"] = tempfile.mkdtemp(prefix="timbro-i123-home-")
        code = ("from timbro.axes.richness import RICHNESS_METRIC; "
                f"print(repr(RICHNESS_METRIC.extract({_TEXT!r})))")
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, timeout=600, check=False, env=env,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        value = ast.literal_eval(r.stdout.decode().strip())
        self.assertIsInstance(value, tuple)
        # Non-vacuous: a degenerate 0.0 would be byte-equal for the wrong reason.
        self.assertGreater(value[1], 0.0, r.stdout)
        return r.stdout, value

    def test_extract_byte_identical_across_hash_seeds(self):
        out5, _ = self._extract_repr_stdout("5")
        out9, _ = self._extract_repr_stdout("9")
        self.assertEqual(out5, out9)


class LocalHddVsLibraryTest(unittest.TestCase):
    def test_within_1e9_of_library_hdd_on_fixed_corpora(self):
        from lexical_diversity import lex_div

        from timbro.axes.richness import _hdd

        # Fixed corpora, no spaCy: _hdd takes the token list directly.
        corpora = [
            [f"w{i % 17}" for i in range(60)],          # 17 types, 60 tokens
            [f"tok{i}" for i in range(100)],            # 100 distinct types
            ["same"] * 50,                              # 1 type, max repetition
            ["cat", "dog", "run", "fast", "sleep", "day"] * 10,  # 6 types, 60 tokens
        ]
        for tokens in corpora:
            self.assertAlmostEqual(
                _hdd(tokens), lex_div.hdd(tokens), delta=1e-9,
                msg=f"corpus of {len(tokens)} tokens, {len(set(tokens))} types",
            )


class LocalHddShortInputTest(unittest.TestCase):
    def test_below_sample_window_returns_zero(self):
        from timbro.axes.richness import _hdd

        # hdd's ZeroDivisionError path: the library (and so _hdd) returns 0.0
        # below the 42-token sample size; the call site's >= 2 guard does not
        # screen this range.
        self.assertEqual(_hdd(["cat", "dog"]), 0.0)
        self.assertEqual(_hdd([f"w{i}" for i in range(41)]), 0.0)


if __name__ == "__main__":
    unittest.main()
