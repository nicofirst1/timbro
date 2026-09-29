"""Issue #160: near-duplicate exemplars leave float-rounding POS stds around
1e-17, which slip past the exact-zero guard (`pstd[pstd == 0] = 1.0`) and make
`score` return z ~3e15 at confidence 1.00 ("fewer auxiliary verbs,
confidence 1.00"). POS and tell rates live in [0, 1], so a std below 1e-9 is
float rounding, not spread, and must be guarded like an exact zero.
"""
from __future__ import annotations

import math
import re
import unittest
from unittest import mock

import numpy as np

import timbro.model as tm
import timbro.model.embedding as tem

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


# Health-ok corpus (>= 2500 words / >= 16 substantive paragraphs, per
# _profile_evidence) so normalized_distance reports a distance_z instead of
# returning None.
_TEXTS_OK = [
    "\n\n".join([_PARA] * 13) + f"\n\nVariant {i} closes with a short note about timing."
    for i in range(4)
]


def _patched_feature_matrix(texts):
    """feature_matrix with the pos_AUX column forced to a tiny-but-nonzero std."""
    X, names = _REAL_FEATURE_MATRIX(texts)
    X = np.array(X, dtype=float)
    X[:, names.index("pos_AUX")] = [0.0, 0.0, 0.0, 2e-17]  # std ~8.7e-18, nonzero
    return X, names


# Embedding twin of the round-1 patch: the real _style_vec with dimension 0
# overridden. Exemplar docs (they carry the "Variant i" marker) get values
# 0, 7e-18, 14e-18, 21e-18 -- distinct doubles, so the column std is tiny but
# nonzero (~8.1e-18); the draft (no marker) sits at a normal 0.05 offset, which
# is the O(0.01) genuine difference the bug amplifies into z ~1e15.
# Bound the real _style_vec once at import so the patched version can call it
# without recursing while the patch is active.
_REAL_STYLE_VEC = tem._style_vec
_EMBED_DIM = 0
_DRAFT_EMBED_VALUE = 0.05


def _patched_style_vec(text: str) -> tuple[float, ...]:
    v = list(_REAL_STYLE_VEC(text))
    m = re.search(r"Variant (\d+)", text)
    v[_EMBED_DIM] = 7e-18 * int(m.group(1)) if m else _DRAFT_EMBED_VALUE
    return tuple(v)


