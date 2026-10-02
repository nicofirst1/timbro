"""Every skills/*/SKILL.md has frontmatter that strict loaders can parse (#210).

The timbro-review skill shipped since 0.8.0 with an unquoted plain-scalar
description containing ": ", which fails yaml.safe_load; pi's loader dropped
the skill silently. Guard the whole contract here: frontmatter between the
first two ``---`` lines parses as YAML, exposes ``name`` and ``description``,
and the description stays within the 1024-character budget.
"""
from __future__ import annotations

import unittest
from pathlib import Path

import yaml

MAX_DESCRIPTION_CHARS = 1024

SKILL_FILES = sorted((Path(__file__).resolve().parents[1] / "skills").glob("*/SKILL.md"))


class SkillFrontmatterTest(unittest.TestCase):
    def test_skill_files_exist(self):
        # Fail loudly on an empty glob (renamed layout) instead of passing vacuously.
        self.assertGreaterEqual(len(SKILL_FILES), 2, f"found: {SKILL_FILES}")

    def test_frontmatter_parses_with_name_and_description(self):
        for skill in SKILL_FILES:
            with self.subTest(skill=str(skill.relative_to(skill.parents[2]))):
                lines = skill.read_text().splitlines()
                self.assertEqual("---", lines[0], f"{skill} must start with ---")
                closing = lines.index("---", 1)
                block = "\n".join(lines[1:closing])
                try:
                    frontmatter = yaml.safe_load(block)
                except yaml.YAMLError as exc:
                    self.fail(f"{skill} frontmatter is not valid YAML: {exc}")
                self.assertIsInstance(frontmatter, dict, str(skill))
                self.assertIn("name", frontmatter, str(skill))
                self.assertIn("description", frontmatter, str(skill))
                self.assertIsInstance(frontmatter["name"], str, str(skill))
                self.assertIsInstance(frontmatter["description"], str, str(skill))

    def test_description_within_budget(self):
        for skill in SKILL_FILES:
            with self.subTest(skill=str(skill.relative_to(skill.parents[2]))):
                lines = skill.read_text().splitlines()
                block = "\n".join(lines[1:lines.index("---", 1)])
                frontmatter = yaml.safe_load(block)
                self.assertIsInstance(frontmatter, dict, str(skill))
                self.assertLessEqual(
                    len(frontmatter.get("description") or ""),
                    MAX_DESCRIPTION_CHARS,
                    str(skill),
                )


if __name__ == "__main__":
    unittest.main()
