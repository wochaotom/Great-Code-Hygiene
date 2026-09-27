#!/usr/bin/env python3
"""Export the current Codex skill as a Claude package."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path

from internal.package_meta import EXCLUDED_NAMES
from internal.package_meta import SKILL_NAME
from internal.package_meta import PACKAGE_DIRS
from internal.evidence import unsafe_link

CLAUDE_SKILL_DESCRIPTION = (
    "Improve, review, refactor, harden, test, and evaluate code hygiene with "
    "PASS-100 scoring and source-grounded compounding."
)
PORTABLE_PROMPT_NAME = "code-hygiene-compounder-chat.md"
EXPORT_MARKER = ".great-code-hygiene-export.json"


COMMAND_TEXT = """# Code Hygiene Compounder

Use the bundled code hygiene workflow to improve, review, refactor, harden, test, or evaluate code. Treat `.claude/code-hygiene-compounder` as the local reference package.

First read repo instructions:
1. Read `CLAUDE.md`, `AGENTS.md`, and nearby package/module instructions when present.
2. Repo instructions and explicit user requests override this command.
3. Preserve user edits and local conventions.

Default to audit mode:
1. For review/audit requests, do not edit files.
2. For implementation requests, inspect first and state the smallest viable change before editing.
3. If the request is ambiguous, propose the edit and wait for approval before changing files.

Follow this hygiene loop:
1. For ordinary code work, read `.claude/code-hygiene-compounder/references/HYGIENE_QUICK.md`.
2. Ground in relevant code, tests, types, manifests, docs, and existing patterns; for bounded scratch, fixture, export, or subdirectory tasks, scope status, diff, and discovery commands to that target.
3. For bugs, regressions, or flaky behavior, build the smallest deterministic feedback loop that reproduces the symptom before fixing, or state what blocked that loop.
4. Make the smallest behavior-correct change; avoid unrelated rewrites, formatting churn, and dependency changes.
5. Check tests, security, error paths, observability, dependencies, and local conventions.
6. Verify with meaningful commands and include the evidence report from `.claude/code-hygiene-compounder/references/evidence-report.md` before claiming completion.
7. Do not trust agent reports, generated summaries, or intermediate files as proof; inspect the final user-facing artifact and verification output.
8. Score significant work with PASS-100 when requested or when compounding a lesson.
9. For broad training or scoring work, use `.claude/code-hygiene-compounder/references/context-index.json` as a router for smaller reference reads, not as a replacement for required source packs.
10. Use source-grounded honing only when requested; then read every activated source pack and validate the honing report before promotion.
11. Capture durable lessons and only promote instruction updates through the compound loop.

Read these files when needed:
- `.claude/code-hygiene-compounder/references/HYGIENE_QUICK.md`
- `.claude/code-hygiene-compounder/references/context-index.json`
- `.claude/code-hygiene-compounder/references/evidence-report.md`
- `.claude/code-hygiene-compounder/references/PASS-100.md`
- `.claude/code-hygiene-compounder/references/eval-prompts.md`
- `.claude/code-hygiene-compounder/references/compound-loop.md`
- `.claude/code-hygiene-compounder/references/research-canon.md`
- `.claude/code-hygiene-compounder/references/source-grounded-honing.md`
- `.claude/code-hygiene-compounder/references/training-lessons.md`
"""

PORTABLE_PROMPT_INTRO = """# Code Hygiene Compounder Portable Chat Prompt

Generated from the canonical `code-hygiene-compounder` skill bundle by `scripts/export_claude_package.py --format portable-prompt`.
Paste this into a chat-only LLM when the local Codex or Claude skill system is unavailable.

## Role

You are a code hygiene reviewer and implementation partner. Your job is to make code safer, smaller, more testable, easier to review, and better integrated with the local system.

## Chat-Only Limits

A chat-only model may simulate review, scoring, critique, and lesson extraction, but must not imply local file edits, script execution, test results, package exports, or verified runtime behavior without tool evidence or user-provided command output.

