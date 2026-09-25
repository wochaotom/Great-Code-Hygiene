from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
README_PATH = REPO_ROOT / "README.md"
README = README_PATH.read_text(encoding="utf-8")
POWER_USERS = (REPO_ROOT / "docs" / "power-users.md").read_text(encoding="utf-8")

MARKDOWN_DESTINATION = re.compile(r"\]\(([^)\s]+)(?:\s+[^)]*)?\)")


def markdown_lines_outside_fences(markdown: str) -> list[str]:
    lines: list[str] = []
    fence_char = ""
    fence_length = 0

    for line in markdown.splitlines():
        fence = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if fence and not fence_char:
            marker = fence.group(1)
            fence_char = marker[0]
            fence_length = len(marker)
            continue

        if fence and fence_char and fence.group(1)[0] == fence_char:
            closing = rf"^\s{{0,3}}{re.escape(fence_char)}{{{fence_length},}}\s*$"
            if re.match(closing, line):
                fence_char = ""
                fence_length = 0
            continue

        if not fence_char:
            lines.append(line)

    return lines


def github_heading_anchors(markdown: str) -> set[str]:
    anchors: set[str] = set()
    duplicates: dict[str, int] = {}

    for line in markdown_lines_outside_fences(markdown):
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if not match:
            continue

        heading = re.sub(r"<[^>]+>", "", match.group(1))
        slug = re.sub(r"[^\w\- ]", "", heading.lower())
        slug = re.sub(r"\s+", "-", slug.strip())
        occurrence = duplicates.get(slug, 0)
        duplicates[slug] = occurrence + 1
        anchors.add(slug if occurrence == 0 else f"{slug}-{occurrence}")

    return anchors


def markdown_section(markdown: str, heading: str, next_heading: str) -> str:
    lines = markdown_lines_outside_fences(markdown)
    if heading not in lines:
        raise AssertionError(f"heading {heading!r} not found in visible markdown")
    start = lines.index(heading) + 1
    if next_heading not in lines[start:]:
        raise AssertionError(
            f"next heading {next_heading!r} not found after {heading!r}"
        )
    end = lines.index(next_heading, start)
    return "\n".join(lines[start:end])


def local_link_errors(markdown: str, source_path: Path) -> list[str]:
    errors: list[str] = []
    visible_markdown = "\n".join(markdown_lines_outside_fences(markdown))

    for destination in MARKDOWN_DESTINATION.findall(visible_markdown):
        if destination.startswith(("http://", "https://", "mailto:")):
            continue

        path_text, _, fragment = destination.partition("#")
        target = source_path if not path_text else source_path.parent / path_text.replace("%20", " ")

        if not target.exists():
            errors.append(f"missing target: {destination}")
            continue

        if fragment and target.is_file() and target.suffix.lower() == ".md":
            anchors = github_heading_anchors(target.read_text(encoding="utf-8"))
            if fragment not in anchors:
                errors.append(f"missing anchor: {destination}")

    return errors


