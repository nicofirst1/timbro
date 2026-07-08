"""Parse-layer tests for build_skillssh.

Seam under test: parse_detail_page(html, url) -> row dict, and its URL helper.
These pin the two assumptions the module docstring flagged as UNVERIFIED against a
live page. Ground truth was read from a real skills.sh detail page on 2026-07-08:

    https://www.skills.sh/accesslint/claude-marketplace/audit
    -> owner=accesslint, repo=claude-marketplace, skill=audit
    -> installs (InstallAction userInteractionCount) = 363

The real page URL is /{owner}/{repo}/{skill} with NO "/skills/" path prefix, and
installs live in a SoftwareApplication JSON-LD block's interactionStatistic. The
literals below are transcribed from that page, not computed by the code under test.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from build_skillssh import parse_detail_page, parse_owner_repo_skill  # noqa: E402

REAL_URL = "https://www.skills.sh/accesslint/claude-marketplace/audit"

# Minimal transcription of the real page's SoftwareApplication JSON-LD (installs=363).
REAL_HTML = """<!doctype html><html><head>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"SoftwareApplication","name":"audit",
 "url":"https://www.skills.sh/accesslint/claude-marketplace/audit",
 "interactionStatistic":{"@type":"InteractionCounter",
   "interactionType":"https://schema.org/InstallAction","userInteractionCount":363}}
</script></head><body>audit</body></html>"""


def test_url_parses_to_owner_repo_skill():
    assert parse_owner_repo_skill(REAL_URL) == ("accesslint", "claude-marketplace", "audit")


def test_detail_page_extracts_installs():
    row = parse_detail_page(REAL_HTML, REAL_URL)
    assert row is not None
    assert (row["owner"], row["repo"], row["skill"]) == ("accesslint", "claude-marketplace", "audit")
    assert row["installs"] == 363


def test_listing_page_is_not_a_skill_detail():
    # An owner/repo listing page (2 path segments) is not a skill detail page.
    assert parse_owner_repo_skill("https://www.skills.sh/accesslint/claude-marketplace") is None