## Operating Rules

1. Inspect the existing code, tests, docs, manifests, and local conventions before recommending changes.
2. For bugs, regressions, or flaky behavior, build the smallest deterministic feedback loop that reproduces the symptom before fixing. Prefer a focused test, CLI/script harness, UI automation, replayed fixture, or captured trace over manual inspection.
3. If no deterministic loop is possible, state what was tried and what artifact, access, or environment is missing.
4. Prefer the smallest behavior-correct change. Avoid unrelated rewrites, broad formatting churn, and needless dependencies.
5. Check correctness, tests, security, data safety, error handling, observability, docs, compatibility, and local integration.
6. Never claim completion or passing status without fresh verification evidence. If you cannot run checks, say exactly that.
7. Preserve user edits. Do not revert unrelated changes.
8. When reviewing only, do not edit; report findings first, ordered by severity with file and line references when available.
9. For source-grounded honing, tie lessons to concrete failures or authoritative principles, not personal preference.

## Verification-Before-Completion Gate

NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE.

Before claiming any status or expressing satisfaction:

1. IDENTIFY: What command or evidence proves this claim?
2. RUN: Execute the full command fresh when tools are available. If tools are unavailable, request the needed output or state that verification is pending.
3. READ: Inspect the full output, including exit code, failures, warnings, and skipped checks.
4. VERIFY: Does the output confirm the claim?
   - If NO: State actual status with evidence.
   - If YES: State the claim with evidence.
5. ONLY THEN: Make the claim.

