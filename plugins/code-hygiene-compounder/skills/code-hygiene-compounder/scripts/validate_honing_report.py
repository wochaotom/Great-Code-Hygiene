#!/usr/bin/env python3
"""Validate source-grounded honing reports before promotion."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ALLOWED_DECISIONS = {"promote", "reject", "needs-more-evidence"}


def is_non_empty_string_list(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and bool(item.strip()) for item in value
    )


def is_string_list(value: object) -> bool:
    return isinstance(value, list) and all(
        isinstance(item, str) and bool(item.strip()) for item in value
    )


def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    return data


def validate_report(report: dict, strict: bool = True) -> list[str]:
    errors: list[str] = []
    if report.get("run_type") != "source-grounded":
        errors.append("run_type must be 'source-grounded'")

    activated = report.get("activated_sources")
    if not isinstance(activated, list) or not activated:
        errors.append("activated_sources must be a non-empty array")
        activated_ids: set[str] = set()
    else:
        activated_ids = {item for item in activated if isinstance(item, str) and item}
        if len(activated_ids) != len(activated):
            errors.append("activated_sources must contain only non-empty strings")

    principles = report.get("principles_checked")
    if not is_non_empty_string_list(principles):
        errors.append("principles_checked must be a non-empty array of non-empty strings")

    checklist_results = report.get("checklist_results")
    if not isinstance(checklist_results, list) or not checklist_results:
        errors.append("checklist_results must be a non-empty array")
    else:
        result_ids: set[str] = set()
        for index, item in enumerate(checklist_results):
            if not isinstance(item, dict):
                errors.append(f"checklist_results[{index}] must be an object")
                continue
            source_id = item.get("source_id")
            if not isinstance(source_id, str) or not source_id:
                errors.append(f"checklist_results[{index}].source_id must be a non-empty string")
                continue
            if source_id not in activated_ids:
                errors.append(f"checklist_results[{index}].source_id is not activated: {source_id}")
            if source_id in result_ids:
                errors.append(f"checklist_results[{index}].source_id is duplicated: {source_id}")
            result_ids.add(source_id)
            checked = item.get("checked")
            if not is_non_empty_string_list(checked):
                errors.append(
                    f"checklist_results[{index}].checked must be a non-empty array of non-empty strings"
                )
            findings = item.get("findings")
            deductions = item.get("deductions")
            if findings is not None and not is_string_list(findings):
                errors.append(
                    f"checklist_results[{index}].findings must be an array of non-empty strings when present"
                )
            if deductions is not None and not is_string_list(deductions):
                errors.append(
                    f"checklist_results[{index}].deductions must be an array of non-empty strings when present"
                )
        missing = sorted(activated_ids - result_ids)
        if missing:
            errors.append(f"missing checklist_results for activated sources: {', '.join(missing)}")

    score = report.get("pass100_score")
    if not isinstance(score, (int, float)) or score < 0 or score > 100:
        errors.append("pass100_score must be a number from 0 to 100")

    decision = report.get("promotion_decision")
    if decision not in ALLOWED_DECISIONS:
        errors.append("promotion_decision must be promote, reject, or needs-more-evidence")

    lessons = report.get("lessons")
    if lessons is None:
        errors.append("lessons must be present, use [] when there are no lessons")
    elif not isinstance(lessons, list):
        errors.append("lessons must be an array")
    elif strict and decision == "promote":
        if not lessons:
            errors.append("promote decisions require at least one source-backed lesson")
        for index, lesson in enumerate(lessons):
            if not isinstance(lesson, dict):
                errors.append(f"lessons[{index}] must be an object")
                continue
            source_id = lesson.get("source_id")
            if not isinstance(source_id, str) or not source_id.strip():
                errors.append(f"lessons[{index}].source_id is required")
            elif source_id not in activated_ids:
                errors.append(f"lessons[{index}].source_id is not activated: {source_id}")
            if not isinstance(lesson.get("principle"), str) or not lesson["principle"].strip():
                errors.append(f"lessons[{index}].principle is required")
            if not isinstance(lesson.get("evidence"), str) or not lesson["evidence"].strip():
                errors.append(f"lessons[{index}].evidence is required")

    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a source-grounded honing report.")
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--lenient", action="store_true", help="Allow promote reports with no lessons.")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    report = load_json(args.report)
    errors = validate_report(report, strict=not args.lenient)
    payload = {
        "report": str(args.report),
        "valid": not errors,
        "errors": errors,
        "activated_source_count": len(report.get("activated_sources", []))
        if isinstance(report.get("activated_sources"), list)
        else 0,
    }
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
