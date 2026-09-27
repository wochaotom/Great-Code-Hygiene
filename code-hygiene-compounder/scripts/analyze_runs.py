#!/usr/bin/env python3
"""Analyze valid PASS-100 runs with hard statistics and regression deltas."""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, stdev

sys.dont_write_bytecode = True

from pass100_runner import CATEGORY_KEYS
from validate_results import default_source_weights
from validate_results import load_json
from validate_results import load_known_prompt_ids
from validate_results import load_source_ids
from validate_results import validate_payload


CRITICAL_CATEGORIES = {"correctness", "tests", "security", "minimal_diff"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normal_mean_interval(values: list[float], lower_bound: float, upper_bound: float) -> dict:
    if not values:
        return {"low": None, "high": None, "method": "normal-approximation-95"}
    if len(values) == 1:
        return {"low": None, "high": None, "method": "insufficient-samples"}
    margin = 1.96 * stdev(values) / math.sqrt(len(values))
    return {
        "low": round(max(lower_bound, mean(values) - margin), 2),
        "high": round(min(upper_bound, mean(values) + margin), 2),
        "method": "normal-approximation-95",
    }


def wilson_interval(successes: int, count: int) -> dict:
    if count <= 1:
        return {"low": None, "high": None, "method": "insufficient-samples"}
    z = 1.96
    phat = successes / count
    denominator = 1 + z**2 / count
    center = (phat + z**2 / (2 * count)) / denominator
    margin = z * math.sqrt((phat * (1 - phat) + z**2 / (4 * count)) / count) / denominator
    return {
        "low": round(max(0.0, center - margin), 4),
        "high": round(min(1.0, center + margin), 4),
        "method": "wilson-95",
    }


def collect_scores(payloads: list[dict]) -> list[dict]:
    scores: list[dict] = []
    for payload in payloads:
        raw_scores = payload.get("scores", [])
        if isinstance(raw_scores, list):
            scores.extend(item for item in raw_scores if isinstance(item, dict))
    return scores


def summarize_scores(scores: list[dict], threshold: float) -> dict:
    totals = [float(item["total"]) for item in scores if isinstance(item.get("total"), (int, float))]
    category_values: dict[str, list[float]] = {key: [] for key in CATEGORY_KEYS}
    resolved_values: list[bool] = []
    for item in scores:
        categories = item.get("categories", {})
        if isinstance(categories, dict):
            for key in CATEGORY_KEYS:
                value = categories.get(key)
                if isinstance(value, (int, float)):
                    category_values[key].append(float(value))
        if isinstance(item.get("resolved"), bool):
            resolved_values.append(bool(item["resolved"]))

    passes = sum(1 for total in totals if total >= threshold)
    resolved_count = sum(1 for value in resolved_values if value)
    category_averages = {
        key: round(mean(values), 2) if values else None for key, values in category_values.items()
    }
    measures = {}
    for key in ("duration_ms", "input_tokens", "output_tokens", "cost_usd"):
        values = [item.get(key) for item in scores]
        complete = bool(values) and all(isinstance(value, (int, float)) and math.isfinite(value) and not isinstance(value, bool) for value in values)
        measures[key] = {"available": complete, "total": sum(values) if complete else None}
    category_confidence = {
        key: normal_mean_interval(values, 0.0, float(CATEGORY_KEYS[key]))
        for key, values in category_values.items()
    }
    return {
        "count": len(scores),
        "threshold": threshold,
        "average": round(mean(totals), 2) if totals else None,
        "minimum": round(min(totals), 2) if totals else None,
        "maximum": round(max(totals), 2) if totals else None,
        "mean_ci": normal_mean_interval(totals, 0.0, 100.0),
        "pass_count": passes,
        "pass_rate": round(passes / len(totals), 4) if totals else None,
        "pass_rate_ci": wilson_interval(passes, len(totals)),
        "resolved_count": resolved_count if resolved_values else None,
        "resolved_rate": round(resolved_count / len(resolved_values), 4) if resolved_values else None,
        "resolved_rate_ci": wilson_interval(resolved_count, len(resolved_values))
        if resolved_values
        else None,
        "category_averages": category_averages,
        "category_mean_ci": category_confidence,
        "measurements": measures,
        "low_scores": [
            {
                "prompt_id": item.get("prompt_id"),
                "total": item.get("total"),
                "deductions": item.get("deductions", []),
            }
            for item in scores
            if isinstance(item.get("total"), (int, float)) and float(item["total"]) < threshold
        ],
    }


def compare_summaries(current: dict, baseline: dict, margin: float) -> dict:
    regressions: list[dict] = []
    current_average = current.get("average")
    baseline_average = baseline.get("average")
    average_delta = None
    if isinstance(current_average, (int, float)) and isinstance(baseline_average, (int, float)):
        average_delta = round(current_average - baseline_average, 2)
        if average_delta < -margin:
            regressions.append(
                {
                    "metric": "average",
                    "delta": average_delta,
                    "baseline": baseline_average,
                    "current": current_average,
                }
            )

    category_deltas: dict[str, float | None] = {}
    for key in CATEGORY_KEYS:
        current_value = current.get("category_averages", {}).get(key)
        baseline_value = baseline.get("category_averages", {}).get(key)
        if isinstance(current_value, (int, float)) and isinstance(baseline_value, (int, float)):
            delta = round(current_value - baseline_value, 2)
            category_deltas[key] = delta
            if key in CRITICAL_CATEGORIES and delta < -margin:
                regressions.append(
                    {
                        "metric": f"category.{key}",
                        "delta": delta,
                        "baseline": baseline_value,
                        "current": current_value,
                    }
                )
        else:
            category_deltas[key] = None
    return {
        "average_delta": average_delta,
        "category_deltas": category_deltas,
        "regression_margin": margin,
        "regressions": regressions,
        "regression_detected": bool(regressions),
    }


def compare_paired_runs(current: list[dict], baseline: list[dict], plan: dict) -> tuple[dict | None, list[str]]:
    errors: list[str] = []
    targets = plan.get("target_ids")
    trials = plan.get("trial_count")
    prompts = plan.get("prompt_ids")
    critical = plan.get("critical_prompt_ids")
    if (not isinstance(targets, list) or not targets or any(not isinstance(item, str) or not item for item in targets)
            or len(set(targets)) != len(targets) or not isinstance(trials, int) or isinstance(trials, bool) or trials < 1
            or not isinstance(prompts, list) or not prompts or any(not isinstance(item, str) or not item for item in prompts)
            or len(set(prompts)) != len(prompts) or not isinstance(critical, list) or not critical
            or any(not isinstance(item, str) or not item for item in critical) or not set(critical).issubset(prompts)):
        return None, ["plan must predeclare unique targets, trials, prompts, and critical prompts"]
    expected = {(target, trial) for target in targets for trial in range(1, trials + 1)}

    def index(payloads: list[dict], arm: str) -> dict[tuple, dict]:
        indexed: dict[tuple, dict] = {}
        for payload in payloads:
            key = (payload.get("target_id"), payload.get("trial"))
            if payload.get("schema_version") != 2 or payload.get("arm") != arm or payload.get("run_type") != "model-execution":
                errors.append(f"{arm} contains non-v2 or non-model result")
            if key in indexed:
                errors.append(f"duplicate {arm} trial: {key}")
            indexed[key] = payload
        if set(indexed) != expected:
            errors.append(f"{arm} target/trial set differs from plan")
        return indexed

    before = index(baseline, "baseline")
    after = index(current, "candidate")
    if errors:
        return None, errors
    deltas: list[float] = []
    target_deltas: dict[str, list[float]] = {target: [] for target in targets}
    attempts: list[dict] = []
    critical_regressions: list[str] = []
    for key in sorted(expected):
        old, new = before[key], after[key]
        if any(old.get(field) != new.get(field) for field in ("model", "harness", "runtime", "phase")):
            errors.append(f"configuration differs in pair {key}")
            continue
        old_scores = {item["prompt_id"]: item for item in old["scores"]}
        new_scores = {item["prompt_id"]: item for item in new["scores"]}
        if set(old_scores) != set(new_scores) or set(old_scores) != set(prompts):
            errors.append(f"prompt set differs in pair {key}")
            continue
        for prompt_id in sorted(old_scores):
            prior, latest = old_scores[prompt_id], new_scores[prompt_id]
            delta = float(latest["total"]) - float(prior["total"])
            deltas.append(delta)
            target_deltas[key[0]].append(delta)
            attempts.append({"target_id": key[0], "trial": key[1], "prompt_id": prompt_id, "baseline": prior["total"], "candidate": latest["total"], "delta": delta})
            if prompt_id in critical:
                for category in CRITICAL_CATEGORIES:
                    if latest["categories"][category] < prior["categories"][category]:
                        critical_regressions.append(f"{key}/{prompt_id}/{category}")
    if errors or not deltas:
        return None, errors or ["no matched scores"]
    average_delta = mean(deltas)
    return {
        "paired_count": len(deltas),
        "paired_deltas": attempts,
        "average_delta": round(average_delta, 2),
        "delta_ci": normal_mean_interval([mean(target_deltas[target]) for target in targets], -100.0, 100.0),
        "uncertainty_unit": "target",
        "independent_units": len(targets),
        "critical_regressions": critical_regressions,
        "regression_detected": average_delta < 0 or bool(critical_regressions),
    }, []


def table_row(metric: str, expected: object, actual: object, status: str, artifact: str) -> dict:
    return {
        "metric": metric,
        "expected": expected,
        "actual": actual,
        "status": status,
        "artifact": artifact,
    }


def build_summary_table(analysis: dict, threshold: float) -> list[dict]:
    rows: list[dict] = []
    result_artifact = ", ".join(analysis.get("results", []))
    rows.append(
        table_row(
            "result validation",
            "all inputs valid",
            "all inputs valid" if analysis.get("valid") else "one or more inputs invalid",
            "pass" if analysis.get("valid") else "fail",
            result_artifact,
        )
    )
    aggregate = analysis.get("aggregate")
    if isinstance(aggregate, dict):
        average = aggregate.get("average")
        rows.append(
            table_row(
                "average score",
                f">= {threshold}",
                average,
                "pass" if isinstance(average, (int, float)) and average >= threshold else "fail",
                result_artifact,
            )
        )
        rows.append(
            table_row(
                "pass rate",
                "reported",
                aggregate.get("pass_rate"),
                "pass" if aggregate.get("pass_rate") is not None else "fail",
                result_artifact,
            )
        )
    comparison = analysis.get("comparison")
    if isinstance(comparison, dict):
        rows.append(
            table_row(
                "baseline regression",
                "no critical regression",
                "regression" if comparison.get("regression_detected") else "no regression",
                "diagnostic" if comparison.get("eligibility", "").startswith("diagnostic-only") else "fail" if comparison.get("regression_detected") else "pass",
                str(analysis.get("baseline", {}).get("result")),
            )
        )
    return rows


def cohort_key(payload: dict) -> tuple:
    return (
        payload.get("run_type"), payload.get("schema_version", 1), payload.get("phase"),
        payload.get("model"), payload.get("harness"),
        json.dumps(payload.get("runtime"), sort_keys=True),
        tuple(sorted(payload.get("prompt_ids", []))),
    )


def load_valid_payloads(
    paths: list[Path],
    suite: Path | None,
    source_weights: Path | None,
) -> tuple[list[dict], list[dict]]:
    known_prompt_ids = load_known_prompt_ids(suite) if suite else None
    source_ids = load_source_ids(source_weights)
    payloads: list[dict] = []
    validations: list[dict] = []
    seen_ids: set[str] = set()
    cohort: tuple | None = None
    for path in paths:
        payload = load_json(path)
        errors, warnings = validate_payload(payload, known_prompt_ids, source_ids)
        run_id = payload.get("run_id")
        if run_id in seen_ids:
            errors.append(f"duplicate run_id: {run_id}")
        if isinstance(run_id, str):
            seen_ids.add(run_id)
        current_cohort = cohort_key(payload)
        if cohort is None:
            cohort = current_cohort
        elif current_cohort != cohort:
            errors.append("mixed run cohort: type, schema, phase, model, harness, runtime, and prompts must match")
        validations.append(
            {
                "result": str(path),
                "valid": not errors,
                "errors": errors,
                "warnings": warnings,
                "run_id": payload.get("run_id"),
                "run_type": payload.get("run_type"),
            }
        )
        if errors:
            continue
        payloads.append(payload)
    return payloads, validations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze PASS-100 run results.")
    parser.add_argument("--results", type=Path, nargs="+", required=True)
    parser.add_argument("--baseline", type=Path, nargs="+")
    parser.add_argument("--plan", type=Path, help="Predeclared target/trial plan for paired model-execution comparison.")
    parser.add_argument("--suite", type=Path)
    parser.add_argument("--source-weights", type=Path)
    parser.add_argument("--threshold", type=float, default=85.0)
    parser.add_argument("--regression-margin", type=float, default=0.0)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--log", type=Path)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    source_weights = args.source_weights
    if source_weights is None:
        source_weights = default_source_weights(args.results[0])

    payloads, validations = load_valid_payloads(args.results, args.suite, source_weights)
    analysis = {
        "analyzed_at": utc_now(),
        "results": [str(path) for path in args.results],
        "valid": all(item["valid"] for item in validations),
        "validations": validations,
        "statistics_note": (
            "PASS-100 score intervals use a 95% normal approximation; pass/resolved "
            "rates use a 95% Wilson interval. Paired-delta intervals use target-level means."
        ),
        "aggregate": summarize_scores(collect_scores(payloads), args.threshold) if payloads else None,
        "baseline": None,
        "comparison": None,
        "comparison_errors": [],
    }

    if args.baseline:
        baseline_payloads, baseline_validations = load_valid_payloads(
            args.baseline,
            args.suite,
            source_weights,
        )
        baseline_summary = (
            summarize_scores(collect_scores(baseline_payloads), args.threshold)
            if baseline_payloads
            else None
        )
        analysis["baseline"] = {
            "result": ", ".join(str(path) for path in args.baseline),
            "results": [str(path) for path in args.baseline],
            "validations": baseline_validations,
            "aggregate": baseline_summary,
        }
        analysis["valid"] = analysis["valid"] and all(item["valid"] for item in baseline_validations)
        if payloads and baseline_payloads and cohort_key(payloads[0]) != cohort_key(baseline_payloads[0]):
            analysis["comparison_errors"].append("current and baseline cohorts differ in run type, schema, phase, model, harness, runtime, or prompts")
            analysis["valid"] = False
        elif args.plan:
            plan = load_json(args.plan)
            comparison, pair_errors = compare_paired_runs(payloads, baseline_payloads, plan)
            analysis["comparison"] = comparison
            analysis["pair_errors"] = pair_errors
            analysis["valid"] = analysis["valid"] and not pair_errors
        elif analysis["aggregate"] and baseline_summary:
            analysis["comparison"] = compare_summaries(analysis["aggregate"], baseline_summary, args.regression_margin)
            analysis["comparison"]["eligibility"] = "diagnostic-only; no predeclared paired plan"

    analysis["summary_table"] = build_summary_table(analysis, args.threshold)

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(analysis, indent=2, sort_keys=True), encoding="utf-8")
    if args.log and analysis["aggregate"]:
        args.log.parent.mkdir(parents=True, exist_ok=True)
        with args.log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(analysis, sort_keys=True) + "\n")
    print(json.dumps(analysis, indent=2, sort_keys=True))
    if not analysis["valid"]:
        raise SystemExit(1)
    comparison = analysis.get("comparison")
    if isinstance(comparison, dict) and comparison.get("regression_detected"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
