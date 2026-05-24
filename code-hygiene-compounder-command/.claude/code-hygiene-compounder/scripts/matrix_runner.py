#!/usr/bin/env python3
"""Generate and run large scratch hygiene target matrices."""
from __future__ import annotations
import argparse
from collections import Counter
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
sys.dont_write_bytecode = True
from matrix_families import REVIEW_FAMILIES, build_cases, build_review_cases, family_manifest, family_names, review_family_manifest
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
def tail(text: str, limit: int = 2500) -> str:
    return text if len(text) <= limit else text[-limit:]
def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
def write_files(root: Path, files: dict[str, str]) -> None:
    for relative, content in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8", newline="\n")
def run_command(command: list[str], cwd: Path, timeout: int) -> dict:
    resolved = [sys.executable if part == "{python}" else part for part in command]
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    started = time.monotonic()
    try:
        completed = subprocess.run(
            resolved,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            env=env,
        )
        return {
            "command": resolved,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "exit_code": completed.returncode,
            "passed": completed.returncode == 0,
            "stdout_tail": tail(completed.stdout),
            "stderr_tail": tail(completed.stderr),
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "command": resolved,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "exit_code": None,
            "passed": False,
            "stdout_tail": tail(exc.stdout or ""),
            "stderr_tail": tail(exc.stderr or ""),
            "timed_out": True,
        }
def run_case(case, root: Path, timeout: int, keep_targets: bool) -> dict:
    target = root / case.case_id
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    write_files(target, case.files)
    baseline = run_command(case.command, target, timeout)
    write_files(target, case.fixed_files)
    oracle = run_command(case.command, target, timeout)
    result = {
        "case_id": case.case_id,
        "family": case.family,
        "split": case.split,
        "evidence_kind": case.evidence_kind,
        "generated": case.generated,
        "prompt_id": case.prompt_id,
        "category": case.category,
        "target": str(target),
        "baseline_red": not baseline["passed"],
        "oracle_green": bool(oracle["passed"]),
        "baseline": baseline,
        "oracle": oracle,
    }
    if not keep_targets:
        shutil.rmtree(target, ignore_errors=True)
        result["target_removed"] = True
    return result
def contract_errors(case) -> list[str]:
    errors: list[str] = []
    spec = case.files.get("SPEC.md")
    if not spec:
        errors.append("missing SPEC.md")
        spec = ""
    for contract in case.contracts:
        if contract not in spec:
            errors.append(f"contract {contract} missing from SPEC.md")
    for contract in case.hidden_contracts:
        if contract not in case.contracts:
            errors.append(f"hidden contract {contract} is not in visible contract set")
    all_files = {**case.files, **case.fixed_files}
    for relative, content in all_files.items():
        try:
            content.encode("ascii")
        except UnicodeEncodeError:
            errors.append(f"{relative} contains non-ASCII; use escaped Unicode in generated evals")
    return errors
def run_review_case(case, root: Path, timeout: int, keep_targets: bool) -> dict:
    target = root / case.case_id
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    write_files(target, case.files)
    visible_baseline = run_command(case.visible_command, target, timeout)
    hidden_baseline = run_command(case.hidden_command, target, timeout)
    write_files(target, case.fixed_files)
    visible_oracle = run_command(case.visible_command, target, timeout)
    hidden_oracle = run_command(case.hidden_command, target, timeout)
    errors = contract_errors(case)
    result = {
        "case_id": case.case_id,
        "family": case.family,
        "split": case.split,
        "evidence_kind": case.evidence_kind,
        "generated": case.generated,
        "prompt_id": case.prompt_id,
        "category": case.category,
        "target": str(target),
        "contracts": case.contracts,
        "hidden_contracts": case.hidden_contracts,
        "contract_errors": errors,
        "contract_valid": not errors,
        "visible_baseline_green": bool(visible_baseline["passed"]),
        "hidden_baseline_red": not hidden_baseline["passed"],
        "visible_oracle_green": bool(visible_oracle["passed"]),
        "hidden_oracle_green": bool(hidden_oracle["passed"]),
        "visible_baseline": visible_baseline,
        "hidden_baseline": hidden_baseline,
        "visible_oracle": visible_oracle,
        "hidden_oracle": hidden_oracle,
    }
    result["valid"] = (
        result["contract_valid"]
        and result["visible_baseline_green"]
        and result["hidden_baseline_red"]
        and result["visible_oracle_green"]
        and result["hidden_oracle_green"]
    )
    if not keep_targets:
        shutil.rmtree(target, ignore_errors=True)
        result["target_removed"] = True
    return result
