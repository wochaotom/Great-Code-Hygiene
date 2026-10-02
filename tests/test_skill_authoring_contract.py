from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TRAINER_ROOT = REPO_ROOT / "code-hygiene-compounder"
REFERENCES = TRAINER_ROOT / "references"
SKILL_FILES = (
    REPO_ROOT / "code-hygiene" / "SKILL.md",
    REPO_ROOT / "code-hygiene-skeleton" / "SKILL.md",
    TRAINER_ROOT / "SKILL.md",
    REPO_ROOT / "code-hygiene-compounder-claude-ai" / "code-hygiene-compounder" / "SKILL.md",
)
# Claude reads only the start of a long reference file before deciding whether to
# read the rest, so files past this length must open with a contents list.
CONTENTS_REQUIRED_AFTER_LINES = 100
CONTENTS_HEADING_WINDOW = 20

sys.path.insert(0, str(TRAINER_ROOT / "scripts"))
from export_claude_package import CLAUDE_SKILL_DESCRIPTION  # noqa: E402


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    _, block, _ = text.split("---", 2)
    fields: dict[str, str] = {}
    for line in block.strip().splitlines():
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields


def section(text: str, heading: str) -> str:
    return text.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]


class SkillAuthoringContractTests(unittest.TestCase):
    def test_long_reference_files_open_with_contents(self) -> None:
        for path in sorted(REFERENCES.rglob("*.md")):
            lines = path.read_text(encoding="utf-8").splitlines()
            if len(lines) <= CONTENTS_REQUIRED_AFTER_LINES:
                continue
            with self.subTest(path=path.relative_to(REPO_ROOT).as_posix()):
                self.assertIn("## Contents", lines[:CONTENTS_HEADING_WINDOW])

    def test_contents_lists_every_section(self) -> None:
        for name in ("eval-prompts.md", "source-registry.md"):
            text = (REFERENCES / name).read_text(encoding="utf-8")
            contents = section(text, "Contents")
            for heading in re.findall(r"^## (.+)$", text, flags=re.MULTILINE):
                if heading != "Contents":
                    with self.subTest(file=name, heading=heading):
                        self.assertIn(f"- {heading}:", contents)

    def test_training_lesson_contents_lists_each_lesson_once(self) -> None:
        text = (REFERENCES / "training-lessons.md").read_text(encoding="utf-8")
        contents = section(text, "Contents")
        listed = [
            title.strip()
            for line in contents.splitlines()
            if line.startswith("- ")
            for title in line.split(":", 1)[1].split(";")
        ]
        lessons = [
            re.sub(r"^\d{4}-\d{2}-\d{2}: ", "", heading)
            for heading in re.findall(r"^## (.+)$", text, flags=re.MULTILINE)
            if heading != "Contents"
        ]
        self.assertEqual(sorted(listed), sorted(lessons))

    def test_skill_frontmatter_meets_agent_skill_limits(self) -> None:
        for path in SKILL_FILES:
            fields = frontmatter(path)
            with self.subTest(path=path.relative_to(REPO_ROOT).as_posix()):
                self.assertRegex(fields["name"], r"^[a-z0-9-]{1,64}$")
                self.assertNotRegex(fields["name"], r"anthropic|claude")
                self.assertTrue(fields["description"])
                self.assertLessEqual(len(fields["description"]), 1024)
                self.assertNotRegex(fields["description"], r"<[^>]+>")
                self.assertIn("Use ", fields["description"])
                body = path.read_text(encoding="utf-8").split("---", 2)[2]
                self.assertLess(len(body.splitlines()), 500)

    def test_claude_ai_upload_description_fits_upload_limit(self) -> None:
        self.assertLessEqual(len(CLAUDE_SKILL_DESCRIPTION), 200)

    def test_workflows_return_to_constrain_when_verification_fails(self) -> None:
        for path in (REPO_ROOT / "code-hygiene" / "SKILL.md", TRAINER_ROOT / "SKILL.md"):
            text = " ".join(path.read_text(encoding="utf-8").split())
            with self.subTest(path=path.relative_to(REPO_ROOT).as_posix()):
                self.assertIn("Hygiene progress:", text)
                self.assertIn("If a check fails, return to Constrain", text)

    def test_every_surface_reruns_failed_checks_before_reporting(self) -> None:
        surfaces = (
            REPO_ROOT / "code-hygiene" / "SKILL.md",
            TRAINER_ROOT / "SKILL.md",
            REFERENCES / "HYGIENE_QUICK.md",
            REPO_ROOT / ".cursor" / "rules" / "code-hygiene.mdc",
            REPO_ROOT / "code-hygiene-compounder-command" / ".claude" / "commands" / "code-hygiene.md",
            REPO_ROOT / "portable-prompts" / "code-hygiene-compounder-chat.md",
            *sorted((REPO_ROOT / "chatbot-profiles").glob("*-instructions.md")),
        )
        for path in surfaces:
            text = " ".join(path.read_text(encoding="utf-8").split())
            with self.subTest(path=path.relative_to(REPO_ROOT).as_posix()):
                self.assertIn("If a check fails", text)
                self.assertIn("re-run", text)


if __name__ == "__main__":
    unittest.main()
