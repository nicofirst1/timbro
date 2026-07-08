"""Chain-logic tests for build_skill_diffs (the RQ4 version-chain table).

Seam under test: build_chains(states_by_skill) and apply_fork_exclusion(rows) —
the §8b chain mechanics that run_chains_only() relies on. Expected values are
derived from the spec (§8b addendum: link before_sha==prev.after_sha, split on a
broken link and keep the longest contiguous segment; drop non-canonical members of
a multi-repo cluster), not from running the code.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from build_skill_diffs import apply_fork_exclusion, build_chains  # noqa: E402


def _state(sha, before, date, repo="r1", cluster=None, canon=False):
    return {
        "sha": sha, "before_sha": before, "text": f"t-{sha}", "commit_date": date,
        "intent_class": "x", "intent_confidence": 0.5, "quality_score": 0.5,
        "repo": repo, "skill_path": "SKILL.md", "platform": "claude",
        "skill_cluster_id": cluster, "is_canonical": canon, "is_root": before is None,
    }


def test_clean_chain_stays_whole():
    states = {"A": [
        _state("a0", None, "2026-01-01T00:00:00+00:00"),
        _state("a1", "a0", "2026-01-02T00:00:00+00:00"),
        _state("a2", "a1", "2026-01-03T00:00:00+00:00"),
    ]}
    rows, n_split = build_chains(states)
    assert n_split == 0
    assert [r["version_index"] for r in rows] == [0, 1, 2]
    assert [r["after_sha"] for r in rows] == ["a0", "a1", "a2"]
    assert all(r["n_versions"] == 3 for r in rows)


def test_broken_link_splits_keeping_longest_segment():
    states = {"B": [
        _state("b0", None, "2026-01-01T00:00:00+00:00"),
        _state("b1", "b0", "2026-01-02T00:00:00+00:00"),
        _state("b2", "ZZZ", "2026-01-03T00:00:00+00:00"),   # broken link -> new segment
        _state("b3", "b2", "2026-01-04T00:00:00+00:00"),
        _state("b4", "b3", "2026-01-05T00:00:00+00:00"),
    ]}
    rows, n_split = build_chains(states)
    assert n_split == 1
    assert [r["after_sha"] for r in rows] == ["b2", "b3", "b4"]  # longest segment wins
    assert all(r["n_versions"] == 3 for r in rows)


def test_fork_exclusion_drops_noncanonical_in_multirepo_cluster():
    states = {
        "P": [_state("p0", None, "2026-01-01T00:00:00+00:00", repo="r1", cluster="C1", canon=True)],
        "Q": [_state("q0", None, "2026-01-01T00:00:00+00:00", repo="r2", cluster="C1", canon=False)],
    }
    kept, n_excluded = apply_fork_exclusion(build_chains(states)[0])
    assert n_excluded == 1
    assert {r["skill_id"] for r in kept} == {"sd:P"}  # canonical kept, fork dropped


def test_single_repo_cluster_is_not_fork_excluded():
    # Same cluster, same repo -> not a cross-repo fork; both kept.
    states = {
        "P": [_state("p0", None, "2026-01-01T00:00:00+00:00", repo="r1", cluster="C1", canon=True)],
        "R": [_state("r0", None, "2026-01-01T00:00:00+00:00", repo="r1", cluster="C1", canon=False)],
    }
    kept, n_excluded = apply_fork_exclusion(build_chains(states)[0])
    assert n_excluded == 0
    assert {r["skill_id"] for r in kept} == {"sd:P", "sd:R"}
