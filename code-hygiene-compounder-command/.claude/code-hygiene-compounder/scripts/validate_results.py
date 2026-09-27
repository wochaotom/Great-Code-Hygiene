#!/usr/bin/env python3
"""Validate PASS-100 result JSON before scoring, analysis, or promotion."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean

from internal.policy import CATEGORY_KEYS
from internal.policy import RUBRIC_CAPS
from internal.policy import finite_number
from internal.json_integrity import loads_strict

sys.dont_write_bytecode = True

from pass100_runner import RUN_TYPE_EVIDENCE
from pass100_runner import load_prompts


ALLOWED_RUN_TYPES = set(RUN_TYPE_EVIDENCE)
SOURCE_ID_FALLBACKS = {"eval-failure"}


def nonfinite_paths(value: object, path: str = "") -> list[str]:
    if isinstance(value, float) and not math.isfinite(value):
        return [f"{path} must be finite"]
    if isinstance(value, dict):
        return [error for key, child in value.items() for error in nonfinite_paths(child, f"{path}.{key}" if path else str(key))]
    if isinstance(value, list):
        return [error for index, child in enumerate(value) for error in nonfinite_paths(child, f"{path}[{index}]")]
    return []


def load_json(path: Path) -> dict:
    try:
        data = loads_strict(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    return data


def load_known_prompt_ids(suite: Path | None) -> set[str] | None:
    if suite is None:
        return None
    return {prompt["id"] for prompt in load_prompts(suite)}


def load_source_ids(path: Path | None) -> set[str] | None:
    if path is None or not path.exists():
        return None
    try:
        payload = loads_strict(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"{path}: invalid source weights JSON: {exc}") from exc
    weights = payload.get("weights")
    if not isinstance(weights, list):
        raise SystemExit(f"{path}: source weights must contain a weights array")
    ids = {
        item.get("id")
        for item in weights
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id")
    }
    if not ids:
        raise SystemExit(f"{path}: no source ids found")
    return ids | SOURCE_ID_FALLBACKS


def default_source_weights(results_path: Path) -> Path | None:
    for parent in [results_path.resolve().parent, *results_path.resolve().parents]:
        candidate = parent / "references" / "source-weights.json"
        if candidate.exists():
            return candidate
    return None


def is_non_empty_string(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_string_list(value: object, label: str, errors: list[str], allow_empty: bool = True) -> None:
    if not isinstance(value, list):
        errors.append(f"{label} must be an array")
        return
    if not allow_empty and not value:
        errors.append(f"{label} must be a non-empty array")
    for index, item in enumerate(value):
        if not is_non_empty_string(item):
            errors.append(f"{label}[{index}] must be a non-empty string")


def parse_iso8601(value: object, label: str, errors: list[str]) -> datetime | None:
    if value is None:
        return None
    if not is_non_empty_string(value):
        errors.append(f"{label} must be an ISO-8601 string when present")
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{label} must be an ISO-8601 timestamp")
        return None


def validate_source_anchors(
    value: object,
    label: str,
    source_ids: set[str] | None,
    errors: list[str],
) -> int:
    if value is None:
        return 0
    if not isinstance(value, list):
        errors.append(f"{label} must be an array when present")
        return 0
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{label}[{index}] must be an object")
            continue
        source_id = item.get("source_id")
        principle = item.get("principle")
        evidence = item.get("evidence")
        if not is_non_empty_string(source_id):
            errors.append(f"{label}[{index}].source_id is required")
        elif source_ids is not None and source_id not in source_ids:
            errors.append(f"{label}[{index}].source_id is unknown: {source_id}")
        if not is_non_empty_string(principle):
            errors.append(f"{label}[{index}].principle is required")
        if not is_non_empty_string(evidence):
            errors.append(f"{label}[{index}].evidence is required")
    return len(value)


def validate_optional_number(
    item: dict,
    key: str,
    label: str,
    errors: list[str],
    integer: bool = False,
) -> None:
    if key not in item:
        return
    value = item[key]
    if not finite_number(value, integer=integer, nonnegative=True):
        kind = "non-negative integer" if integer else "non-negative number"
        errors.append(f"{label}.{key} must be a {kind}")


def validate_score_item(
    item: object,
    index: int,
    declared_prompt_ids: set[str],
    known_prompt_ids: set[str] | None,
    source_ids: set[str] | None,
    schema_version: int = 1,
) -> tuple[str | None, float | None, dict[str, float]]:
    errors: list[str] = []
    label = f"scores[{index}]"
    if not isinstance(item, dict):
        errors.append(f"{label} must be an object")
        return None, None, {"_errors": errors}  # type: ignore[dict-item]

    prompt_id = item.get("prompt_id")
    if not is_non_empty_string(prompt_id):
        errors.append(f"{label}.prompt_id is required")
        prompt_id = None
    else:
        if prompt_id not in declared_prompt_ids:
            errors.append(f"{label}.prompt_id is not listed in prompt_ids: {prompt_id}")
        if known_prompt_ids is not None and prompt_id not in known_prompt_ids:
            errors.append(f"{label}.prompt_id is not in the prompt suite: {prompt_id}")

    categories = item.get("categories")
    category_values: dict[str, float] = {}
    if not isinstance(categories, dict):
        errors.append(f"{label}.categories must be an object")
    else:
        missing = sorted(set(CATEGORY_KEYS) - set(categories))
        extra = sorted(set(categories) - set(CATEGORY_KEYS))
        if missing:
            errors.append(f"{label}.categories missing: {', '.join(missing)}")
        if extra:
            errors.append(f"{label}.categories has unknown keys: {', '.join(extra)}")
        for key, maximum in CATEGORY_KEYS.items():
            value = categories.get(key)
            if not finite_number(value):
                errors.append(f"{label}.categories.{key} must be numeric")
                continue
            if value < 0 or value > maximum:
                errors.append(f"{label}.categories.{key}={value} outside 0..{maximum}")
            category_values[key] = float(value)

    total = item.get("total")
    numeric_total: float | None = None
    if not finite_number(total):
        errors.append(f"{label}.total must be numeric")
    else:
        numeric_total = float(total)
        if numeric_total < 0 or numeric_total > 100:
            errors.append(f"{label}.total={total} outside 0..100")
        subtotal = sum(category_values.values())
        tolerance = 1e-9 if schema_version == 2 else 0.01
        if len(category_values) == len(CATEGORY_KEYS) and abs(numeric_total - subtotal) > tolerance:
            errors.append(f"{label}.total {total} does not match category sum {subtotal:g}")

    deductions = item.get("deductions")
    lessons = item.get("lessons")
    validate_string_list(deductions, f"{label}.deductions", errors)
    validate_string_list(lessons, f"{label}.lessons", errors)
    if numeric_total is not None and numeric_total < 100:
        if not isinstance(deductions, list) or not deductions:
            errors.append(f"{label}.deductions must explain any score below 100")
    if schema_version == 2:
        flags = item.get("rubric_flags")
        if not isinstance(flags, dict) or set(flags) != set(RUBRIC_CAPS):
            errors.append(f"{label}.rubric_flags must declare every rubric cap")
        elif any(not isinstance(flag, bool) for flag in flags.values()):
            errors.append(f"{label}.rubric_flags values must be boolean")
        elif numeric_total is not None:
            active_caps = [limit for key, limit in RUBRIC_CAPS.items() if flags[key]]
            if active_caps and numeric_total > min(active_caps):
                errors.append(f"{label}.total exceeds triggered rubric cap {min(active_caps)}")

    anchor_count = validate_source_anchors(
        item.get("source_anchors"),
        f"{label}.source_anchors",
        source_ids,
        errors,
    )
    if isinstance(lessons, list) and lessons and anchor_count == 0:
        errors.append(f"{label}.source_anchors must be present when lessons are recorded")

    artifacts = item.get("artifacts")
    if artifacts is not None:
        validate_string_list(artifacts, f"{label}.artifacts", errors)
    if "resolved" in item and not isinstance(item["resolved"], bool):
        errors.append(f"{label}.resolved must be boolean when present")
    for key in ("duration_ms", "cost_usd"):
        validate_optional_number(item, key, label, errors)
    for key in ("input_tokens", "output_tokens"):
        validate_optional_number(item, key, label, errors, integer=True)

    if errors:
        category_values["_errors"] = errors  # type: ignore[assignment]
    return prompt_id if isinstance(prompt_id, str) else None, numeric_total, category_values


def validate_payload(
    payload: dict,
    known_prompt_ids: set[str] | None = None,
    source_ids: set[str] | None = None,
) -> tuple[list[str], list[str]]:
    errors: list[str] = nonfinite_paths(payload)
    warnings: list[str] = []
    schema_version = payload.get("schema_version", 1)
    if schema_version not in (1, 2) or isinstance(schema_version, bool):
        errors.append("schema_version must be 1 or 2")
        schema_version = 1

    if not is_non_empty_string(payload.get("run_id")):
        errors.append("run_id must be a non-empty string")
    run_type = payload.get("run_type")
    if run_type not in ALLOWED_RUN_TYPES:
        errors.append(f"run_type must be one of: {', '.join(sorted(ALLOWED_RUN_TYPES))}")
    phase = payload.get("phase")
    if not isinstance(phase, int) or isinstance(phase, bool) or phase < 0:
        errors.append("phase must be a non-negative integer")

    declared = payload.get("prompt_ids")
    if not isinstance(declared, list) or not declared:
        errors.append("prompt_ids must be a non-empty array")
        declared_prompt_ids: set[str] = set()
    else:
        validate_string_list(declared, "prompt_ids", errors, allow_empty=False)
        declared_prompt_ids = {item for item in declared if isinstance(item, str)}
        if len(declared_prompt_ids) != len(declared):
            errors.append("prompt_ids must be unique")
        if known_prompt_ids is not None:
            unknown = sorted(declared_prompt_ids - known_prompt_ids)
            if unknown:
                errors.append("prompt_ids not in prompt suite: " + ", ".join(unknown))

    scores = payload.get("scores")
    if not isinstance(scores, list) or not scores:
        errors.append("scores must be a non-empty array")
        scores = []

    score_prompt_ids: set[str] = set()
    totals: list[float] = []
    for index, item in enumerate(scores):
        prompt_id, total, category_values = validate_score_item(
            item,
            index,
            declared_prompt_ids,
            known_prompt_ids,
            source_ids,
            schema_version,
        )
        item_errors = category_values.pop("_errors", [])
        errors.extend(item_errors)
        if prompt_id:
            if prompt_id in score_prompt_ids:
                errors.append(f"scores[{index}].prompt_id is duplicated: {prompt_id}")
            score_prompt_ids.add(prompt_id)
        if total is not None:
            totals.append(total)

    if declared_prompt_ids and score_prompt_ids != declared_prompt_ids:
        missing = sorted(declared_prompt_ids - score_prompt_ids)
        extra = sorted(score_prompt_ids - declared_prompt_ids)
        if missing:
            errors.append("scores missing prompt_ids: " + ", ".join(missing))
        if extra:
            errors.append("scores include undeclared prompt_ids: " + ", ".join(extra))

    started = parse_iso8601(payload.get("started_at"), "started_at", errors)
    completed = parse_iso8601(payload.get("completed_at"), "completed_at", errors)
    if started and completed and completed < started:
        errors.append("completed_at must not be earlier than started_at")

    if run_type == "model-execution":
        if not is_non_empty_string(payload.get("model")):
            warnings.append("model-execution runs should record model")
        if not is_non_empty_string(payload.get("skill_version")):
            warnings.append("model-execution runs should record skill_version")
    if schema_version == 2:
        for key in ("target_id", "arm", "model", "harness"):
            if not is_non_empty_string(payload.get(key)):
                errors.append(f"{key} is required for v2 results")
        if payload.get("arm") not in ("baseline", "candidate"):
            errors.append("arm must be baseline or candidate")
        trial = payload.get("trial")
        if not isinstance(trial, int) or isinstance(trial, bool) or trial < 1:
            errors.append("trial must be a positive integer")
        if not isinstance(payload.get("runtime"), dict):
            errors.append("runtime identity is required for v2 results")
        if started is None or completed is None:
            errors.append("started_at and completed_at are required for v2 results")

    if totals:
        average = mean(totals)
        if average >= 95 and any(
            isinstance(item, dict) and item.get("deductions") for item in scores
        ):
            warnings.append("average is very high; confirm deductions are reflected in totals")

    return errors, warnings


def validation_summary(
    path: Path,
    payload: dict,
    errors: list[str],
    warnings: list[str],
) -> dict:
    scores = payload.get("scores")
    score_items = scores if isinstance(scores, list) else []
    totals = [
        float(item["total"])
        for item in score_items
        if isinstance(item, dict) and finite_number(item.get("total"))
    ]
    return {
        "result": str(path),
        "valid": not errors,
        "run_id": payload.get("run_id"),
        "run_type": payload.get("run_type"),
        "phase": payload.get("phase"),
        "count": len(scores) if isinstance(scores, list) else 0,
        "average": round(mean(totals), 2) if totals else None,
        "errors": errors,
        "warnings": warnings,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate PASS-100 result JSON.")
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--suite", type=Path)
    parser.add_argument("--source-weights", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--json", action="store_true", help="Print full JSON summary.")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    payload = load_json(args.results)
    suite_ids = load_known_prompt_ids(args.suite) if args.suite else None
    source_weights = args.source_weights
    if source_weights is None:
        source_weights = default_source_weights(args.results)
    source_ids = load_source_ids(source_weights)
    errors, warnings = validate_payload(payload, suite_ids, source_ids)
    summary = validation_summary(args.results, payload, errors, warnings)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    if args.json or errors or warnings:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"PASS-100 result validation: valid ({summary['count']} scores)")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
