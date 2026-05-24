#!/usr/bin/env python3
"""Check overtraining and bloat guardrails for the hygiene skill."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from fixture_runner import load_fixtures
from fixture_runner import validate_fixture
from pass100_runner import load_prompts


EXCLUDED_NAMES = {
    "runs",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".fixture-tmp",
    ".fixture-work",
    ".git",
}


def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8-sig").splitlines())


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_fingerprint(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    for current, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_NAMES]
        current_path = Path(current)
        for filename in filenames:
            path = current_path / filename
            relative = path.relative_to(root)
            if any(part in EXCLUDED_NAMES for part in relative.parts):
                continue
            files[relative.as_posix()] = file_digest(path)
    return files


class Reporter:
    def __init__(self) -> None:
        self.checks: list[dict] = []
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def record(self, name: str, status: str, detail: str, **values: object) -> None:
        item = {"name": name, "status": status, "detail": detail}
        item.update(values)
        self.checks.append(item)
        if status == "fail":
            self.errors.append(f"{name}: {detail}")
        elif status == "warn":
            self.warnings.append(f"{name}: {detail}")

    def pass_check(self, name: str, detail: str, **values: object) -> None:
        self.record(name, "pass", detail, **values)

    def fail_check(self, name: str, detail: str, **values: object) -> None:
        self.record(name, "fail", detail, **values)

    def warn_check(self, name: str, detail: str, **values: object) -> None:
        self.record(name, "warn", detail, **values)


def check_maximum(
    reporter: Reporter,
    name: str,
    value: int | float,
    maximum: int | float,
    unit: str,
) -> None:
    detail = f"{value:g} {unit}; limit {maximum:g}"
    if value > maximum:
        reporter.fail_check(name, detail, value=value, limit=maximum)
    else:
        reporter.pass_check(name, detail, value=value, limit=maximum)


def check_skill_size(skill_root: Path, args: argparse.Namespace, reporter: Reporter) -> None:
    skill_path = skill_root / "SKILL.md"
    if not skill_path.is_file():
        reporter.fail_check("active skill", "missing SKILL.md")
        return
    line_count = count_lines(skill_path)
    byte_count = skill_path.stat().st_size
    check_maximum(reporter, "SKILL.md line budget", line_count, args.max_skill_lines, "lines")
    check_maximum(reporter, "SKILL.md byte budget", byte_count, args.max_skill_bytes, "bytes")


def check_training_lessons(skill_root: Path, args: argparse.Namespace, reporter: Reporter) -> None:
    path = skill_root / "references" / "training-lessons.md"
    if not path.is_file():
        reporter.warn_check("training lessons", "missing training-lessons.md")
        return
    text = path.read_text(encoding="utf-8-sig")
    line_count = len(text.splitlines())
    sections = len(re.findall(r"^##\s+", text, flags=re.MULTILINE))
    check_maximum(
        reporter,
        "training lesson line budget",
        line_count,
        args.max_training_lesson_lines,
        "lines",
    )
    check_maximum(
        reporter,
        "training lesson section budget",
        sections,
        args.max_training_lesson_sections,
        "sections",
    )


def check_fixture_budget(skill_root: Path, args: argparse.Namespace, reporter: Reporter) -> None:
    suite = skill_root / "references" / "eval-prompts.md"
    fixtures_dir = skill_root / "fixtures"
    if not suite.is_file():
        reporter.fail_check("fixture coverage", "missing eval prompt suite")
        return
    prompt_ids = {prompt["id"] for prompt in load_prompts(suite)}
    fixtures = load_fixtures(fixtures_dir) if fixtures_dir.is_dir() else []
    errors: list[str] = []
    covered: set[str] = set()
    for fixture in fixtures:
        errors.extend(validate_fixture(fixture, prompt_ids))
        prompt_id = fixture.get("prompt_id")
        if isinstance(prompt_id, str):
            covered.add(prompt_id)
    if errors:
        reporter.fail_check("fixture metadata", "; ".join(errors[:5]), error_count=len(errors))
    else:
        reporter.pass_check("fixture metadata", f"{len(fixtures)} fixtures valid")

    check_maximum(reporter, "fixture count budget", len(fixtures), args.max_fixtures, "fixtures")
    coverage = len(covered) / len(prompt_ids) if prompt_ids else 0.0
    if coverage > args.max_fixture_coverage:
        reporter.fail_check(
            "fixture coverage budget",
            f"{coverage:.1%} of prompts have fixtures; limit {args.max_fixture_coverage:.1%}",
            value=coverage,
            limit=args.max_fixture_coverage,
        )
    else:
        reporter.pass_check(
            "fixture coverage budget",
            f"{coverage:.1%} of prompts have fixtures; limit {args.max_fixture_coverage:.1%}",
            value=coverage,
            limit=args.max_fixture_coverage,
        )


def check_script_budget(skill_root: Path, args: argparse.Namespace, reporter: Reporter) -> None:
    scripts_dir = skill_root / "scripts"
    scripts = sorted(path for path in scripts_dir.glob("*.py") if path.is_file())
    check_maximum(reporter, "script count budget", len(scripts), args.max_scripts, "scripts")
    oversized = [
        f"{path.name}:{count_lines(path)}"
        for path in scripts
        if count_lines(path) > args.max_script_lines
    ]
    if oversized:
        reporter.fail_check(
            "script line budget",
            "oversized scripts: " + ", ".join(oversized),
            limit=args.max_script_lines,
        )
    else:
        reporter.pass_check(
            "script line budget",
            f"all scripts within {args.max_script_lines} lines",
            limit=args.max_script_lines,
        )


def check_source_budget(skill_root: Path, args: argparse.Namespace, reporter: Reporter) -> None:
    packs = sorted((skill_root / "references" / "source-packs").glob("*.md"))
    check_maximum(reporter, "source pack budget", len(packs), args.max_source_packs, "source packs")


def check_generated_noise(skill_root: Path, reporter: Reporter) -> None:
    bad_files: list[str] = []
    bad_dirs: list[str] = []
    for current, dirnames, filenames in os.walk(skill_root):
        current_path = Path(current)
        for dirname in list(dirnames):
            if dirname in {".fixture-tmp", ".fixture-work", "__pycache__", ".pytest_cache", ".mypy_cache"}:
                bad_dirs.append((current_path / dirname).relative_to(skill_root).as_posix())
        dirnames[:] = [name for name in dirnames if name not in EXCLUDED_NAMES]
        for filename in filenames:
            if any(fnmatch.fnmatch(filename, pattern) for pattern in ("*.zip", "*.pyc", "*.pyo")):
                bad_files.append((current_path / filename).relative_to(skill_root).as_posix())
    if bad_files or bad_dirs:
        detail = "; ".join(
            item
            for item in (
                "files: " + ", ".join(sorted(bad_files)) if bad_files else "",
                "dirs: " + ", ".join(sorted(bad_dirs)) if bad_dirs else "",
            )
            if item
        )
        reporter.fail_check("generated noise", detail)
    else:
        reporter.pass_check("generated noise", "no generated files or scratch directories inside skill root")


def check_installed_sync(
    skill_root: Path,
    installed_root: Path | None,
    require: bool,
    reporter: Reporter,
) -> None:
    if installed_root is None:
        return
    if not installed_root.exists():
        status = "fail" if require else "warn"
        reporter.record("installed skill sync", status, f"installed skill missing: {installed_root}")
        return
    source = tree_fingerprint(skill_root)
    installed = tree_fingerprint(installed_root)
    missing = sorted(set(source) - set(installed))
    extra = sorted(set(installed) - set(source))
    changed = sorted(path for path in set(source) & set(installed) if source[path] != installed[path])
    if missing or extra or changed:
        detail = (
            f"missing={len(missing)}, extra={len(extra)}, changed={len(changed)}"
        )
        status = "fail" if require else "warn"
        reporter.record(
            "installed skill sync",
            status,
            detail,
            missing=missing[:20],
            extra=extra[:20],
            changed=changed[:20],
        )
    else:
        reporter.pass_check("installed skill sync", f"matches {installed_root}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check overtraining and bloat guardrails.")
    parser.add_argument("--skill-root", type=Path, default=Path.cwd())
    parser.add_argument("--installed-skill-root", type=Path)
    parser.add_argument("--require-installed-sync", action="store_true")
    parser.add_argument("--max-skill-lines", type=int, default=180)
    parser.add_argument("--max-skill-bytes", type=int, default=16000)
    parser.add_argument("--max-training-lesson-lines", type=int, default=350)
    parser.add_argument("--max-training-lesson-sections", type=int, default=70)
    parser.add_argument("--max-fixtures", type=int, default=10)
    parser.add_argument("--max-fixture-coverage", type=float, default=0.25)
    parser.add_argument("--max-scripts", type=int, default=12)
    parser.add_argument("--max-script-lines", type=int, default=450)
    parser.add_argument("--max-source-packs", type=int, default=25)
    parser.add_argument("--json", action="store_true")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    skill_root = args.skill_root.resolve()
    reporter = Reporter()

    check_skill_size(skill_root, args, reporter)
    check_training_lessons(skill_root, args, reporter)
    check_fixture_budget(skill_root, args, reporter)
    check_script_budget(skill_root, args, reporter)
    check_source_budget(skill_root, args, reporter)
    check_generated_noise(skill_root, reporter)
    check_installed_sync(
        skill_root,
        args.installed_skill_root.resolve() if args.installed_skill_root else None,
        args.require_installed_sync,
        reporter,
    )

    payload = {
        "valid": not reporter.errors,
        "skill_root": str(skill_root),
        "checks": reporter.checks,
        "errors": reporter.errors,
        "warnings": reporter.warnings,
    }
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        status = "valid" if payload["valid"] else "invalid"
        print(f"Overtraining guardrails: {status}")
        for check in reporter.checks:
            print(f"[{check['status']}] {check['name']}: {check['detail']}")
    if reporter.errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