def summarize(results: list[dict]) -> dict:
    families: dict[str, dict] = {}
    splits: dict[str, dict] = {}
    ids = [item["case_id"] for item in results]
    duplicate_ids = sorted(case_id for case_id, count in Counter(ids).items() if count > 1)
    for item in results:
        for bucket, key in ((families, item["family"]), (splits, item["split"])):
            stats = bucket.setdefault(key, {"count": 0, "baseline_red": 0, "oracle_green": 0})
            stats["count"] += 1
            stats["baseline_red"] += 1 if item["baseline_red"] else 0
            stats["oracle_green"] += 1 if item["oracle_green"] else 0
    baseline_red = sum(1 for item in results if item["baseline_red"])
    oracle_green = sum(1 for item in results if item["oracle_green"])
    return {
        "count": len(results),
        "unique_case_ids": len(set(ids)),
        "duplicate_case_ids": duplicate_ids,
        "baseline_red": baseline_red,
        "oracle_green": oracle_green,
        "baseline_red_rate": round(baseline_red / len(results), 4) if results else None,
        "oracle_green_rate": round(oracle_green / len(results), 4) if results else None,
        "families": families,
        "splits": splits,
        "evidence_kinds": dict(Counter(item.get("evidence_kind", "unknown") for item in results)),
        "candidate_evidence_only": all(item.get("evidence_kind") == "candidate_evidence" for item in results),
    }
def summarize_review(results: list[dict]) -> dict:
    ids = [item["case_id"] for item in results]
    duplicate_ids = sorted(case_id for case_id, count in Counter(ids).items() if count > 1)
    families: dict[str, dict] = {}
    for item in results:
        stats = families.setdefault(item["family"], {"count": 0, "valid": 0})
        stats["count"] += 1
        stats["valid"] += 1 if item["valid"] else 0
    return {
        "count": len(results),
        "unique_case_ids": len(set(ids)),
        "duplicate_case_ids": duplicate_ids,
        "valid": sum(1 for item in results if item["valid"]),
        "contract_valid": sum(1 for item in results if item["contract_valid"]),
        "visible_baseline_green": sum(1 for item in results if item["visible_baseline_green"]),
        "hidden_baseline_red": sum(1 for item in results if item["hidden_baseline_red"]),
        "visible_oracle_green": sum(1 for item in results if item["visible_oracle_green"]),
        "hidden_oracle_green": sum(1 for item in results if item["hidden_oracle_green"]),
        "families": families,
        "evidence_kinds": dict(Counter(item.get("evidence_kind", "unknown") for item in results)),
        "candidate_evidence_only": all(item.get("evidence_kind") == "candidate_evidence" for item in results),
    }
def selected_families(args: argparse.Namespace) -> list[str]:
    if args.families:
        families = [item.strip() for item in args.families.split(",") if item.strip()]
    else:
        families = family_names(args.split)
    unknown = sorted(set(families) - set(family_names("all")))
    if unknown:
        raise SystemExit("unknown families: " + ", ".join(unknown))
    return families
def selected_review_families(args: argparse.Namespace) -> list[str]:
    if args.families:
        families = [item.strip() for item in args.families.split(",") if item.strip()]
    else:
        families = sorted(REVIEW_FAMILIES)
    unknown = sorted(set(families) - set(REVIEW_FAMILIES))
    if unknown:
        raise SystemExit("unknown review families: " + ", ".join(unknown))
    return families
def cmd_list(_: argparse.Namespace) -> None:
    print(json.dumps({"families": family_manifest(), "review_families": review_family_manifest()}, indent=2, sort_keys=True))
