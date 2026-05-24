#!/usr/bin/env python3
"""Build a source-grounded honing checklist from source weights and packs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from difflib import get_close_matches
from pathlib import Path


ACTIVATION_MAP = {
    "general": set(),
    "review": set(),
    "test": set(),
    "tests": set(),
    "legacy": set(),
    "docs": {"developer_documentation"},
    "documentation": {"developer_documentation"},
    "developer-docs": {"developer_documentation"},
    "readability": {"developer_documentation", "when_local_style_unclear"},
    "human-ergonomics": {"developer_documentation", "when_local_style_unclear"},
    "web": {"web_ui", "web_or_api_security"},
    "ui": {"web_ui"},
    "frontend": {"web_ui"},
    "api": {"rest_api", "web_or_api_security"},
    "http": {"http_protocol"},
    "http-protocol": {"http_protocol"},
    "headers": {"http_protocol"},
    "cookies": {"http_protocol"},
    "ai": {"llm_tool_schema"},
    "llm": {"llm_tool_schema"},
    "ai-sdk": {"llm_tool_schema"},
    "function-calling": {"llm_tool_schema"},
    "mcp": {"llm_tool_schema"},
    "provider-schema": {"llm_tool_schema"},
    "structured-output": {"llm_tool_schema"},
    "tool-schema": {"llm_tool_schema"},
    "security": {
        "security_core",
        "security_or_product_design",
        "security_or_release",
        "language_specific_or_security",
        "web_or_api_security",
    },
    "security-core": {"security_core"},
    "secure-coding": {"security_core", "language_specific_or_security"},
    "vulnerability": {"security_core", "security_or_release"},
    "config": {"config_or_deploy"},
    "deploy": {"config_or_deploy", "build_release_or_supply_chain"},
    "build": {"build_release_or_supply_chain"},
    "release": {"build_release_or_supply_chain", "security_or_release"},
    "supply-chain": {"build_release_or_supply_chain", "oss_or_dependency_risk"},
    "dependency": {"oss_or_dependency_risk"},
    "observability": {"observability"},
    "package": {"public_package_or_sdk"},
    "sdk": {"public_package_or_sdk"},
    "safety-critical": {"safety_critical_only"},
    "training": {"training_loop"},
    "training-loop": {"training_loop"},
    "python": {"python_language", "python_tests_or_package"},
    "py": {"python_language", "python_tests_or_package"},
    "pytest": {"python_tests_or_package"},
    "python-tests": {"python_tests_or_package"},
    "python-package": {"python_tests_or_package", "public_package_or_sdk"},
    "pyproject": {"python_tests_or_package", "build_release_or_supply_chain"},
}
CONTEXT_SKIP_NAMES = {"__pycache__", ".pytest_cache", ".mypy_cache", "runs", "context-index.json"}
CONTEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml"}
CONTEXT_GENERATED_AT = "1970-01-01T00:00:00+00:00"
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
WORD_RE = re.compile(r"\S+")
DOMAIN_RULES = (
    (("training-lessons.md", "compound-loop.md", "overtraining-guardrails.md", "PASS-100.md"), ("training", "promotion", "guardrails")),
    (("source-registry.md", "source-weights.json", "source-grounded-honing.md", "source-packs/"), ("source", "audit")),
    (("evidence-report.md", "PASS-100.md"), ("evidence", "verification")),
    (("eval-prompts.md", "fixtures", "matrix"), ("fixtures", "matrix")),
    (("HYGIENE_QUICK.md", "hygiene-principles.md", "SKILL.md"), ("daily-hygiene", "routing")),
)
ROLE_RULES = (
    ("SKILL.md", "active skill entrypoint and routing workflow"),
    ("HYGIENE_QUICK.md", "daily hygiene checklist"),
    ("evidence-report.md", "completion and verification report shape"),
    ("PASS-100.md", "PASS-100 scoring rubric"),
    ("eval-prompts.md", "PASS-100 prompt suite"),
    ("training-lessons.md", "promoted compact lessons"),
    ("source-registry.md", "authoritative source registry"),
    ("source-weights.json", "source activation weights"),
    ("source-packs/", "distilled source pack"),
    ("compound-loop.md", "training and promotion protocol"),
    ("overtraining-guardrails.md", "anti-overtraining checks"),
    ("hygiene-principles.md", "distilled operational principles"),
    ("research-canon.md", "research basis summary"),
)
READ_WHEN_RULES = (
    ("SKILL.md", ("starting broad training or export work", "checking active workflow routing")),
    ("HYGIENE_QUICK.md", ("ordinary code review, cleanup, hardening, or implementation",)),
    ("evidence-report.md", ("claiming completion", "recording verification evidence")),
    ("PASS-100.md", ("scoring or evaluating candidate work",)),
    ("eval-prompts.md", ("selecting PASS-100 prompts or checking fixture coverage",)),
    ("training-lessons.md", ("checking prior promoted lessons", "avoiding duplicate lessons")),
    ("source-registry.md", ("classifying or auditing sources",)),
    ("source-weights.json", ("activating source packs by domain",)),
    ("source-packs/", ("performing source-grounded scoring or honing",)),
    ("compound-loop.md", ("changing training, promotion, or compounding behavior",)),
    ("overtraining-guardrails.md", ("adding lessons, fixtures, sources, or training rules",)),
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            value.update(chunk)
    return value.hexdigest()


def context_values(relative: str, rules, default) -> list[str]:
    values: list[str] = []
    for needles, additions in rules:
        if any(needle in relative for needle in needles):
            values.extend(additions)
    return sorted(set(values or list(default)))


def context_role(relative: str) -> str:
    for needle, role in ROLE_RULES:
        if needle in relative:
            return role
    return "reference material"


def context_sections(text: str, domains: list[str]) -> list[dict]:
    headings = [(match.group(2).strip(), line_no) for line_no, line in enumerate(text.splitlines(), 1) if (match := HEADING_RE.match(line))]
    return [
        {
            "heading": heading,
            "lines": [start, headings[index + 1][1] - 1 if index + 1 < len(headings) else max(start, len(text.splitlines()))],
            "domains": domains,
        }
        for index, (heading, start) in enumerate(headings)
    ]


def build_context_index(skill_root: Path) -> dict:
    skill_root = skill_root.resolve()
    files: list[dict] = []
    paths = sorted(skill_root.rglob("*"), key=lambda candidate: candidate.relative_to(skill_root).as_posix())
    for path in paths:
        if not path.is_file() or path.suffix not in CONTEXT_SUFFIXES:
            continue
        relative_path = path.relative_to(skill_root)
        if any(part in CONTEXT_SKIP_NAMES for part in relative_path.parts):
            continue
        relative = relative_path.as_posix()
        if relative != "SKILL.md" and not relative.startswith("references/"):
            continue
        text = path.read_text(encoding="utf-8-sig")
        domains = context_values(relative, DOMAIN_RULES, ("reference",))
        files.append(
            {
                "path": relative,
                "role": context_role(relative),
                "domains": domains,
                "read_when": context_values(relative, READ_WHEN_RULES, ("the task directly names this file or domain",)),
                "sha256": digest(path),
                "lines": len(text.splitlines()),
                "words": len(WORD_RE.findall(text)),
                "sections": context_sections(text, domains),
            }
        )
    return {"version": "1", "generated_at": CONTEXT_GENERATED_AT, "root": skill_root.name, "files": files}


def context_index_errors(skill_root: Path, payload: dict) -> list[str]:
    expected = build_context_index(skill_root)
    required = {"SKILL.md", "references/training-lessons.md", "references/eval-prompts.md", "references/source-registry.md", "references/evidence-report.md"}
    actual_paths = {item.get("path") for item in payload.get("files", []) if isinstance(item, dict)}
    errors = []
    if payload != expected:
        errors.append("references/context-index.json is stale")
    missing = sorted(required - actual_paths)
    if missing:
        errors.append("missing required indexed paths: " + ", ".join(missing))
    return errors


def read_pack(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    title = path.stem
    checks: list[str] = []
    focus: list[str] = []
    section = None
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            section = line[3:].strip().lower()
        elif line.startswith("- ") and section == "distilled checks":
            checks.append(line[2:].strip())
        elif line.startswith("`") and section == "pass-100 focus":
            focus.extend(part.strip(" `") for part in line.split(","))
    return {"title": title, "checks": checks, "pass100_focus": [item for item in focus if item]}


def active_activation_values(domains: list[str]) -> set[str]:
    active = {"always"}
    for domain in domains:
        active.update(ACTIVATION_MAP.get(domain.lower(), set()))
    return active


def validate_domains(domains: list[str]) -> list[str]:
    errors: list[str] = []
    allowed = sorted(ACTIVATION_MAP)
    for domain in domains:
        normalized = domain.lower()
        if normalized in ACTIVATION_MAP:
            continue
        suggestion = get_close_matches(normalized, allowed, n=1)
        message = f"unknown domain: {domain}"
        if suggestion:
            message += f" (did you mean {suggestion[0]}?)"
        errors.append(message)
    return errors


def load_source_weights(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    weights = data.get("weights")
    if not isinstance(weights, list) or not weights:
        raise SystemExit(f"{path}: weights must be a non-empty array")
    required = {"id", "name", "default_weight", "activation", "scope"}
    for index, item in enumerate(weights):
        if not isinstance(item, dict):
            raise SystemExit(f"{path}: weights[{index}] must be an object")
        missing = sorted(required - item.keys())
        if missing:
            raise SystemExit(f"{path}: weights[{index}] missing required keys: {', '.join(missing)}")
    return weights


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a source-grounded audit plan.")
    parser.add_argument("--skill-root", type=Path, required=True)
    parser.add_argument("--domain", action="append", default=[], help="Task domain, repeatable.")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--context-index", action="store_true", help="Write the machine-readable context router instead of a source audit plan.")
    parser.add_argument("--check", action="store_true", help="With --context-index, fail if the existing index is stale.")
    args = parser.parse_args()

    if args.context_index:
        payload = build_context_index(args.skill_root)
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        if args.check:
            existing = args.out.read_text(encoding="utf-8-sig") if args.out.is_file() else None
            if existing != text:
                raise SystemExit(f"context index is stale: {args.out}")
            print(json.dumps({"valid": True, "path": str(args.out), "files": len(payload["files"])}, sort_keys=True))
            return
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
        print(json.dumps({"path": str(args.out), "files": len(payload["files"])}, sort_keys=True))
        return

    weights_path = args.skill_root / "references" / "source-weights.json"
    packs_dir = args.skill_root / "references" / "source-packs"
    domain_errors = validate_domains(args.domain)
    if domain_errors:
        allowed = ", ".join(sorted(ACTIVATION_MAP))
        raise SystemExit("; ".join(domain_errors) + f". Allowed domains: {allowed}")
    weights = load_source_weights(weights_path)
    activations = active_activation_values(args.domain)

    sources = []
    for item in weights:
        if item["activation"] not in activations:
            continue
        pack_path = packs_dir / f"{item['id']}.md"
        pack = read_pack(pack_path) if pack_path.exists() else {"title": item["name"], "checks": [], "pass100_focus": []}
        sources.append(
            {
                "id": item["id"],
                "name": item["name"],
                "weight": item["default_weight"],
                "activation": item["activation"],
                "scope": item["scope"],
                "pack": str(pack_path),
                "checks": pack["checks"],
                "pass100_focus": pack["pass100_focus"],
            }
        )

    payload = {
        "domains": args.domain,
        "activation_values": sorted(activations),
        "source_count": len(sources),
        "sources": sources,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(f"Wrote {len(sources)} active source packs to {args.out}")


if __name__ == "__main__":
    main()
