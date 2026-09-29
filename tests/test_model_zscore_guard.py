"""Issue #160: near-duplicate exemplars leave float-rounding POS stds around
1e-17, which slip past the exact-zero guard (`pstd[pstd == 0] = 1.0`) and make
`score` return z ~3e15 at confidence 1.00 ("fewer auxiliary verbs,
confidence 1.00"). POS and tell rates live in [0, 1], so a std below 1e-9 is
float rounding, not spread, and must be guarded like an exact zero.
"""
from __future__ import annotations

import math
import unittest
from unittest import mock

import numpy as np

import timbro.model as tm

# Bound the real feature_matrix once at import so the patched version can call it
# without recursing into itself while the patch is active.
_REAL_FEATURE_MATRIX = tm.feature_matrix

_PARA = (
    "The team reviewed the plan this morning and agreed that the second draft "
    "reads much closer to the voice we want for the launch, so we will keep "
    "the same opening, trim the middle section, and send it out before the "
    "end of the day with a short summary attached."
)
# Near-duplicate exemplars: the same text block per doc plus one tiny differing
# closing sentence -- the issue's "same article twice" corpus (health != insufficient,
# so score() emits moves).
_TEXTS = [
    "\n\n".join([_PARA] * 6) + f"\n\nVariant {i} closes with a short note about timing."
    for i in range(4)
]
_DRAFT = (
    "I just wanted to quickly say that I think this approach might actually work "
    "for us, though we should probably keep an eye on the way the team handles "
    "the reviews before we ship it to everyone next week."
)


def _patched_feature_matrix(texts):
    """feature_matrix with the pos_AUX column forced to a tiny-but-nonzero std."""
    X, names = _REAL_FEATURE_MATRIX(texts)
    X = np.array(X, dtype=float)
    X[:, names.index("pos_AUX")] = [0.0, 0.0, 0.0, 2e-17]  # std ~8.7e-18, nonzero
    return X, names


class ZscoreFloatFloorTests(unittest.TestCase):
    def test_tiny_but_nonzero_std_cannot_explode_current_z(self):
        # Fixture sanity: the patched pos_AUX column really has a tiny, nonzero std.
        X, names = _patched_feature_matrix(_TEXTS)
        col_std = float(X[:, names.index("pos_AUX")].std())
        self.assertGreater(col_std, 0.0)
        self.assertLess(col_std, 1e-9)
        with mock.patch.object(tm, "feature_matrix", _patched_feature_matrix):
            model = tm.VoiceModel.fit(_TEXTS)
        for move in model.score(_DRAFT).direction:
            self.assertTrue(math.isfinite(move.current_z), f"{move.feature}: {move.current_z}")
            self.assertLess(abs(move.current_z), 1e6, f"{move.feature}: {move.current_z}")


if __name__ == "__main__":
    unittest.main()
