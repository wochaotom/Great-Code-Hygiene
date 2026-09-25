#!/usr/bin/env python3
"""PASS-100 batch and scoring helper."""

from __future__ import annotations

import argparse
import json
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean

from internal.policy import CATEGORY_KEYS
from internal.policy import CRITICAL_CATEGORIES
from internal.policy import PROMOTION_THRESHOLD
from internal.policy import finite_number

PROMPT_RE = re.compile(r"^\s*(\d+)\.\s+\*\*(HYG-\d{3}):\*\*\s+(.*)$")


RUN_TYPE_EVIDENCE = {
    "audit-backed": {
        "level": "self-reported",
        "note": (
            "Audit-backed PASS-100 scores are structured judgment from observed work. "
            "Use them for lessons and triage, not as objective benchmark proof."
        ),
        "major_promotion_evidence": False,
    },
    "script-only": {
        "level": "harness-only",
        "note": (
            "Script-only PASS-100 scores validate scoring artifacts and gates. "
            "They do not measure model code quality."
        ),
        "major_promotion_evidence": False,
    },
    "model-execution": {
        "level": "model-output",
        "note": (
            "Model-execution PASS-100 scores evaluate actual model outputs. "
            "They are stronger evidence when prompts, outputs, deductions, and judge reasoning are logged."
        ),
        "major_promotion_evidence": True,
    },
}