# --- Round 3: the embedding path's E is float32, so byte-identical exemplars
# leave per-dimension stds at the float32 mean-rounding scale even though the
# vectors are bitwise equal (measured 1.9e-9..7.5e-9 on the degen3b sandbox
# corpus, 36 of 768 dims) -- ABOVE the r2 floor of 1e-9, so the scalar distance
# still explodes. Measured on real corpora: smallest per-dim std 1.38e-4
# (packaged sample voice; 5-post and 6-post corpora 3.8e-4..1.3e-3), largest
# near-duplicate rounding noise 7.45e-9. Floor 1e-6 sits 134x above the noise
# and 138x below the smallest real spread.
_LONG_POST_PARAS = [
    (
        "The release train left the station on Tuesday, and for the first time in "
        "months nobody stood next to it with a fire extinguisher. The change that "
        "made the difference was not a new tool or a bolder roadmap. It was a "
        "decision to stop carrying features that nobody had touched since spring, "
        "and to say so out loud in the planning meeting instead of letting them "
        "hibernate in the backlog for another quarter."
    ),
    (
        "Cutting a feature is not the same as killing it. We moved the code to a "
        "branch, wrote a paragraph about why it existed and what would have to be "
        "true for it to come back, and tagged the branch so the paragraph travels "
        "with it. Two people asked where the feature had gone. Both were satisfied "
        "by the paragraph, which says something about how much of our backlog is "
        "maintained for an audience that no longer exists."
    ),
    (
        "The planning meeting itself changed shape. We used to walk the backlog "
        "from the top, which meant the oldest items were discussed the least "
        "because everybody had already made up their minds about them. Now we "
        "walk it from the bottom, from the oldest untouched row upward, and the "
        "first question for each row is whether the world that justified it still "
        "exists. More rows die in the meeting than in any review document."
    ),
    (
        "There was a cost, and it is worth naming. One cut feature turned out to "
        "matter to a customer we had stopped talking to, and we spent a week "
        "restoring it from the branch. The restore went fine, precisely because "
        "the branch carried its own explanation. That week cost less than a "
        "quarter of quietly maintaining the feature for everyone else."
    ),
    (
        "The measurement we trust is not velocity. It is how often a line of the "
        "backlog changes state without a human touching it, which is our proxy "
        "for priorities that have gone stale. Six months in, that number is down "
        "by half, and the rows that remain are the ones people can explain in one "
        "sentence when asked why they exist."
    ),
    (
        "The rollback story deserves its own paragraph. We used to treat a "
        "rollback as a failure of planning, something to be apologized for in the "
        "review. Now a rollback that takes five minutes is just a Tuesday action, "
        "and the review asks why it took five minutes rather than why it happened "
        "at all. The change in tone did more for our release health than any "
        "tool. Engineers call for the rollback earlier, when the blast radius is "
        "small, instead of riding out a bad deploy because calling it feels like "
        "an admission."
    ),
    (
        "Documentation followed the same path. Every feature we cut keeps a "
        "one-page headstone: what it did, who asked for it, what changed in the "
        "world that made it stop mattering. New engineers read the headstones "
        "before the architecture docs, because the headstones explain why the "
        "system looks the way it does. Half of our tribal knowledge used to live "
        "in the heads of two people. The headstones moved it into the repository "
        "where it belongs."
    ),
    (
        "The last piece was celebrating the cuts in the release notes. Users read "
        "release notes to learn what changed, and a feature quietly disappearing "
        "is a change whether we name it or not. Naming it cut support tickets by "
        "a third for the affected areas. People respect honesty about subtraction "
        "far more than we expected, and the notes have become a place where the "
        "roadmap argues with itself in public, politely, once a month."
    ),
    (
        "Hiring changed with the same logic. We stopped asking candidates to "
        "describe a time they shipped something big and started asking what they "
        "had removed. The best answer we ever got was a confession: a service the "
        "candidate had turned off in their first month, with the graph of the "
        "alerts that never came back. We hired that person. The graph is still "
        "flat and the service is still gone."
    ),
    (
        "None of this made the roadmap shorter. Cutting the dead weight made "
        "room, and room fills. What changed is the texture of the arguments: "
        "when somebody proposes a new line of work, the first question is what "
        "it replaces, and the second is what we will stop doing to make space "
        "for it. The answers are written down next to the proposal, which keeps "
        "the conversation honest without slowing it down much."
    ),
    (
        "The survey we run every quarter asked the same question for three years "
        "and got the same answer, and we kept shipping features for the people "
        "who never answered it. When we finally split the responses by how long "
        "the respondent had been with us, the pattern was embarrassing: the "
        "features everyone praised in planning were the ones the newest cohort "
        "could not find. We renamed nothing and removed nothing that week. We "
        "just stopped counting the praise of people who had already learned "
        "their way around, and the next quarter's plan looked different on its "
        "own. The dashboard that tracked the split now has a third line, and "
        "nobody has asked to remove it."
    ),
]
# degen3b-style: the same article three times -- the issue's "ingesting the same
# article twice" corpus. Eight paragraphs x3 keeps health "ok" so distance_z
# reports; the corpus must be >= 2500 words for _profile_evidence.
_DEGEN_TEXTS = ["\n\n".join(_LONG_POST_PARAS)] * 3
_DEGEN_DRAFT = (
    "Rain fell on the market square all morning, and the stalls with the best "
    "awnings did the best trade. The cheesemonger, who has sold on the square "
    "for thirty years, says the weather decides more than price ever did. The "
    "stalls that stay open through winter are the ones with a roof and a "
    "regular crowd, not the ones with the loudest signs."
)


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
class EmbeddingFloatFloorTests(unittest.TestCase):
    def test_tiny_but_nonzero_embedding_std_keeps_distance_sane(self):
        # Fixture sanity: the patched embedding dimension really has a tiny, nonzero std.
        E = np.array([_patched_style_vec(t) for t in _TEXTS_OK])
        col_std = float(E[:, _EMBED_DIM].std())
        self.assertGreater(col_std, 0.0)
        self.assertLess(col_std, 1e-9)
        # fit_embedding resolves _style_vec in embedding.py, _dist in timbro.model:
        # patch both so exemplars and draft go through the same patched vector.
        with mock.patch.object(tem, "_style_vec", _patched_style_vec), mock.patch.object(
            tm, "_style_vec", _patched_style_vec
        ):
            model = tm.VoiceModel.fit(_TEXTS_OK)
        distance = model.score(_DRAFT).distance
        distance_z = model.normalized_distance(_DRAFT)
        self.assertTrue(math.isfinite(distance), f"distance {distance}")
        self.assertLess(distance, 1e6, f"distance {distance}")
        self.assertIsNotNone(distance_z)
        self.assertTrue(math.isfinite(distance_z), f"distance_z {distance_z}")
        self.assertLess(abs(distance_z), 1e6, f"distance_z {distance_z}")
class EmbeddingFloat32NoiseTests(unittest.TestCase):
    def test_byte_identical_exemplars_keep_distance_and_z_sane(self):
        # Fixture sanity: the corpus is health-ok (distance_z reports) and its raw
        # per-dim stds reach the float32 mean-rounding band the r2 floor misses,
        # while staying below 1e-6 (pure rounding, zero genuine spread).
        E = np.array([_REAL_STYLE_VEC(t) for t in _DEGEN_TEXTS])
        estd = E.std(0)
        self.assertGreaterEqual(float(estd.max()), 1e-9)
        self.assertLess(float(estd.max()), 1e-6)
        # Real pipeline, no patching: the noise is E.std(0)'s float32 mean-rounding.
        model = tm.VoiceModel.fit(_DEGEN_TEXTS)
        distance = model.score(_DEGEN_DRAFT).distance
        distance_z = model.normalized_distance(_DEGEN_DRAFT)
        self.assertTrue(math.isfinite(distance), f"distance {distance}")
        self.assertLess(distance, 1e3, f"distance {distance}")
        self.assertIsNotNone(distance_z)
        self.assertTrue(math.isfinite(distance_z), f"distance_z {distance_z}")
        self.assertLess(abs(distance_z), 1e3, f"distance_z {distance_z}")


if __name__ == "__main__":
    unittest.main()