def cmd_run(args: argparse.Namespace) -> None:
    families = selected_families(args)
    if args.variants_per_family < 1:
        raise SystemExit("--variants-per-family must be positive")
    if args.loops < 1:
        raise SystemExit("--loops must be positive")
    run_root = args.work_root / f"matrix-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    run_root.mkdir(parents=True, exist_ok=False)
    results: list[dict] = []
    loop_summaries: list[dict] = []
    for loop in range(args.loops):
        loop_root = run_root / f"loop-{loop + 1:03d}"
        loop_root.mkdir()
        offset = loop * args.variants_per_family
        loop_results = [
            run_case(case, loop_root, args.timeout, args.keep_targets)
            for case in build_cases(families, args.variants_per_family, offset)
        ]
        loop_summary = summarize(loop_results)
        loop_summary["loop"] = loop + 1
        loop_summary["start_index"] = offset
        loop_summaries.append(loop_summary)
        results.extend(loop_results)
        if args.out and args.checkpoint_each_loop:
            partial = summarize(results)
            write_json(args.out, {
                "run_id": args.run_id or run_root.name,
                "created_at": utc_now(),
                "partial": True,
                "completed_loops": loop + 1,
                "work_root": str(run_root),
                "requested_split": args.split,
                "families": families,
                "loops": args.loops,
                "variants_per_family": args.variants_per_family,
                "evidence_note": "Generated matrix targets are candidate evidence only, not model-execution promotion proof.",
                "summary": partial,
                "loop_summaries": loop_summaries,
                "results": results,
            })
    summary = summarize(results)
    payload = {
        "run_id": args.run_id or run_root.name,
        "created_at": utc_now(),
        "valid": summary["baseline_red"] == summary["count"]
        and summary["oracle_green"] == summary["count"]
        and not summary["duplicate_case_ids"],
        "work_root": str(run_root),
        "requested_split": args.split,
        "families": families,
        "loops": args.loops,
        "variants_per_family": args.variants_per_family,
        "evidence_note": "Generated matrix targets are candidate evidence only, not model-execution promotion proof.",
        "summary": summary,
        "loop_summaries": loop_summaries,
        "results": results,
    }
    if not args.keep_targets:
        shutil.rmtree(run_root, ignore_errors=True)
    if args.out:
        write_json(args.out, payload)
    print(json.dumps({"valid": payload["valid"], **summary}, indent=2, sort_keys=True))
    if not payload["valid"]:
        raise SystemExit(1)
def cmd_review(args: argparse.Namespace) -> None:
    families = selected_review_families(args)
    if args.variants_per_family < 1:
        raise SystemExit("--variants-per-family must be positive")
    run_root = args.work_root / f"review-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}"
    run_root.mkdir(parents=True, exist_ok=False)
    results = [
        run_review_case(case, run_root, args.timeout, args.keep_targets)
        for case in build_review_cases(families, args.variants_per_family)
    ]
    summary = summarize_review(results)
    payload = {
        "run_id": args.run_id or run_root.name,
        "created_at": utc_now(),
        "valid": summary["valid"] == summary["count"] and not summary["duplicate_case_ids"],
        "work_root": str(run_root),
        "families": families,
        "variants_per_family": args.variants_per_family,
        "evidence_note": "Generated review targets are candidate evidence only, not model-execution promotion proof.",
        "summary": summary,
        "results": results,
    }
    if not args.keep_targets:
        shutil.rmtree(run_root, ignore_errors=True)
    if args.out:
        write_json(args.out, payload)
    print(json.dumps({"valid": payload["valid"], **summary}, indent=2, sort_keys=True))
    if not payload["valid"]:
        raise SystemExit(1)
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run generated hygiene target matrices.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list")
    list_parser.set_defaults(func=cmd_list)
    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--families")
    run_parser.add_argument("--split", choices=["train", "holdout", "all"], default="train")
    run_parser.add_argument("--loops", type=int, default=1)
    run_parser.add_argument("--variants-per-family", type=int, default=20)
    run_parser.add_argument("--work-root", type=Path, default=Path("runs/matrix"))
    run_parser.add_argument("--timeout", type=int, default=20)
    run_parser.add_argument("--keep-targets", action="store_true")
    run_parser.add_argument("--run-id")
    run_parser.add_argument("--out", type=Path)
    run_parser.add_argument("--no-checkpoint", action="store_false", dest="checkpoint_each_loop")
    run_parser.set_defaults(func=cmd_run)
    review_parser = subparsers.add_parser("review")
    review_parser.add_argument("--families")
    review_parser.add_argument("--variants-per-family", type=int, default=1)
    review_parser.add_argument("--work-root", type=Path, default=Path("runs/matrix-review"))
    review_parser.add_argument("--timeout", type=int, default=20)
    review_parser.add_argument("--keep-targets", action="store_true")
    review_parser.add_argument("--run-id")
    review_parser.add_argument("--out", type=Path)
    review_parser.set_defaults(func=cmd_review)
    return parser
def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)
if __name__ == "__main__":
    main()