DEFAULT_EVIDENCE = {
    "level": "unknown",
    "note": (
        "Unknown PASS-100 run type. Do not treat this score as promotion evidence until "
        "the run type and evidence source are classified."
    ),
    "major_promotion_evidence": False,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_prompts(path: Path) -> list[dict]:
    prompts: list[dict] = []
    category = "Uncategorized"
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.startswith("## "):
            category = line[3:].strip()
            continue
        match = PROMPT_RE.match(line)
        if match:
            prompts.append(
                {
                    "number": int(match.group(1)),
                    "id": match.group(2),
                    "category": category,
                    "prompt": match.group(3).strip(),
                }
            )
    if not prompts:
        raise SystemExit(f"No HYG prompts found in {path}")
    return prompts


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def cmd_list(args: argparse.Namespace) -> None:
    prompts = load_prompts(args.suite)
    categories: dict[str, int] = {}
    for prompt in prompts:
        categories[prompt["category"]] = categories.get(prompt["category"], 0) + 1
    payload = {"count": len(prompts), "categories": categories}
    print(json.dumps(payload, indent=2, sort_keys=True))


def select_batch(prompts: list[dict], mode: str, seed: int | None, limit: int | None,
                 categories: list[str] | None = None, failure_ids: set[str] | None = None) -> list[dict]:
    if mode == "full":
        selected = prompts
    elif mode == "smoke":
        groups: dict[str, list[dict]] = {}
        for prompt in prompts:
            groups.setdefault(prompt["category"], []).append(prompt)
        rng = random.Random(seed)
        for group in groups.values():
            if seed is not None:
                rng.shuffle(group)
        selected = []
        while len(selected) < min(10, len(prompts)):
            added = False
            for group in groups.values():
                if group and len(selected) < min(10, len(prompts)):
                    selected.append(group.pop(0))
                    added = True
            if not added:
                break
    elif mode == "focused":
        if not categories:
            raise SystemExit("focused mode requires --category")
        unknown = set(categories) - {prompt["category"] for prompt in prompts}
        if unknown:
            raise SystemExit("unknown categories: " + ", ".join(sorted(unknown)))
        selected = [prompt for prompt in prompts if prompt["category"] in categories]
    elif mode == "regression":
        if not failure_ids:
            raise SystemExit("regression mode requires --failure-history")
        selected = [prompt for prompt in prompts if prompt["id"] in failure_ids]
        if len(selected) != len(failure_ids):
            raise SystemExit("failure history contains unknown prompt ids")
    elif mode == "sample":
        rng = random.Random(seed)
        count = limit or min(25, len(prompts))
        selected = rng.sample(prompts, min(count, len(prompts)))
    else:
        raise SystemExit(f"Unknown mode: {mode}")
    if limit and mode != "sample":
        selected = selected[:limit]
    return selected


def load_failure_ids(path: Path, threshold: float = PROMOTION_THRESHOLD) -> set[str]:
    from validate_results import load_json, validate_payload

    try:
        history = load_json(path)
    except SystemExit as exc:
        raise SystemExit(f"invalid failure history: {exc}") from exc
    if "aggregate" in history:
        aggregate = history.get("aggregate")
        if history.get("valid") is not True or not isinstance(aggregate, dict):
            raise SystemExit("failure history analysis must be valid")
        records = aggregate.get("low_scores")
    else:
        errors, _ = validate_payload(history)
        if errors:
            raise SystemExit("failure history result is invalid: " + "; ".join(errors))
        records = history.get("scores")
    if not isinstance(records, list):
        raise SystemExit("failure history must contain recorded scores")
    failures = {
        item["prompt_id"]
        for item in records
        if isinstance(item, dict) and isinstance(item.get("prompt_id"), str)
        and finite_number(item.get("total")) and item["total"] < threshold
    }
    if not failures:
        raise SystemExit("failure history has no recorded low scores")
    return failures


def cmd_batch(args: argparse.Namespace) -> None:
    prompts = load_prompts(args.suite)
    failure_ids = load_failure_ids(args.failure_history) if args.failure_history else None
    selected = select_batch(prompts, args.mode, args.seed, args.limit, args.category, failure_ids)
    payload = {
        "batch_id": args.batch_id or f"{args.mode}-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "created_at": utc_now(),
        "mode": args.mode,
        "suite": str(args.suite),
        "count": len(selected),
        "prompts": selected,
    }
    write_json(args.out, payload)
    print(f"Wrote {len(selected)} prompts to {args.out}")


def validate_score(item: dict) -> list[str]:
    warnings: list[str] = []
    if not isinstance(item, dict):
        return ["score item must be an object"]
    categories = item.get("categories", {})
    if not isinstance(categories, dict):
        return ["categories must be an object"]
    subtotal = 0
    for key, maximum in CATEGORY_KEYS.items():
        value = categories.get(key)
        if not finite_number(value):
            warnings.append(f"missing numeric category: {key}")
            continue
        if value < 0 or value > maximum:
            warnings.append(f"{key}={value} outside 0..{maximum}")
        subtotal += value
    total = item.get("total")
    if not finite_number(total):
        warnings.append("missing numeric total")
    elif abs(total - subtotal) > 0.01:
        warnings.append(f"total {total} does not match category sum {subtotal}")
    return warnings


def cmd_score(args: argparse.Namespace) -> None:
    from validate_results import validate_payload
    from validate_results import load_json

    raw = load_json(args.results)
    errors, _ = validate_payload(raw)
    if errors:
        raise SystemExit("invalid results: " + "; ".join(errors))
    scores = raw.get("scores", [])
    if not isinstance(scores, list) or not scores:
        raise SystemExit("results JSON must contain a non-empty scores array")

    warnings: list[dict] = []
    totals: list[float] = []
    category_values: dict[str, list[float]] = {key: [] for key in CATEGORY_KEYS}
    for item in scores:
        item_warnings = validate_score(item)
        if item_warnings:
            prompt_id = item.get("prompt_id") if isinstance(item, dict) else None
            warnings.append({"prompt_id": prompt_id, "warnings": item_warnings})
        if not isinstance(item, dict):
            continue
        if finite_number(item.get("total")):
            totals.append(float(item["total"]))
        categories = item.get("categories", {})
        if not isinstance(categories, dict):
            categories = {}
        for key in CATEGORY_KEYS:
            value = categories.get(key)
            if finite_number(value):
                category_values[key].append(float(value))

    if not totals:
        raise SystemExit("no numeric total values found in scores")

    average = mean(totals)
    category_averages = {
        key: round(mean(values), 2) if values else None for key, values in category_values.items()
    }
    critical_regression = any(
        category_averages[key] is not None and category_averages[key] < CATEGORY_KEYS[key] * 0.7
        for key in CRITICAL_CATEGORIES
    )
    run_type = raw.get("run_type", "unspecified")
    evidence = RUN_TYPE_EVIDENCE.get(run_type, DEFAULT_EVIDENCE)
    evidence_warning = {
        "run_type": run_type,
        "evidence_level": evidence["level"],
        "major_promotion_evidence": evidence["major_promotion_evidence"],
        "note": evidence["note"],
    }
    payload = {
        "scored_at": utc_now(),
        "run_id": raw.get("run_id"),
        "run_type": run_type,
        "phase": raw.get("phase", 0),
        "count": len(scores),
        "average": round(average, 2),
        "minimum": round(min(totals), 2),
        "maximum": round(max(totals), 2),
        "category_averages": category_averages,
        "evidence_warning": evidence_warning,
        "warnings": warnings,
        "promotion_ready": False,
        "diagnostic_score_threshold_met": average >= args.threshold and not warnings and not critical_regression,
        "threshold": args.threshold,
    }
    write_json(args.out, payload)
    if args.log:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        with args.log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage PASS-100 prompt batches and scores.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="Summarize prompt suite.")
    list_parser.add_argument("--suite", type=Path, required=True)
    list_parser.set_defaults(func=cmd_list)

    batch_parser = subparsers.add_parser("batch", help="Write a prompt batch JSON file.")
    batch_parser.add_argument("--suite", type=Path, required=True)
    batch_parser.add_argument("--mode", choices=["smoke", "focused", "regression", "full", "sample"], required=True)
    batch_parser.add_argument("--out", type=Path, required=True)
    batch_parser.add_argument("--batch-id")
    batch_parser.add_argument("--seed", type=int)
    batch_parser.add_argument("--limit", type=int)
    batch_parser.add_argument("--category", action="append", help="Required in focused mode; repeatable exact category name.")
    batch_parser.add_argument("--failure-history", type=Path, help="Valid result or analysis JSON with recorded low scores for regression mode.")
    batch_parser.set_defaults(func=cmd_batch)

    score_parser = subparsers.add_parser("score", help="Score a PASS-100 results JSON file.")
    score_parser.add_argument("--results", type=Path, required=True)
    score_parser.add_argument("--out", type=Path, required=True)
    score_parser.add_argument("--log", type=Path)
    score_parser.add_argument("--threshold", type=float, default=PROMOTION_THRESHOLD)
    score_parser.set_defaults(func=cmd_score)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
