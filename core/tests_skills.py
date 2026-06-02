import tempfile
from pathlib import Path

from django.test import SimpleTestCase

from core.skills import SkillRegistry


class SkillRegistryTests(SimpleTestCase):
    def test_search_prioritizes_enabled_skill_by_tag(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "skills.json"
            path.write_text(
                """
                {
                  "schema_version": "1.0",
                  "skills": [
                    {
                      "name": "api_request_standard",
                      "version": "1.0.0",
                      "enabled": true,
                      "priority": "high",
                      "domain": "integration",
                      "tags": ["api", "networking"],
                      "rules": ["usar timeout"],
                      "defaults": {"timeout": 30}
                    },
                    {
                      "name": "disabled_api",
                      "version": "1.0.0",
                      "enabled": false,
                      "priority": "critical",
                      "domain": "integration",
                      "tags": ["api", "networking"],
                      "rules": ["no usar"]
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            registry = SkillRegistry(skills_dir=temp_dir)
            matches = registry.search(tags=["api"])

            self.assertEqual(matches[0].name, "api_request_standard")
            self.assertIsNone(registry.get("disabled_api"))

    def test_extends_merges_rules_and_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "skills.json"
            path.write_text(
                """
                {
                  "schema_version": "1.0",
                  "skills": [
                    {
                      "name": "base",
                      "version": "1.0.0",
                      "enabled": true,
                      "priority": "medium",
                      "domain": "general",
                      "tags": ["base"],
                      "rules": ["regla base"],
                      "defaults": {"timeout": 30}
                    },
                    {
                      "name": "child",
                      "version": "1.0.0",
                      "enabled": true,
                      "priority": "high",
                      "domain": "general",
                      "tags": ["child"],
                      "extends": ["base"],
                      "rules": ["regla hija"],
                      "defaults": {"retries": 3}
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            skill = SkillRegistry(skills_dir=temp_dir).get("child")

            self.assertIn("regla base", skill.rules)
            self.assertIn("regla hija", skill.rules)
            self.assertEqual(skill.defaults["timeout"], 30)
            self.assertEqual(skill.defaults["retries"], 3)