class ReadmeContractTests(unittest.TestCase):
    def test_markdown_helpers_ignore_fenced_examples(self) -> None:
        markdown = """# Visible

```bash
# Hidden heading
[Missing example](missing-example.md)
```

[Existing anchor](#why-it-exists)
"""

        self.assertEqual({"visible"}, github_heading_anchors(markdown))
        self.assertEqual([], local_link_errors(markdown, README_PATH))

    def test_heading_slugger_preserves_unicode_letters(self) -> None:
        heading = "## R\N{LATIN SMALL LETTER E WITH ACUTE}sum\N{LATIN SMALL LETTER E WITH ACUTE} \N{CJK UNIFIED IDEOGRAPH-65E5}\N{CJK UNIFIED IDEOGRAPH-672C}"
        expected = "r\N{LATIN SMALL LETTER E WITH ACUTE}sum\N{LATIN SMALL LETTER E WITH ACUTE}-\N{CJK UNIFIED IDEOGRAPH-65E5}\N{CJK UNIFIED IDEOGRAPH-672C}"

        self.assertEqual({expected}, github_heading_anchors(heading))

    def test_markdown_section_matches_heading_lines_only(self) -> None:
        markdown = """Mention `## Section` in prose.

## Section

kept

## Next
"""

        self.assertEqual("\nkept\n", markdown_section(markdown, "## Section", "## Next"))
        with self.assertRaisesRegex(AssertionError, "heading '## Missing' not found"):
            markdown_section(markdown, "## Missing", "## Next")

    def test_readme_explains_the_complete_runtime_workflow(self) -> None:
        required_headings = (
            "## How Great Code Hygiene Works",
            "### 1. Activation",
            "### 2. Grounding",
            "### 3. Deterministic Feedback Loop",
            "### 4. Scoped Change",
            "### 5. Risk-Driven Hardening",
            "### 6. Verification",
            "### 7. Evidence Report",
            "## Evidence Model",
            "## How the Full Trainer Compounds",
        )

        for heading in required_headings:
            with self.subTest(heading=heading):
                self.assertIn(heading, README)

    def test_readme_defines_use_and_non_use_boundaries(self) -> None:
        use_section = markdown_section(README, "## When to Use It", "## When Not to Use It")
        non_use_section = markdown_section(
            README, "## When Not to Use It", "## How Great Code Hygiene Works"
        )

        for task in ("code review", "bug fixes", "refactors", "package", "documentation"):
            with self.subTest(section="use", task=task):
                self.assertIn(task, use_section.lower())

        for boundary in (
            "formatting-only",
            "compiler or type checker",
            "dedicated security review",
            "full trainer for routine code changes",
            "do not use pass-100",
        ):
            with self.subTest(section="non-use", boundary=boundary):
                self.assertIn(boundary, non_use_section.lower())

    def test_readme_distinguishes_all_three_editions(self) -> None:
        for edition in ("code-hygiene", "code-hygiene-compounder", "code-hygiene-skeleton"):
            with self.subTest(edition=edition):
                self.assertIn(f"`{edition}`", README)
        self.assertIn("function-only", README.lower())
        self.assertIn("does not train itself", README.lower())
        self.assertIn("blank starting point", README.lower())

    def test_readme_preserves_manually_verified_install_commands(self) -> None:
        required_commands = (
            "npx skills@latest add wochaotom/Great-Code-Hygiene --skill code-hygiene --agent claude-code --global --yes",
            "npx skills@latest add wochaotom/Great-Code-Hygiene --skill code-hygiene --agent codex --global --yes",
            "npx skills@latest add wochaotom/Great-Code-Hygiene --skill code-hygiene --agent cursor --global --yes",
            "npx skills@latest add wochaotom/Great-Code-Hygiene --skill code-hygiene --agent antigravity --global --yes",
            "npx skills@latest add wochaotom/Great-Code-Hygiene --skill code-hygiene-compounder --agent <agent> --global --yes",
            "npx skills@latest add wochaotom/Great-Code-Hygiene --skill code-hygiene-skeleton --agent <agent> --global --yes",
            "codex plugin marketplace add wochaotom/Great-Code-Hygiene",
            "codex plugin add code-hygiene-compounder@great-code-hygiene",
            "/plugin marketplace add wochaotom/Great-Code-Hygiene",
            "/plugin install code-hygiene-compounder@great-code-hygiene",
        )

        for command in required_commands:
            with self.subTest(command=command):
                self.assertIn(command, README)

    def test_readme_local_links_and_anchors_resolve(self) -> None:
        self.assertEqual([], local_link_errors(README, README_PATH))

    def test_power_user_guide_local_links_and_anchors_resolve(self) -> None:
        power_user_path = REPO_ROOT / "docs" / "power-users.md"
        self.assertEqual([], local_link_errors(POWER_USERS, power_user_path))

    def test_readme_documents_every_trainer_script(self) -> None:
        script_dir = REPO_ROOT / "code-hygiene-compounder" / "scripts"
        script_names = sorted(
            path.relative_to(script_dir).as_posix()
            for path in script_dir.glob("*.py")
            if not any(
                part.startswith("_") for part in path.relative_to(script_dir).parts
            )
        )
        script_section = markdown_section(
            POWER_USERS, "### What the Scripts Automate", "## Chatbot Profiles"
        )

        for script_name in script_names:
            with self.subTest(script=script_name):
                self.assertIn(f"`{script_name}`", script_section)

    def test_power_user_guide_preserves_manually_verified_removal_commands(self) -> None:
        required_commands = (
            "npx skills@latest remove code-hygiene --global --yes",
            "npx skills@latest remove code-hygiene-compounder --global --yes",
            "npx skills@latest remove code-hygiene-skeleton --global --yes",
            "codex plugin remove code-hygiene-compounder@great-code-hygiene",
            "claude plugin uninstall code-hygiene-compounder@great-code-hygiene",
        )

        for command in required_commands:
            with self.subTest(command=command):
                self.assertIn(command, POWER_USERS)

    def test_power_user_guide_documents_cli_help_checks(self) -> None:
        required_help_commands = (
            "npx skills@latest --help",
            "npx skills@latest remove --help",
            "codex plugin add --help",
            "codex plugin remove --help",
            "codex plugin marketplace remove --help",
            "claude plugin install --help",
            "claude plugin uninstall --help",
            "claude plugin marketplace remove --help",
        )

        for command in required_help_commands:
            with self.subTest(command=command):
                self.assertIn(command, POWER_USERS)


if __name__ == "__main__":
    unittest.main()
