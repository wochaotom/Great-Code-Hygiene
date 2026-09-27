#!/usr/bin/env python3
"""Promote a candidate skill folder when PASS-100 gates pass."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True


def reject_verifier_bytecode() -> None:
    for current, dirs, files in os.walk(Path(__file__).resolve().parent):
        if any(name.casefold() == "__pycache__" for name in dirs) or any(name.casefold().endswith((".pyc", ".pyo")) for name in files):
            raise SystemExit(f"verifier bytecode is not allowed: {current}")


reject_verifier_bytecode()

from internal.evidence import evaluate_bundle, tree_digest, unsafe_link
from internal.policy import finite_number
from internal.transaction import TRANSFERABLE_RUNTIME_NAMES, apply_transaction, journal_path, recover_transaction
from validate_honing_report import load_json as load_honing_json
from validate_honing_report import validate_report as validate_honing_report_payload


MARKER_NAMES = {"SKILL.md", "compounder-manifest.json"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_skill(path: Path) -> list[str]:
    skill = path / "SKILL.md"
    if not skill.exists():
        return ["missing SKILL.md"]
    text = skill.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return ["SKILL.md missing YAML frontmatter"]
    try:
        _, frontmatter, _ = text.split("---", 2)
    except ValueError:
        return ["SKILL.md frontmatter is not closed"]
    errors: list[str] = []
    if "name:" not in frontmatter:
        errors.append("frontmatter missing name")
    if "description:" not in frontmatter:
        errors.append("frontmatter missing description")
    return errors


def load_score(path: Path) -> tuple[dict, list[str]]:
    try:
        score = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        return {}, [f"score invalid JSON: {exc}"]
    if not isinstance(score, dict):
        return {}, ["score must be a JSON object"]
    errors: list[str] = []
    if not finite_number(score.get("average")):
        errors.append("score.average must be finite numeric")
    if not isinstance(score.get("promotion_ready"), bool):
        errors.append("score.promotion_ready must be boolean")
    return score, errors


def gate_error(field: str, expected: object, actual: object, artifact: Path) -> str:
    return f"{field} failed: expected {expected}, actual {actual} in {artifact}"


def major_promotion_evidence(score: dict, score_path: Path) -> tuple[bool, str]:
    evidence = score.get("evidence_warning")
    run_type = score.get("run_type", "unknown")
    if not isinstance(evidence, dict):
        return False, gate_error("score.evidence_warning", "object", type(evidence).__name__, score_path)
    evidence_run_type = evidence.get("run_type", run_type)
    if run_type != "model-execution" or evidence_run_type != "model-execution":
        return False, (
            gate_error("score.run_type", "model-execution", run_type, score_path)
            + "; "
            + gate_error("score.evidence_warning.run_type", "model-execution", evidence_run_type, score_path)
        )
    value = evidence.get("major_promotion_evidence")
    if value is not True:
        return False, (
            gate_error("score.evidence_warning.major_promotion_evidence", True, value, score_path)
        )
    return True, ""


def resolve_existing_dir(path: Path, label: str) -> tuple[Path | None, list[str]]:
    if unsafe_link(path):
        return None, [f"{label} is a link or junction: {path}"]
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        return None, [f"{label} does not exist: {path}"]
    if not resolved.is_dir():
        return resolved, [f"{label} is not a directory: {resolved}"]
    return resolved, []


def has_marker(path: Path) -> bool:
    return any((path / marker).exists() for marker in MARKER_NAMES)


def find_repo_root(path: Path) -> Path | None:
    for candidate in [path, *path.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def validate_apply_target(current: Path, candidate: Path) -> list[str]:
    errors: list[str] = []
    if current == candidate:
        errors.append("--current and --candidate resolve to the same directory")
    if current in candidate.parents or candidate in current.parents:
        errors.append("--current and --candidate must not overlap")
    for label, root in (("--current", current), ("--candidate", candidate)):
        if unsafe_link(root):
            errors.append(f"{label} is a link or junction")
        for child in root.rglob("*"):
            if unsafe_link(child):
                errors.append(f"{label} contains a link or junction: {child}")
                break

    home = Path.home().resolve()
    dangerous_roots = {
        Path(current.anchor).resolve(),
        home,
        home / ".claude",
        home / ".codex",
        Path.cwd().resolve(),
    }
    if current in dangerous_roots:
        errors.append(f"refusing to apply to dangerous root: {current}")

    repo_root = find_repo_root(current)
    if repo_root and current == repo_root:
        errors.append(f"refusing to apply to repository root: {current}")

    if not has_marker(current):
        errors.append(f"--current must contain one marker file: {', '.join(sorted(MARKER_NAMES))}")
    if not has_marker(candidate):
        errors.append(f"--candidate must contain one marker file: {', '.join(sorted(MARKER_NAMES))}")
    return errors


def planned_deletions(current: Path) -> list[str]:
    return [
        str(child)
        for child in sorted(current.iterdir(), key=lambda item: item.name.lower())
        if child.name.casefold() not in TRANSFERABLE_RUNTIME_NAMES
    ]


def validate_honing_report(path: Path) -> list[str]:
    try:
        report = load_honing_json(path)
    except SystemExit as exc:
        return [f"honing report invalid: {exc}"]
    return [f"honing report {error}" for error in validate_honing_report_payload(report)]


def append_decision_log(path: Path, decision: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if unsafe_link(path):
        raise ValueError(f"unsafe decision log: {path}")
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(decision, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def log_overlaps_tree(log: Path, tree: Path) -> bool:
    log_path = log.resolve(strict=False)
    root = tree.resolve(strict=False)
    return log_path == root or root in log_path.parents


def main() -> None:
    parser = argparse.ArgumentParser(description="Gate and promote a candidate skill update.")
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--candidate", type=Path)
    evidence = parser.add_mutually_exclusive_group()
    evidence.add_argument("--score", type=Path, help="Historical diagnostic only; cannot authorize --apply.")
    evidence.add_argument("--evidence-bundle", type=Path, help="Versioned, hashed evidence bundle for promotion gates.")
    parser.add_argument("--baseline-average", type=float)
    parser.add_argument("--honing-report", type=Path)
    parser.add_argument("--require-honing-report", action="store_true")
    parser.add_argument(
        "--allow-non-major-evidence",
        action="store_true",
        help="Allow non-model-execution evidence for explicit dry-run or non-final gates.",
    )
    parser.add_argument("--apply", action="store_true", help="Actually copy candidate over current.")
    parser.add_argument("--recover", action="store_true", help="Roll back an incomplete swap or finish the journal while retaining the old-tree backup.")
    parser.add_argument("--log", type=Path)
    args = parser.parse_args()

    if args.log and (log_overlaps_tree(args.log, args.current) or (args.candidate and log_overlaps_tree(args.log, args.candidate))):
        parser.error("--log must be outside --current and --candidate trees")

    if args.recover:
        if args.apply or args.score or args.evidence_bundle or args.candidate or args.baseline_average is not None or args.honing_report or args.require_honing_report or args.allow_non_major_evidence:
            parser.error("--recover accepts only --current and optional --log")
        journal = journal_path(args.current.absolute())
        phase = None
        try:
            if journal.is_file() and not unsafe_link(journal):
                state = json.loads(journal.read_text(encoding="utf-8"))
                phase = state.get("phase") if isinstance(state, dict) else None
            recovery: dict = {}
            retained_backup = recover_transaction(args.current, report=recovery)
        except (Exception, SystemExit) as exc:
            decision = {"decided_at": utc_now(), "recovered": False, "current": str(args.current), "journal": str(journal), "phase": phase, "error": str(exc)}
            if args.log:
                append_decision_log(args.log, decision)
            print(json.dumps(decision, indent=2, sort_keys=True))
            raise SystemExit(1) from exc
        decision = {"decided_at": utc_now(), "recovered": True, "current": str(args.current), "journal": str(journal), "phase": recovery["phase"], "action": recovery["action"], "journal_state": recovery["journal_state"], "retained_backup": str(retained_backup) if retained_backup else None}
        try:
            decision["installed_fingerprint"] = tree_digest(args.current)
        except (OSError, ValueError) as exc:
            decision["installed_fingerprint_error"] = str(exc)
        if args.log:
            append_decision_log(args.log, decision)
        print(json.dumps(decision, indent=2, sort_keys=True))
        return
    if not args.candidate or not (args.score or args.evidence_bundle):
        parser.error("--candidate and either --score or --evidence-bundle are required")
    current, current_errors = resolve_existing_dir(args.current, "--current")
    candidate, candidate_errors = resolve_existing_dir(args.candidate, "--candidate")
    errors = current_errors + candidate_errors
    if candidate:
        errors.extend(validate_skill(candidate))
    if args.apply and current and candidate:
        errors.extend(validate_apply_target(current, candidate))
    if args.apply and args.allow_non_major_evidence:
        errors.append("--allow-non-major-evidence cannot be used with --apply")
    if args.apply and args.evidence_bundle and not args.log:
        errors.append("--apply requires --log for a durable transaction audit")
    if args.score:
        score, score_errors = load_score(args.score)
        errors.extend(score_errors)
        average = float(score.get("average", 0)) if not score_errors else None
        if args.apply:
            errors.append("legacy --score evidence is diagnostic-only and cannot authorize --apply")
        if args.baseline_average is not None and average is not None and average < args.baseline_average:
            errors.append(gate_error("score.average", f">= {args.baseline_average}", average, args.score))
        if args.require_honing_report and not args.honing_report:
            errors.append("missing required --honing-report")
        if args.honing_report:
            errors.extend(validate_honing_report(args.honing_report))
        decision = {
            "diagnostic_only": True,
            "diagnostic_score_ready": bool(score.get("promotion_ready")) if not score_errors else False,
            "average": average,
            "promotion_ready": False,
            "gates": [{"name": "versioned_evidence", "status": "fail", "detail": "legacy score cannot authorize promotion"}],
        }
    else:
        if current and candidate:
            try:
                decision = evaluate_bundle(args.evidence_bundle, current, candidate, Path(__file__).resolve().parents[1])
            except (Exception, SystemExit) as exc:
                decision = {"promotion_ready": False, "gates": [{"name": "evaluation", "status": "fail", "detail": str(exc)}], "evaluation_error": str(exc)}
        else:
            decision = {"promotion_ready": False, "gates": []}
        if args.baseline_average is not None or args.honing_report or args.require_honing_report or args.allow_non_major_evidence:
            errors.append("legacy gate options cannot override a versioned evidence bundle")
    decision.update({
        "decided_at": utc_now(),
        "candidate": str(candidate or args.candidate),
        "current": str(current or args.current),
        "planned_deletions": planned_deletions(current) if current and decision["promotion_ready"] else [],
        "applied": False,
        "errors": errors,
    })
    if args.evidence_bundle and decision.get("promotion_ready") and not decision.get("evidence_bundle_sha256"):
        errors.append("validated evidence bundle hash is missing")
    if errors:
        decision["promotion_ready"] = False

    if decision["promotion_ready"] and args.apply:
        try:
            append_decision_log(args.log, {
                "event": "apply_started", "decided_at": utc_now(), "current": str(current),
                "candidate": str(candidate), "baseline_fingerprint": decision["baseline_fingerprint"],
                "candidate_fingerprint": decision["candidate_fingerprint"],
                "evidence_bundle_sha256": decision.get("evidence_bundle_sha256"),
            })
            retained_backup = apply_transaction(candidate, current, decision["baseline_fingerprint"], decision["candidate_fingerprint"], evidence_bundle_sha256=decision["evidence_bundle_sha256"])
            decision["applied"] = True
            decision["retained_backup"] = str(retained_backup)
        except BaseException as exc:
            decision["event"] = "apply_failed"
            decision["apply_error"] = str(exc) or type(exc).__name__
            decision["errors"].append(f"apply failed: {decision['apply_error']}")
            journal = journal_path(current)
            decision["journal"] = str(journal)
            decision["promotion_ready"] = False
            journal_phase = None
            if journal.is_file() and not unsafe_link(journal):
                try:
                    journal_phase = json.loads(journal.read_text(encoding="utf-8")).get("phase")
                except (OSError, ValueError, AttributeError):
                    journal_phase = "unreadable"
            decision["journal_phase"] = journal_phase
            try:
                installed = tree_digest(current)
                if installed == decision["candidate_fingerprint"]:
                    decision["installation_state"] = "candidate-pending-recovery" if journal_phase not in (None, "committed") else "candidate-commit-pending-cleanup" if journal_phase == "committed" else "candidate-present"
                    decision["applied"] = journal_phase in (None, "committed")
                else:
                    decision["installation_state"] = "baseline-present" if installed == decision["baseline_fingerprint"] else "indeterminate"
            except (OSError, ValueError):
                decision["installation_state"] = "indeterminate"
            if args.log:
                append_decision_log(args.log, decision)
            print(json.dumps(decision, indent=2, sort_keys=True))
            raise SystemExit(1) from exc

    if args.log:
        append_decision_log(args.log, decision)

    print(json.dumps(decision, indent=2, sort_keys=True))
    if errors or not decision["promotion_ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