Skip any step = not verified. Do not treat prior runs, agent reports, generated summaries, or partial checks as proof.
"""


def reject_export_links(root: Path) -> None:
    if unsafe_link(root) or not root.is_dir():
        raise ValueError(f"unsafe export link or missing directory: {root}")

    def fail(error: OSError) -> None:
        raise error

    for current, dirs, files in os.walk(root, onerror=fail):
        for name in dirs + files:
            path = Path(current) / name
            if unsafe_link(path):
                raise ValueError(f"unsafe export link: {path}")


def copy_tree(src: Path, dest: Path, extra_excludes: tuple[str, ...] = ()) -> None:
    reject_export_links(src)
    if dest.exists():
        shutil.rmtree(dest)
    source_root = src.resolve(strict=True)

    def ignored(directory: str, names: list[str]) -> set[str]:
        excluded = {name.casefold() for name in EXCLUDED_NAMES}
        if Path(directory).resolve(strict=True) == source_root:
            excluded.update(name.casefold() for name in extra_excludes)
        return {name for name in names if name.casefold() in excluded}

    shutil.copytree(src, dest, symlinks=True, ignore=ignored)
    reject_export_links(dest)


def zip_dir(src: Path, zip_path: Path, prefix: str = "") -> None:
    reject_export_links(src)
    if zip_path.exists():
        zip_path.unlink()
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(src.rglob("*"), key=lambda item: item.relative_to(src).as_posix()):
            relative_path = path.relative_to(src)
            if path.is_file() and relative_path.as_posix() != EXPORT_MARKER and not any(part.casefold() in EXCLUDED_NAMES for part in relative_path.parts):
                if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
                    raise ValueError(f"unsafe export link: {path}")
                archive_name = (Path(prefix) / relative_path).as_posix() if prefix else relative_path.as_posix()
                info = zipfile.ZipInfo(archive_name, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 3
                info.external_attr = 0o644 << 16
                archive.writestr(info, path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def read_skill_text(skill_root: Path) -> str:
    reject_export_links(skill_root)
    text = (skill_root / "SKILL.md").read_text(encoding="utf-8-sig")
    if not text.startswith("---\n"):
        raise SystemExit("SKILL.md missing YAML frontmatter")
    try:
        _, frontmatter, body = text.split("---", 2)
    except ValueError as exc:
        raise SystemExit("SKILL.md frontmatter is not closed") from exc

    frontmatter_lines: list[str] = []
    seen_name = False
    seen_description = False
    for line in frontmatter.splitlines():
        if line.startswith("name:"):
            frontmatter_lines.append(f"name: {SKILL_NAME}")
            seen_name = True
        elif line.startswith("description:"):
            frontmatter_lines.append(f"description: {CLAUDE_SKILL_DESCRIPTION}")
            seen_description = True
        elif line.strip():
            frontmatter_lines.append(line)
    if not seen_name:
        frontmatter_lines.insert(0, f"name: {SKILL_NAME}")
    if not seen_description:
        frontmatter_lines.append(f"description: {CLAUDE_SKILL_DESCRIPTION}")
    return "---\n" + "\n".join(frontmatter_lines) + "\n---" + body


def read_reference(skill_root: Path, relative: str) -> str:
    return (skill_root / relative).read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()


def remove_top_heading(text: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("# "):
        return "\n".join(lines[1:]).strip()
    return text.strip()


def build_portable_prompt(skill_root: Path) -> str:
    reject_export_links(skill_root)
    sections = [
        PORTABLE_PROMPT_INTRO.strip(),
        "## Hygiene Quick Entry\n\n" + remove_top_heading(read_reference(skill_root, "references/HYGIENE_QUICK.md")),
        "## PASS-100\n\n" + remove_top_heading(read_reference(skill_root, "references/PASS-100.md")),
        "## Hygiene Principles\n\n" + remove_top_heading(read_reference(skill_root, "references/hygiene-principles.md")),
        "## Training Lessons\n\n" + remove_top_heading(read_reference(skill_root, "references/training-lessons.md")),
    ]
    return "\n\n".join(sections).strip() + "\n"


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def validate_export_paths(skill_root: Path, package_root: Path, zip_path: Path) -> None:
    skill_root = skill_root.resolve(strict=True)
    package_root = package_root.resolve(strict=False)
    zip_path = zip_path.resolve(strict=False)
    if package_root == skill_root or is_relative_to(package_root, skill_root) or is_relative_to(skill_root, package_root):
        raise SystemExit("refusing to export Claude package inside or over the skill root")
    if is_relative_to(zip_path, skill_root):
        raise SystemExit("refusing to write Claude zip inside the skill root")


def export_inventory(root: Path) -> dict:
    reject_export_links(root)
    return {
        "directories": sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_dir()),
        "files": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file() and path.relative_to(root).as_posix() != EXPORT_MARKER
        },
    }


def prepare_export_root(package_root: Path, zip_path: Path) -> None:
    if not package_root.exists():
        return
    marker = package_root / EXPORT_MARKER
    try:
        recorded = json.loads(marker.read_text(encoding="utf-8"))
        inventory = export_inventory(package_root)
        if {key: recorded.get(key) for key in inventory} != inventory:
            raise ValueError("export contents changed")
        if zip_path.exists() and recorded.get("archive_sha256") != hashlib.sha256(zip_path.read_bytes()).hexdigest():
            raise ValueError("export archive changed or is not owned")
    except (OSError, ValueError) as exc:
        raise SystemExit(f"refusing to replace unowned or modified export: {package_root}: {exc}") from exc
    shutil.rmtree(package_root)


def mark_export_root(package_root: Path, zip_path: Path | None = None) -> None:
    marker = export_inventory(package_root)
    if zip_path is not None:
        marker["archive_sha256"] = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    (package_root / EXPORT_MARKER).write_text(json.dumps(marker, sort_keys=True), encoding="utf-8")


def validate_prompt_export_path(skill_root: Path, prompt_path: Path) -> None:
    skill_root = skill_root.resolve(strict=True)
    prompt_path = prompt_path.resolve(strict=False)
    if is_relative_to(prompt_path, skill_root):
        raise SystemExit("refusing to write portable prompt inside the skill root")


def copy_supporting_files(skill_root: Path, dest: Path) -> None:
    copy_tree(skill_root / "references", dest / "references")
    copy_tree(skill_root / "scripts", dest / "scripts")
    fixtures = skill_root / "fixtures"
    if fixtures.exists():
        copy_tree(fixtures, dest / "fixtures")


def install_text(mode: str) -> str:
    if mode == "claude-code-skill":
        text = (
            "Copy the .claude folder from this package into your Claude Code project or home configuration.\n"
            "Then invoke /code-hygiene-compounder or let Claude Code load the skill automatically when relevant.\n"
        )
    elif mode == "claude-ai-skill":
        text = (
            "Upload this zip to Claude as a custom skill. The zip contains the code-hygiene-compounder skill directory.\n"
        )
    else:
        text = (
            "Legacy command package. Copy the .claude folder into your Claude Code project or home configuration.\n"
            "Then run /code-hygiene when you want the workflow.\n"
        )
    return text


def write_install(path: Path, mode: str) -> None:
    path.write_text(install_text(mode), encoding="utf-8", newline="\n")


def export_claude_code_skill(skill_root: Path, package_root: Path) -> None:
    skill_dest = package_root / ".claude" / "skills" / SKILL_NAME
    skill_dest.mkdir(parents=True, exist_ok=True)
    (skill_dest / "SKILL.md").write_text(read_skill_text(skill_root), encoding="utf-8", newline="\n")
    copy_supporting_files(skill_root, skill_dest)
    write_install(package_root / "INSTALL.txt", "claude-code-skill")


def export_claude_ai_skill(skill_root: Path, package_root: Path) -> None:
    skill_dest = package_root / SKILL_NAME
    skill_dest.mkdir(parents=True, exist_ok=True)
    (skill_dest / "SKILL.md").write_text(read_skill_text(skill_root), encoding="utf-8", newline="\n")
    copy_supporting_files(skill_root, skill_dest)


def export_legacy_command(skill_root: Path, package_root: Path) -> None:
    command_dir = package_root / ".claude" / "commands"
    reference_dest = package_root / ".claude" / SKILL_NAME / "references"
    script_dest = package_root / ".claude" / SKILL_NAME / "scripts"
    fixture_dest = package_root / ".claude" / SKILL_NAME / "fixtures"
    command_dir.mkdir(parents=True, exist_ok=True)
    reference_dest.parent.mkdir(parents=True, exist_ok=True)

    (command_dir / "code-hygiene.md").write_text(COMMAND_TEXT, encoding="utf-8", newline="\n")
    copy_tree(skill_root / "references", reference_dest)
    copy_tree(skill_root / "scripts", script_dest)
    fixtures = skill_root / "fixtures"
    if fixtures.exists():
        copy_tree(fixtures, fixture_dest)
    write_install(package_root / "INSTALL.txt", "legacy-command")


def export_portable_prompt(skill_root: Path, out_dir: Path) -> None:
    prompt_path = out_dir / PORTABLE_PROMPT_NAME
    validate_prompt_export_path(skill_root, prompt_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(build_portable_prompt(skill_root), encoding="utf-8", newline="\n")
    print(f"Wrote {prompt_path}")


def sync_repo(repo_root: Path) -> None:
    """Refresh tracked distribution copies from the canonical trainer skill."""
    source = repo_root / PACKAGE_DIRS["codex_skill"]
    plugin = repo_root / PACKAGE_DIRS["codex_plugin_skill"]
    claude_ai = repo_root / PACKAGE_DIRS["claude_ai_skill"]
    command = repo_root / PACKAGE_DIRS["claude_command_package"]
    if not source.is_dir() or not (repo_root / ".claude-plugin" / "marketplace.json").is_file() or not (repo_root / "plugins" / SKILL_NAME / ".codex-plugin" / "plugin.json").is_file():
        raise SystemExit("repository or marketplace paths are incomplete")
    reject_export_links(source)
    directory_targets = [plugin, claude_ai, command]
    directory_targets.extend(destination / name for destination in (claude_ai, command) for name in ("references", "scripts", "fixtures"))
    file_targets = [
        claude_ai / "SKILL.md",
        repo_root / "code-hygiene-compounder-command" / ".claude" / "commands" / "code-hygiene.md",
        repo_root / "portable-prompts" / PORTABLE_PROMPT_NAME,
    ]
    if unsafe_link(repo_root):
        raise ValueError(f"unsafe sync root link: {repo_root}")
    for target in directory_targets + file_targets:
        try:
            relative = target.relative_to(repo_root)
        except ValueError as exc:
            raise ValueError(f"sync target outside repository: {target}") from exc
        ancestor = repo_root
        for part in relative.parts:
            ancestor /= part
            if unsafe_link(ancestor):
                raise ValueError(f"unsafe sync target link: {ancestor}")
        if target.exists() and target in directory_targets:
            reject_export_links(target)
        if target.exists() and target in file_targets and not target.is_file():
            raise ValueError(f"sync target is not a file: {target}")
    copy_tree(source, plugin, extra_excludes=(".claude-plugin",))
    claude_ai.mkdir(parents=True, exist_ok=True)
    (claude_ai / "SKILL.md").write_text(read_skill_text(source), encoding="utf-8", newline="\n")
    for name in ("references", "scripts", "fixtures"):
        copy_tree(source / name, claude_ai / name)
        copy_tree(source / name, command / name)
    (repo_root / "code-hygiene-compounder-command" / ".claude" / "commands" / "code-hygiene.md").write_text(COMMAND_TEXT, encoding="utf-8", newline="\n")
    portable = repo_root / "portable-prompts" / PORTABLE_PROMPT_NAME
    portable.write_text(build_portable_prompt(source), encoding="utf-8", newline="\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a Claude package from this Codex skill.")
    parser.add_argument("--skill-root", type=Path)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--sync-repo", type=Path, help="Refresh only tracked distribution copies in this repository.")
    parser.add_argument(
        "--format",
        choices=["claude-code-skill", "claude-ai-skill", "legacy-command", "portable-prompt"],
        default="claude-code-skill",
        help="Package or prompt layout to export. Default is the modern Claude Code skill layout.",
    )
    parser.add_argument("--zip-name", default="claude-code-hygiene-compounder.zip")
    args = parser.parse_args()

    if args.sync_repo:
        if args.skill_root or args.out_dir:
            parser.error("--sync-repo cannot be combined with --skill-root or --out-dir")
        sync_repo(args.sync_repo.resolve())
        print(f"Synced tracked editions in {args.sync_repo}")
        return
    if not args.skill_root or not args.out_dir:
        parser.error("--skill-root and --out-dir are required for exports")
    reject_export_links(args.skill_root)

    if args.format == "portable-prompt":
        export_portable_prompt(args.skill_root, args.out_dir)
        return

    zip_name = Path(args.zip_name)
    if zip_name.name != args.zip_name or zip_name.suffix.lower() != ".zip" or not zip_name.stem:
        parser.error("--zip-name must be a simple .zip filename")
    package_root = args.out_dir / zip_name.stem
    zip_path = args.out_dir / args.zip_name
    validate_export_paths(args.skill_root, package_root, zip_path)
    if unsafe_link(zip_path) or (zip_path.exists() and not package_root.exists()):
        raise SystemExit(f"refusing to replace unowned export archive: {zip_path}")
    prepare_export_root(package_root, zip_path)
    if args.format == "claude-code-skill":
        export_claude_code_skill(args.skill_root, package_root)
    elif args.format == "claude-ai-skill":
        export_claude_ai_skill(args.skill_root, package_root)
    else:
        export_legacy_command(args.skill_root, package_root)

    mark_export_root(package_root)
    zip_dir(package_root, zip_path)
    mark_export_root(package_root, zip_path)
    print(f"Wrote {zip_path}")


if __name__ == "__main__":
    main()
