"""The load-bearing rules of code-hygiene/SKILL.md, frozen by docs/specs/code-hygiene-token-diet.json."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))
from claude_model_check import frontmatter_sha256, missing_rules, normalized_body, split_skill  # noqa: E402

SPEC = json.loads((REPO_ROOT / "docs" / "specs" / "code-hygiene-token-diet.json").read_text(encoding="utf-8"))
SKILL = (REPO_ROOT / SPEC["skill"]).read_text(encoding="utf-8")


class CoreRuleTests(unittest.TestCase):
    def test_every_load_bearing_sentence_is_present(self) -> None:
        self.assertEqual([], missing_rules(SKILL, SPEC["load_bearing"]))

    def test_deleting_a_sentence_flags_exactly_its_rule(self) -> None:
        front, _ = split_skill(SKILL)
        for rule, sentences in SPEC["load_bearing"].items():
            for sentence in sentences:
                with self.subTest(rule=rule, sentence=sentence[:50]):
                    mutated = front + normalized_body(SKILL).replace(sentence, "")
                    self.assertEqual([rule], missing_rules(mutated, SPEC["load_bearing"]))

    def test_frontmatter_is_unchanged(self) -> None:
        self.assertEqual(SPEC["frontmatter_sha256"], frontmatter_sha256(SKILL))


if __name__ == "__main__":
    unittest.main()
