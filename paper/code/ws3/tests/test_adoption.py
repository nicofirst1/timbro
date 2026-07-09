"""WS3 step 4 tests: the join-key seam and the BH correction.

The load-bearing seam for RQ2 is the loose install-join key (merge.py convention) that
maps a corpus row (repo + raw frontmatter `name:`) onto the skills.sh weekly outcome.
A silent key change here would zero out the outcome join (as happened during pre-reg when
features.parquet's JSON-normalized frontmatter was used instead of corpus.parquet's raw
frontmatter). These tests pin the key, the frontmatter parse, and the BH-over-5 rule.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).resolve().parents[1]))
from adoption import (  # noqa: E402
    benjamini_hochberg,
    frontmatter_name,
    join_key,
    outcome_join_key,
)


def test_join_key_matches_merge_convention():
    # re.sub(r"[^a-z0-9]","",s.lower())
    assert join_key("Awesome-Copilot") == "awesomecopilot"
    assert join_key("Terms_Page/Gen") == "termspagegen"
    assert join_key(None) == ""
    assert join_key("  ClaudE Code  ") == "claudecode"


def test_frontmatter_name_parse_and_quote_strip():
    assert frontmatter_name("name: enterprise-agent-ops\ndescription: x") == "enterprise-agent-ops"
    assert frontmatter_name('name: "Bun Package Manager"') == "Bun Package Manager"
    assert frontmatter_name("name: 'phoenix-cli'") == "phoenix-cli"
    assert frontmatter_name("description: no name here") is None
    assert frontmatter_name(None) is None
    assert frontmatter_name(float("nan")) is None  # NaN frontmatter must not crash


def test_outcome_join_key_reconstructs_owner_repo_name():
    # matches the merge.py grouping: (owner, reponame) from repo + frontmatter name.
    key = outcome_join_key("affaanm/EverythingClaudeCode", "name: enterprise-agent-ops")
    assert key == ("affaanm", "everythingclaudecode", "enterpriseagentops")


def test_outcome_join_key_none_without_owner_repo_shape():
    # rows whose repo has no owner/repo shape never join (merge.py skips them).
    assert outcome_join_key("noslash", "name: x") is None
    assert outcome_join_key(None, "name: x") is None
    assert outcome_join_key(float("nan"), "name: x") is None


def test_outcome_join_key_missing_frontmatter_name():
    # repo present but no frontmatter name -> third component is empty, not a crash.
    assert outcome_join_key("owner/repo", None) == ("owner", "repo", "")
    assert outcome_join_key("owner/repo", "description: x") == ("owner", "repo", "")


def test_benjamini_hochberg_over_five():
    # D6: BH q=0.10 over the 5 confirmatory features. Monotone step-up, order preserved.
    p = np.array([0.001, 0.20, 0.04, 0.60, 0.008])
    adj = benjamini_hochberg(p, 0.10)
    assert adj.shape == (5,)
    # smallest raw p stays smallest adjusted; all in [0,1]; monotone with rank
    assert np.all((adj >= 0) & (adj <= 1))
    order = np.argsort(p)
    assert np.all(np.diff(adj[order]) >= -1e-12)  # non-decreasing along sorted p
    # a clearly-significant p survives, a clearly-null one does not
    assert adj[0] <= 0.10
    assert adj[3] > 0.10


def test_benjamini_hochberg_all_null():
    p = np.array([0.9, 0.8, 0.95, 0.7, 0.99])
    adj = benjamini_hochberg(p, 0.10)
    assert np.all(adj > 0.10)
