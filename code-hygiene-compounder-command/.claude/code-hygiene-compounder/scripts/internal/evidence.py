"""Validate versioned promotion evidence against controls outside a candidate tree."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean

from internal.policy import CRITICAL_CATEGORIES, PROMOTION_THRESHOLD
from internal.json_integrity import loads_strict
from fixture_runner import parse_test_report
from pass100_runner import load_prompts
from validate_results import validate_payload


SKIP_NAMES = frozenset({"runs", "__pycache__", ".pytest_cache", ".mypy_cache", ".fixture-work", ".fixture-tmp", ".git"})
SHA256 = re.compile(r"^[0-9a-f]{64}$")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            value.update(chunk)
    return value.hexdigest()


def unsafe_link(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


def tree_digest(root: Path) -> str:
    if not root.is_dir() or unsafe_link(root):
        raise ValueError(f"unsafe or missing tree: {root}")
    value = hashlib.sha256()
    def fail(error: OSError) -> None:
        raise error

    for current, dirs, files in os.walk(root, onerror=fail):
        base = Path(current)
        for name in list(dirs):
            child = base / name
            if unsafe_link(child):
                raise ValueError(f"unsafe link in tree: {child}")
        dirs[:] = sorted(name for name in dirs if name not in SKIP_NAMES)
        for name in sorted(files):
            file = base / name
            if unsafe_link(file):
                raise ValueError(f"unsafe link in tree: {file}")
            relative = file.relative_to(root).as_posix()
            value.update(relative.encode("utf-8"))
            value.update(b"\0")
            value.update(digest(file).encode("ascii"))
            value.update(b"\n")
    return value.hexdigest()


def read_json(path: Path) -> dict:
    payload = loads_strict(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def artifact_registry(manifest: Path, entries: object) -> tuple[dict[str, Path], list[str]]:
    errors: list[str] = []
    paths: dict[str, Path] = {}
    seen_paths: set[str] = set()
    if not isinstance(entries, list) or not entries:
        return paths, ["artifacts must be a non-empty array"]
    root = manifest.resolve().parent
    for index, entry in enumerate(entries):
        label = f"artifacts[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label} must be an object")
            continue
        identity, relative, expected = entry.get("id"), entry.get("path"), entry.get("sha256")
        if not isinstance(identity, str) or not identity or identity in paths:
            errors.append(f"{label}.id is missing or duplicated")
            continue
        if not isinstance(relative, str) or not relative or not isinstance(expected, str) or not SHA256.fullmatch(expected):
            errors.append(f"{label} requires relative path and sha256")
            continue
        raw = Path(relative)
        if raw.is_absolute() or any(part in ("..", ".") for part in raw.parts):
            errors.append(f"{label}.path must be contained relative path")
            continue
        path_key = raw.as_posix().casefold()
        if path_key in seen_paths:
            errors.append(f"{label}.path is duplicated")
            continue
        seen_paths.add(path_key)
        path = root / raw
        if any(unsafe_link(root.joinpath(*raw.parts[:step])) for step in range(1, len(raw.parts) + 1)):
            errors.append(f"{label}.path traverses a link")
            continue
        try:
            resolved = path.resolve(strict=True)
            resolved.relative_to(root)
        except (FileNotFoundError, ValueError):
            errors.append(f"{label}.path is missing or escapes manifest root")
            continue
        try:
            if not resolved.is_file() or digest(resolved) != expected:
                errors.append(f"{label}.sha256 does not match file")
                continue
        except OSError as exc:
            errors.append(f"{label}.sha256 cannot be verified: {exc}")
            continue
        paths[identity] = resolved
    return paths, errors


def control_hashes(accepted_root: Path) -> dict[str, str]:
    return {
        "suite": digest(accepted_root / "references" / "eval-prompts.md"),
        "rubric": digest(accepted_root / "references" / "PASS-100.md"),
        "policy": digest(accepted_root / "scripts" / "internal" / "policy.py"),
        "verifier": tree_digest(accepted_root / "scripts"),
        "fixtures": tree_digest(accepted_root / "fixtures"),
    }


def parse_time(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp is missing")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must have timezone")
    return parsed


def gate(gates: list[dict], name: str, passed: bool, detail: str) -> None:
    gates.append({"name": name, "status": "pass" if passed else "fail", "detail": detail})


def artifact_json(paths: dict[str, Path], identity: object) -> dict:
    if not isinstance(identity, str) or identity not in paths:
        raise ValueError(f"missing artifact reference: {identity}")
    return read_json(paths[identity])


def relative_directory(manifest: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError("package_repo_root must be relative to the manifest")
    root = manifest.resolve().parent
    path = (root / relative).resolve(strict=True)
    path.relative_to(root)
    if not path.is_dir() or unsafe_link(path):
        raise ValueError("package_repo_root is unsafe")
    return path


def evaluate_bundle(manifest: Path, current: Path, candidate: Path, accepted_root: Path) -> dict:
    gates: list[dict] = []
    decision = {"schema_version": 2, "bundle": str(manifest), "promotion_ready": False, "gates": gates}
    try:
        bundle = read_json(manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        gate(gates, "bundle_format", False, str(exc))
        return decision
    if bundle.get("schema_version") != 2 or isinstance(bundle.get("schema_version"), bool):
        gate(gates, "bundle_format", False, "schema_version must be 2")
        return decision
    gate(gates, "bundle_format", True, "v2 bundle")
    paths, errors = artifact_registry(manifest, bundle.get("artifacts"))
    gate(gates, "artifact_integrity", not errors, "; ".join(errors) if errors else f"{len(paths)} hashed artifacts")
    if errors:
        return decision

    try:
        current_hash, candidate_hash = tree_digest(current), tree_digest(candidate)
        stable = bundle.get("baseline_fingerprint") == current_hash and bundle.get("candidate_fingerprint") == candidate_hash and current_hash != candidate_hash
        gate(gates, "skill_fingerprints", stable, "candidate and baseline tree hashes match" if stable else "tree fingerprint mismatch")
        if stable:
            decision["baseline_fingerprint"] = current_hash
            decision["candidate_fingerprint"] = candidate_hash
    except (OSError, ValueError) as exc:
        gate(gates, "skill_fingerprints", False, str(exc))
        return decision

    try:
        accepted = accepted_root.resolve(strict=True)
        candidate_resolved = candidate.resolve(strict=True)
        separated = accepted != candidate_resolved and candidate_resolved not in accepted.parents and accepted not in candidate_resolved.parents
        actual_controls = control_hashes(accepted)
        gate(gates, "accepted_controls", separated and bundle.get("controls") == actual_controls,
             "controls match external verifier" if separated and bundle.get("controls") == actual_controls else "candidate controls differ from accepted external controls")
        candidate_controls = tree_digest(candidate / "scripts") == tree_digest(accepted / "scripts") and tree_digest(candidate / "fixtures") == actual_controls["fixtures"] and all(
            digest(candidate / "references" / name) == digest(accepted / "references" / name)
            for name in ("eval-prompts.md", "PASS-100.md", "source-weights.json")
        )
        gate(gates, "candidate_control_isolation", candidate_controls, "candidate cannot redefine verifier, rubric, suite, weights, or fixtures" if candidate_controls else "candidate-controlled gate inputs differ")
    except (OSError, ValueError) as exc:
        gate(gates, "accepted_controls", False, str(exc))
        gate(gates, "candidate_control_isolation", False, "control comparison unavailable")
        actual_controls = None

    try:
        plan = artifact_json(paths, bundle.get("plan_artifact"))
        suite_ids = {item["id"] for item in load_prompts(accepted / "references" / "eval-prompts.md")}
        targets = plan.get("target_ids")
        target_artifacts = plan.get("target_artifacts")
        trials = plan.get("trial_count")
        prompts = plan.get("prompt_ids")
        critical = plan.get("critical_prompt_ids")
        valid_plan = (
            plan.get("schema_version") == 2 and plan.get("run_type") == "model-execution"
            and plan.get("mode") in ("focused", "hard")
            and isinstance(targets, list) and bool(targets) and all(isinstance(item, str) and item for item in targets) and len(set(targets)) == len(targets)
            and isinstance(target_artifacts, dict) and set(target_artifacts) == set(targets)
            and all(isinstance(identity, str) and identity in paths and paths[identity].stat().st_size > 0 for identity in target_artifacts.values())
            and isinstance(trials, int) and not isinstance(trials, bool) and trials >= 1
            and isinstance(prompts, list) and bool(prompts) and all(isinstance(item, str) and item for item in prompts) and len(set(prompts)) == len(prompts) and set(prompts).issubset(suite_ids)
            and isinstance(critical, list) and bool(critical) and all(isinstance(item, str) and item for item in critical) and len(set(critical)) == len(critical) and set(critical) == set(prompts)
            and isinstance(plan.get("model"), str) and bool(plan["model"])
            and isinstance(plan.get("harness"), str) and bool(plan["harness"])
            and isinstance(plan.get("runtime"), dict) and all(plan["runtime"].get(key) for key in ("os", "python", "node", "codex"))
            and isinstance(plan.get("applicable_fixture_ids"), list)
            and all(isinstance(item, str) and item for item in plan["applicable_fixture_ids"])
            and len(set(plan["applicable_fixture_ids"])) == len(plan["applicable_fixture_ids"])
            and (bool(plan["applicable_fixture_ids"]) or isinstance(plan.get("fixture_na_reason"), str) and bool(plan["fixture_na_reason"].strip()))
            and plan.get("controls") == actual_controls
            and isinstance(plan.get("improvement"), dict) and plan["improvement"].get("type") in ("score", "smaller")
        )
        declared_at = parse_time(plan.get("declared_at"))
        gate(gates, "predeclared_plan", bool(valid_plan), "target/trial/configuration declared" if valid_plan else "invalid or incomplete evaluation plan")
    except (OSError, ValueError, TypeError, KeyError, SystemExit, json.JSONDecodeError) as exc:
        gate(gates, "predeclared_plan", False, str(exc))
        return decision
    if not valid_plan:
        return decision

    target_hashes = {target: digest(paths[identity]) for target, identity in target_artifacts.items()}
    hard_ok = plan["mode"] != "hard" or len(targets) >= 3 and len(set(target_hashes.values())) == len(targets)
    gate(gates, "hard_target_count", hard_ok, "three distinct target snapshots" if plan["mode"] == "hard" else "focused mode")
    fixture_manifests: dict[str, dict] = {}
    try:
        fixture_manifests = {item["id"]: item for fixture in (accepted / "fixtures").glob("*/fixture.json") if (item := read_json(fixture))["prompt_id"] in prompts}
        matching_fixtures = set(fixture_manifests)
        fixture_ids = set(plan["applicable_fixture_ids"])
        fixture_match = fixture_ids == matching_fixtures
        if not matching_fixtures and fixture_match:
            gates.append({"name": "fixture_applicability", "status": "not-applicable", "detail": plan["fixture_na_reason"]})
        else:
            gate(gates, "fixture_applicability", fixture_match, "accepted matching fixtures declared" if fixture_match else "declared fixtures differ from accepted prompt matches")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        gate(gates, "fixture_applicability", False, str(exc))
    try:
        guard = subprocess.run([sys.executable, "-B", str(accepted / "scripts" / "guardrail_check.py"), "--skill-root", str(candidate), "--json"], capture_output=True, text=True, timeout=30)
        guard_ok = guard.returncode == 0 and read_json_text(guard.stdout).get("valid") is True
        gate(gates, "structural_budgets", guard_ok, "accepted guardrails pass" if guard_ok else "accepted guardrails failed")
    except (OSError, ValueError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        gate(gates, "structural_budgets", False, str(exc))

    try:
        from validate_package import validate

        package_root = relative_directory(manifest, bundle.get("package_repo_root"))
        package_skill = package_root / "code-hygiene-compounder"
        package_ok = tree_digest(package_skill) == candidate_hash and validate(package_root, False)["valid"]
        gate(gates, "package_parity", package_ok, "all editions match candidate" if package_ok else "package validation or candidate parity failed")
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        gate(gates, "package_parity", False, str(exc))

    run_entries = bundle.get("runs")
    if not isinstance(run_entries, list) or not run_entries:
        gate(gates, "matched_trials", False, "runs must be a non-empty array")
        return decision
    expected_keys = {(target, trial, arm) for target in targets for trial in range(1, trials + 1) for arm in ("baseline", "candidate")}
    observed: dict[tuple[str, int, str], dict] = {}
    run_ids: set[str] = set()
    execution_ids: set[str] = set()
    inspected_ids: set[str] = set(target_artifacts.values())
    problems: list[str] = []
    for entry in run_entries:
        try:
            if not isinstance(entry, dict):
                raise ValueError("run entry must be an object")
            key = (entry["target_id"], entry["trial"], entry["arm"])
            if key in observed or key not in expected_keys:
                raise ValueError(f"duplicate or undeclared run: {key}")
            result = artifact_json(paths, entry.get("result_artifact"))
            execution = artifact_json(paths, entry.get("execution_artifact"))
            verification = artifact_json(paths, entry.get("verification_artifact"))
            output_id = entry.get("output_artifact")
            if not isinstance(output_id, str) or output_id not in paths or paths[output_id].stat().st_size == 0:
                raise ValueError("captured output is missing or empty")
            for field, value in (("target_id", key[0]), ("trial", key[1]), ("arm", key[2])):
                if result.get(field) != value or execution.get(field) != value:
                    raise ValueError(f"{field} identity mismatch")
            if execution.get("target_artifact") != target_artifacts[key[0]]:
                raise ValueError("execution target snapshot mismatch")
            run_id = result.get("run_id")
            if not isinstance(run_id, str) or not run_id or run_id in run_ids or execution.get("run_id") != run_id:
                raise ValueError("duplicate or inconsistent run_id")
            run_ids.add(run_id)
            if result.get("schema_version") != 2 or result.get("run_type") != "model-execution":
                raise ValueError("legacy or non-model result is ineligible")
            result_errors, _ = validate_payload(result, known_prompt_ids=suite_ids)
            if result_errors:
                raise ValueError("invalid result: " + "; ".join(result_errors))
            if set(result["prompt_ids"]) != set(prompts):
                raise ValueError("run prompt set differs from predeclared plan")
            if result.get("model") != plan["model"] or result.get("harness") != plan["harness"] or result.get("runtime") != plan["runtime"]:
                raise ValueError("result model, harness, or runtime differs from plan")
            if execution.get("model") != plan["model"] or execution.get("harness") != plan["harness"] or execution.get("runtime") != plan["runtime"]:
                raise ValueError("execution model, harness, or runtime differs from plan")
            expected_skill = current_hash if key[2] == "baseline" else candidate_hash
            if result.get("skill_fingerprint") != expected_skill or execution.get("skill_fingerprint") != expected_skill:
                raise ValueError("result or execution skill fingerprint mismatch")
            if execution.get("fresh_context") is not True or execution.get("process_exit") != 0 or not isinstance(execution.get("argv"), list) or not execution["argv"]:
                raise ValueError("fresh external execution record is incomplete")
            if execution.get("output_artifact") != output_id or execution.get("output_sha256") != digest(paths[output_id]):
                raise ValueError("execution output fingerprint mismatch")
            execution_start = parse_time(execution.get("started_at"))
            execution_end = parse_time(execution.get("ended_at"))
            result_start = parse_time(result.get("started_at"))
            result_end = parse_time(result.get("completed_at"))
            if execution_start < declared_at or not execution_start <= result_start <= result_end <= execution_end:
                raise ValueError("execution happened before plan or has reversed time")
            if verification.get("run_id") != run_id or verification.get("status") != "pass":
                raise ValueError("verification report is missing or failed")
            fixture_results = verification.get("fixture_results")
            if (not isinstance(fixture_results, list) or any(not isinstance(item, dict) for item in fixture_results)
                    or len(fixture_results) != len(plan["applicable_fixture_ids"])
                    or {item.get("fixture_id") for item in fixture_results} != set(plan["applicable_fixture_ids"])):
                raise ValueError("verification does not cover declared applicable fixtures")
            for fixture_entry in fixture_results:
                fixture_id = fixture_entry["fixture_id"]
                fixture = fixture_manifests.get(fixture_id)
                fixture_result_id = fixture_entry.get("result_artifact")
                fixture_result = artifact_json(paths, fixture_result_id)
                inspected_ids.add(fixture_result_id)
                if not fixture or fixture_result.get("fixture_id") != fixture_id or fixture_result.get("outcome") != "pass" or fixture_result.get("resolved") is not True:
                    raise ValueError(f"fixture result missing or failed: {fixture_id}")
                if fixture.get("mode", "repo") == "repo":
                    signature = fixture["baseline_signature"]
                    report = fixture_result.get("test_report")
                    command = fixture_result.get("command")
                    captured = fixture_result.get("stdout_tail")
                    if (fixture_result.get("protected_files_ok") is not True or fixture_result.get("tests_passed") is not True
                            or fixture_result.get("exit_code") != 0 or fixture_result.get("timed_out") is not False
                            or fixture_result.get("framework") != signature["framework"]
                            or not isinstance(command, list) or command[1:] != fixture["test_command"][1:]
                            or not isinstance(captured, str) or parse_test_report(captured, signature["framework"]) != report
                            or not isinstance(report, dict) or not isinstance(report.get("tests_run"), int)
                            or report["tests_run"] < signature["test_count_min"] or report.get("failures") != [] or report.get("errors") != []):
                        raise ValueError(f"fixture execution evidence incomplete: {fixture_id}")
                else:
                    actual_id, expected_id = fixture_entry.get("actual_artifact"), fixture_entry.get("expected_artifact")
                    if actual_id not in paths or expected_id not in paths:
                        raise ValueError(f"transcript artifacts missing: {fixture_id}")
                    inspected_ids.update((actual_id, expected_id))
                    actual_text = paths[actual_id].read_text(encoding="utf-8-sig").casefold()
                    expected_text = paths[expected_id].read_text(encoding="utf-8-sig").casefold()
                    if (fixture_result.get("mode") != "transcript" or fixture_result.get("missing_markers") != []
                            or fixture_result.get("expected_missing_markers") != []
                            or any(marker.casefold() not in actual_text or marker.casefold() not in expected_text for marker in fixture["expected_markers"])):
                        raise ValueError(f"transcript verification incomplete: {fixture_id}")
            for artifact_key in ("result_artifact", "execution_artifact", "output_artifact", "verification_artifact"):
                inspected_ids.add(entry[artifact_key])
            execution_ids.add(entry["execution_artifact"])
            observed[key] = result
        except (KeyError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            problems.append(str(exc))
    matched = not problems and set(observed) == expected_keys
    gate(gates, "matched_trials", matched, "all baseline/candidate pairs present" if matched else "; ".join(problems[:5]) or "missing baseline/candidate trials")
    gate(gates, "execution_capture", matched, "fresh-context records, outputs, and verification inspected" if matched else "execution capture invalid")
    if not plan["applicable_fixture_ids"]:
        gates.append({"name": "fixture_verification", "status": "not-applicable", "detail": plan["fixture_na_reason"]})
    else:
        gate(gates, "fixture_verification", matched, "structured fixture execution evidence present" if matched else "fixture execution evidence incomplete")

    try:
        reviewer = artifact_json(paths, bundle.get("review_artifact"))
        reviewer_record = artifact_json(paths, bundle.get("reviewer_execution_artifact"))
        reviewer_output_id = reviewer_record.get("output_artifact")
        reviewed_ids = reviewer.get("inspected_artifact_ids")
        latest_run_end = max((parse_time(artifact_json(paths, entry["execution_artifact"]).get("ended_at")) for entry in run_entries if isinstance(entry, dict) and entry.get("execution_artifact") in paths), default=declared_at)
        reviewer_ok = (
            reviewer.get("verdict") == "approve" and reviewer.get("independent") is True
            and isinstance(reviewer.get("reviewer_id"), str) and reviewer["reviewer_id"]
            and isinstance(reviewed_ids, list) and all(isinstance(item, str) for item in reviewed_ids)
            and len(reviewed_ids) == len(set(reviewed_ids)) and set(reviewed_ids) == inspected_ids
            and reviewer_record.get("fresh_context") is True
            and reviewer_record.get("process_exit") == 0
            and isinstance(reviewer_record.get("argv"), list) and bool(reviewer_record["argv"])
            and reviewer_record.get("run_id") == reviewer.get("reviewer_run_id")
            and reviewer_record.get("run_id") not in run_ids
            and isinstance(reviewer_output_id, str) and reviewer_output_id in paths
            and paths[reviewer_output_id].stat().st_size > 0
            and reviewer_record.get("output_sha256") == digest(paths[reviewer_output_id])
            and parse_time(reviewer_record.get("started_at")) >= latest_run_end
            and parse_time(reviewer_record.get("ended_at")) >= parse_time(reviewer_record.get("started_at"))
        )
        gate(gates, "independent_review", bool(reviewer_ok), "reviewer inspected run artifacts" if reviewer_ok else "independent reviewer evidence incomplete")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        gate(gates, "independent_review", False, str(exc))

    try:
        source_changed = any(
            digest(current / "references" / name) != digest(candidate / "references" / name)
            for name in ("training-lessons.md", "source-registry.md")
        ) or tree_digest(current / "references" / "source-packs") != tree_digest(candidate / "references" / "source-packs")
    except (OSError, ValueError) as exc:
        gate(gates, "source_grounding", False, f"source comparison unavailable: {exc}")
        source_changed = None
    if source_changed is not None and source_changed and plan.get("source_backed") is not True:
        gate(gates, "source_grounding", False, "source or lesson content changed but plan omits source-backed honing")
    elif source_changed is not None and plan.get("source_backed") is True:
        try:
            from validate_honing_report import validate_report

            report = artifact_json(paths, bundle.get("honing_artifact"))
            report_errors = validate_report(report)
            gate(gates, "source_grounding", not report_errors, "; ".join(report_errors) if report_errors else "valid honing report")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            gate(gates, "source_grounding", False, str(exc))
    elif source_changed is not None:
        gates.append({"name": "source_grounding", "status": "not-applicable", "detail": "source and lesson content are unchanged"})

    if matched:
        baseline_totals: list[float] = []
        candidate_totals: list[float] = []
        regressions: list[str] = []
        for target in targets:
            for trial in range(1, trials + 1):
                baseline = observed[(target, trial, "baseline")]
                candidate_result = observed[(target, trial, "candidate")]
                before = {item["prompt_id"]: item for item in baseline["scores"]}
                after = {item["prompt_id"]: item for item in candidate_result["scores"]}
                if set(before) != set(after) or not set(critical).issubset(before):
                    regressions.append(f"prompt set mismatch: {target}/{trial}")
                    continue
                for prompt_id, old in before.items():
                    new = after[prompt_id]
                    baseline_totals.append(float(old["total"]))
                    candidate_totals.append(float(new["total"]))
                    if prompt_id in critical:
                        for category in CRITICAL_CATEGORIES:
                            if new["categories"][category] < old["categories"][category]:
                                regressions.append(f"critical regression: {target}/{trial}/{prompt_id}/{category}")
        average_before = mean(baseline_totals) if baseline_totals else None
        average_after = mean(candidate_totals) if candidate_totals else None
        comparison_ok = not regressions and average_after is not None and average_before is not None and average_after >= average_before and average_after >= PROMOTION_THRESHOLD
        gate(gates, "baseline_comparison", comparison_ok, "zero regression and candidate average >= 85" if comparison_ok else "; ".join(regressions[:5]) or "average regressed or below 85")
        improvement = plan["improvement"]
        if improvement["type"] == "score":
            improved = average_after is not None and average_before is not None and average_after > average_before
        else:
            improved = average_after is not None and average_before is not None and average_after == average_before and (candidate / "SKILL.md").stat().st_size < (current / "SKILL.md").stat().st_size
        gate(gates, "predeclared_improvement", improved, "predeclared gain observed" if improved else "declared gain not observed")
        decision["baseline_average"] = average_before
        decision["candidate_average"] = average_after
    else:
        gate(gates, "baseline_comparison", False, "matched trials unavailable")
        gate(gates, "predeclared_improvement", False, "matched trials unavailable")

    decision["promotion_ready"] = all(item["status"] in ("pass", "not-applicable") for item in gates)
    return decision


def read_json_text(text: str) -> dict:
    payload = loads_strict(text)
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object")
    return payload
