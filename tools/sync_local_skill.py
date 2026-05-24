#!/usr/bin/env python3
"""Safely sync the canonical repo skill into the local Codex skills directory."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True


EXCLUDED_NAMES = {
    "runs",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".fixture-tmp",
    ".fixture-work",
    ".git",
}
SKILL_NAME = "code-hygiene-compounder"


def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_fingerprint(root: Path) -> dict[str, str]:
    files: dict[str, str] = {}
    if not root.exists():
        return files
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(root)
        if any(part in EXCLUDED_NAMES for part in relative.parts):
            continue
        files[relative.as_posix()] = file_digest(path)
    return files


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def default_repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_installed_root() -> Path:
    return Path.home() / ".codex" / "skills" / SKILL_NAME


def validate_paths(source: Path, target: Path) -> list[str]:
    errors: list[str] = []
    if not (source / "SKILL.md").is_file():
        errors.append(f"source missing SKILL.md: {source}")
    if source.name != SKILL_NAME:
        errors.append(f"source directory must be named {SKILL_NAME}: {source}")
    if target.name != SKILL_NAME:
        errors.append(f"target directory must be named {SKILL_NAME}: {target}")
    expected_parent = Path.home() / ".codex" / "skills"
    try:
        target_parent = target.parent.resolve(strict=False)
    except OSError:
        target_parent = target.parent
    if target_parent != expected_parent.resolve(strict=False):
        errors.append(f"target parent must be {expected_parent}: {target_parent}")
    if source.resolve(strict=False) == target.resolve(strict=False):
        errors.append("source and target must be different directories")
    if is_relative_to(target.resolve(strict=False), source.resolve(strict=False)):
        errors.append("target must not be inside source")
    return errors


def compare_trees(source: Path, target: Path) -> dict:
    source_files = tree_fingerprint(source)
    target_files = tree_fingerprint(target)
    missing = sorted(set(source_files) - set(target_files))
    extra = sorted(set(target_files) - set(source_files))
    changed = sorted(
        path for path in set(source_files) & set(target_files) if source_files[path] != target_files[path]
    )
    return {
        "in_sync": not missing and not extra and not changed,
        "source_file_count": len(source_files),
        "target_file_count": len(target_files),
        "missing": missing,
        "extra": extra,
        "changed": changed,
    }


def copy_tree(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for child in target.iterdir():
        if child.name in EXCLUDED_NAMES:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    for child in source.iterdir():
        if child.name in EXCLUDED_NAMES:
            continue
        destination = target / child.name
        if child.is_dir():
            shutil.copytree(child, destination, ignore=shutil.ignore_patterns(*EXCLUDED_NAMES))
        else:
            shutil.copy2(child, destination)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sync canonical Code Hygiene skill into local Codex skills.")
    parser.add_argument("--repo-root", type=Path, default=default_repo_root())
    parser.add_argument("--installed-root", type=Path, default=default_installed_root())
    parser.add_argument("--apply", action="store_true", help="Write the sync. Omit for dry-run comparison.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    source = (args.repo_root / SKILL_NAME).resolve()
    target = args.installed_root.resolve(strict=False)

    errors = validate_paths(source, target)
    before = compare_trees(source, target)
    applied = False
    after = before
    if not errors and args.apply and not before["in_sync"]:
        copy_tree(source, target)
        applied = True
        after = compare_trees(source, target)

    payload = {
        "valid": not errors and after["in_sync"],
        "applied": applied,
        "source": str(source),
        "target": str(target),
        "errors": errors,
        "before": {
            **before,
            "missing": before["missing"][:20],
            "extra": before["extra"][:20],
            "changed": before["changed"][:20],
        },
        "after": {
            **after,
            "missing": after["missing"][:20],
            "extra": after["extra"][:20],
            "changed": after["changed"][:20],
        },
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if errors or not after["in_sync"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
