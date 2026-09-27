"""Validate versioned promotion evidence against controls outside a candidate tree."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from statistics import mean

from internal.policy import CATEGORY_KEYS, CRITICAL_CATEGORIES, PROMOTION_THRESHOLD
from internal.json_integrity import loads_strict
from fixture_runner import classify_test_outcome, executed_test_count, parse_test_report
from pass100_runner import load_prompts
from validate_results import SOURCE_ID_FALLBACKS, load_source_ids, validate_payload


SKIP_NAMES = frozenset({"runs", "__pycache__", ".pytest_cache", ".mypy_cache", ".fixture-work", ".fixture-tmp", ".git"})
PACKAGE_ROOTS = frozenset({"SKILL.md", ".claude-plugin", "agents", "fixtures", "references", "scripts"})
FOLDED_SKIP_NAMES = frozenset(name.casefold() for name in SKIP_NAMES) | {"dist"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
CONTROL_PATHS = (
    ".claude-plugin/plugin.json", "agents", "fixtures", "scripts",
    "references/eval-prompts.md", "references/PASS-100.md",
    "references/source-weights.json", "references/context-index.schema.json",
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            value.update(chunk)
    return value.hexdigest()


def unsafe_link(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(metadata.st_mode) or bool(
        os.name == "nt" and getattr(metadata, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
    )


def exact_path(root: Path, relative: str) -> bool:
    current = root
    for part in Path(relative).parts:
        if part not in os.listdir(current):
            return False
        current /= part
    return True


def reject_excluded_directories(root: Path) -> None:
    def fail(error: OSError) -> None:
        raise error

    for current, dirs, files in os.walk(root, onerror=fail):
        base = Path(current)
        names = dirs + files
        if len({name.casefold() for name in names}) != len(names):
            raise ValueError(f"candidate contains case-colliding siblings: {base}")
        for name in names:
            path = base / name
            if unsafe_link(path):
                raise ValueError(f"candidate contains unsafe link: {path}")
            if name.casefold() in FOLDED_SKIP_NAMES or (name.casefold() == ".claude-plugin" and base != root):
                raise ValueError(f"candidate contains excluded path: {path}")
            if base == root and name not in PACKAGE_ROOTS:
                raise ValueError(f"candidate contains unexpected root path: {path}")


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
        dirs[:] = sorted(name for name in dirs if name.casefold() not in FOLDED_SKIP_NAMES)
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


def instruction_sizes(root: Path) -> tuple[int, int]:
    references = root / "references"
    if not references.is_dir():
        raise ValueError(f"missing instruction references: {references}")
    if not (root / "SKILL.md").is_file():
        raise ValueError(f"missing instruction file: {root / 'SKILL.md'}")
    total = significant = 0

    def fail(error: OSError) -> None:
        raise error

    for subtree in (root / "SKILL.md", references):
        if subtree.is_file():
            files_to_count = [subtree]
        elif subtree.is_dir():
            files_to_count = []
            for current, dirs, files in os.walk(subtree, onerror=fail):
                base = Path(current)
                for name in dirs:
                    if unsafe_link(base / name):
                        raise ValueError(f"unsafe instruction path: {base / name}")
                dirs[:] = [name for name in dirs if name.casefold() not in FOLDED_SKIP_NAMES and name.casefold() != ".claude-plugin"]
                files_to_count.extend(
                    base / name for name in files
                    if name.casefold() not in FOLDED_SKIP_NAMES
                    and (base != references or name not in {"context-index.json", "context-index.schema.json", "source-weights.json"})
                )
        else:
            continue
        for path in files_to_count:
            if unsafe_link(path) or not path.is_file():
                raise ValueError(f"unsafe instruction file: {path}")
            content = path.read_bytes()
            total += len(content)
            significant += sum(byte not in b" \t\r\n\f\v" for byte in content)
    return total, significant


def instruction_bytes(root: Path) -> int:
    return instruction_sizes(root)[0]


def read_json(path: Path) -> dict:
    payload = loads_strict(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def artifact_registry(manifest: Path, entries: object) -> tuple[dict[str, Path], list[str]]:
    errors: list[str] = []
    paths: dict[str, Path] = {}
    seen_paths: set[str] = set()
    seen_physical_files: set[tuple[int, int]] = set()
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
            metadata = resolved.stat()
            physical_file = (metadata.st_dev, metadata.st_ino)
            if metadata.st_ino and physical_file in seen_physical_files:
                errors.append(f"{label}.path reuses a physical file")
                continue
        except OSError as exc:
            errors.append(f"{label}.sha256 cannot be verified: {exc}")
            continue
        if metadata.st_ino:
            seen_physical_files.add(physical_file)
        paths[identity] = resolved
    return paths, errors


def control_hashes(accepted_root: Path) -> dict[str, str]:
    if not all(exact_path(accepted_root, relative) for relative in CONTROL_PATHS):
        raise ValueError(f"control path casing differs from accepted layout: {accepted_root}")
    return {
        "suite": digest(accepted_root / "references" / "eval-prompts.md"),
        "rubric": digest(accepted_root / "references" / "PASS-100.md"),
        "policy": digest(accepted_root / "scripts" / "internal" / "policy.py"),
        "weights": digest(accepted_root / "references" / "source-weights.json"),
        "plugin_manifest": tree_digest(accepted_root / ".claude-plugin"),
        "index_schema": digest(accepted_root / "references" / "context-index.schema.json"),
        "agents": tree_digest(accepted_root / "agents"),
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


PROMOTION_GATES = (
    "bundle_format", "artifact_integrity", "skill_fingerprints", "accepted_controls",
    "candidate_control_isolation", "predeclared_plan", "focused_selection",
    "source_registry", "hard_target_count", "fixture_applicability",
    "structural_budgets", "package_parity", "matched_trials", "execution_capture",
    "fixture_verification", "independent_review", "source_grounding",
    "baseline_comparison", "predeclared_improvement",
)


def incomplete_decision(decision: dict) -> dict:
    gates = decision["gates"]
    reported = {item["name"] for item in gates}
    blocker = next((item["name"] for item in reversed(gates) if item["status"] == "fail"), "an earlier gate")
    for name in PROMOTION_GATES:
        if name not in reported:
            gate(gates, name, False, f"not evaluated after {blocker}")
    return decision


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


def verify_transcript_fixture(fixture: dict, result: dict, entry: dict, paths: dict[str, Path], output_id: str, accepted_expected: Path, baseline_failure: bool) -> bool:
    actual_id, expected_id = entry.get("actual_artifact"), entry.get("expected_artifact")
    if (actual_id != output_id or expected_id == actual_id or expected_id not in paths
            or actual_id not in paths or digest(paths[expected_id]) != digest(accepted_expected)):
        return False
    actual_text = paths[actual_id].read_text(encoding="utf-8-sig").casefold()
    expected_text = paths[expected_id].read_text(encoding="utf-8-sig").casefold()
    markers = fixture["expected_markers"]
    missing = [marker for marker in markers if marker.casefold() not in actual_text]
    expected_missing = [marker for marker in markers if marker.casefold() not in expected_text]
    declared = fixture["baseline_signature"]["expected_missing_markers"] if baseline_failure else []
    return (
        result.get("mode") == "transcript"
        and result.get("missing_markers") == missing
        and result.get("expected_missing_markers") == expected_missing == []
        and sorted(missing) == sorted(declared)
    )


def evaluate_bundle(manifest: Path, current: Path, candidate: Path, accepted_root: Path) -> dict:
    gates: list[dict] = []
    decision = {"schema_version": 2, "bundle": str(manifest), "promotion_ready": False, "gates": gates}
    try:
        manifest_bytes = manifest.read_bytes()
        bundle = loads_strict(manifest_bytes.decode("utf-8-sig"))
        if not isinstance(bundle, dict):
            raise ValueError("expected JSON object")
        decision["evidence_bundle_sha256"] = hashlib.sha256(manifest_bytes).hexdigest()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        gate(gates, "bundle_format", False, str(exc))
        return incomplete_decision(decision)
    if bundle.get("schema_version") != 2 or isinstance(bundle.get("schema_version"), bool) or "diagnostic_only" in bundle:
        gate(gates, "bundle_format", False, "schema_version must be 2 and diagnostic-only markers are not allowed")
        return incomplete_decision(decision)
    gate(gates, "bundle_format", True, "v2 bundle")
    paths, errors = artifact_registry(manifest, bundle.get("artifacts"))
    gate(gates, "artifact_integrity", not errors, "; ".join(errors) if errors else f"{len(paths)} hashed artifacts")
    if errors:
        return incomplete_decision(decision)

    try:
        reject_excluded_directories(candidate)
        current_hash, candidate_hash = tree_digest(current), tree_digest(candidate)
        stable = bundle.get("baseline_fingerprint") == current_hash and bundle.get("candidate_fingerprint") == candidate_hash and current_hash != candidate_hash
        gate(gates, "skill_fingerprints", stable, "candidate and baseline tree hashes match" if stable else "tree fingerprint mismatch")
        if stable:
            decision["baseline_fingerprint"] = current_hash
            decision["candidate_fingerprint"] = candidate_hash
    except (OSError, ValueError) as exc:
        gate(gates, "skill_fingerprints", False, str(exc))
        return incomplete_decision(decision)

    try:
        accepted = accepted_root.resolve(strict=True)
        candidate_resolved = candidate.resolve(strict=True)
        separated = accepted != candidate_resolved and candidate_resolved not in accepted.parents and accepted not in candidate_resolved.parents
        actual_controls = control_hashes(accepted)
        baseline_controls_match = control_hashes(current) == actual_controls
        controls_ok = separated and baseline_controls_match and bundle.get("controls") == actual_controls
        gate(gates, "accepted_controls", controls_ok,
             "controls match the baseline and external verifier" if controls_ok else "external verifier is not anchored to baseline controls")
        candidate_controls = all(exact_path(candidate, relative) for relative in CONTROL_PATHS) and tree_digest(candidate / "scripts") == tree_digest(accepted / "scripts") and tree_digest(candidate / "fixtures") == actual_controls["fixtures"] and tree_digest(candidate / ".claude-plugin") == actual_controls["plugin_manifest"] and tree_digest(candidate / "agents") == actual_controls["agents"] and digest(candidate / "references" / "context-index.schema.json") == actual_controls["index_schema"] and all(
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
        suite_prompts = load_prompts(accepted / "references" / "eval-prompts.md")
        suite_ids = {item["id"] for item in suite_prompts}
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
        return incomplete_decision(decision)
    if not valid_plan:
        return incomplete_decision(decision)

    categories = plan.get("categories")
    suite_categories = {item["category"] for item in suite_prompts}
    selected_categories = set(categories) if isinstance(categories, list) and all(isinstance(item, str) for item in categories) else set()
    expected_prompts = {item["id"] for item in suite_prompts if item["category"] in selected_categories}
    selection_ok = (
        isinstance(categories, list) and bool(categories) and len(categories) == len(selected_categories)
        and selected_categories.issubset(suite_categories) and set(prompts) == expected_prompts
    )
    gate(gates, "focused_selection", selection_ok,
         "complete predeclared categories selected" if selection_ok else "promotion prompts must cover whole declared categories")

    try:
        source_ids = load_source_ids(accepted / "references" / "source-weights.json")
        if not source_ids:
            raise ValueError("accepted source registry is unavailable")
        gate(gates, "source_registry", True, "accepted source IDs loaded")
    except (OSError, ValueError, SystemExit) as exc:
        gate(gates, "source_registry", False, str(exc))
        return incomplete_decision(decision)

    target_hashes = {target: digest(paths[identity]) for target, identity in target_artifacts.items()}
    if plan["mode"] == "hard":
        hard_ok = len(targets) >= 3 and len(set(target_hashes.values())) == len(targets)
        gate(gates, "hard_target_count", hard_ok, "three distinct target snapshots")
    else:
        gates.append({"name": "hard_target_count", "status": "not-applicable", "detail": "focused mode does not require three targets"})
    fixture_manifests: dict[str, dict] = {}
    try:
        fixture_manifests = {}
        for fixture_path in (accepted / "fixtures").glob("*/fixture.json"):
            item = read_json(fixture_path)
            if item["prompt_id"] in prompts:
                item["_accepted_fixture_root"] = str(fixture_path.parent)
                fixture_manifests[item["id"]] = item
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
    except (OSError, ValueError, KeyError, json.JSONDecodeError, SystemExit) as exc:
        gate(gates, "package_parity", False, str(exc))

    run_entries = bundle.get("runs")
    if not isinstance(run_entries, list) or not run_entries:
        gate(gates, "matched_trials", False, "runs must be a non-empty array")
        return incomplete_decision(decision)
    expected_keys = {(target, trial, arm) for target in targets for trial in range(1, trials + 1) for arm in ("baseline", "candidate")}
    observed: dict[tuple[str, int, str], dict] = {}
    run_ids: set[str] = set()
    output_ids: set[str] = set()
    fixture_result_ids: set[str] = set()
    execution_ids: set[str] = set()
    inspected_ids: set[str] = {bundle["plan_artifact"], *target_artifacts.values()}
    if plan.get("source_backed") is True:
        honing_id = bundle.get("honing_artifact")
        if not isinstance(honing_id, str) or honing_id not in paths:
            gate(gates, "source_grounding", False, "source-backed plan lacks a registered honing artifact")
            return incomplete_decision(decision)
        inspected_ids.add(honing_id)
    operator_ids: set[str] = set()
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
            if output_id in output_ids:
                raise ValueError(f"captured output is reused across runs: {output_id}")
            output_ids.add(output_id)
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
            result_errors, _ = validate_payload(result, known_prompt_ids=suite_ids, source_ids=source_ids)
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
            if ("scored_candidate_trial" in execution and execution["scored_candidate_trial"] is not True) or ("scored_candidate_trial" in result and result["scored_candidate_trial"] is not True):
                raise ValueError("unscored diagnostic execution cannot authorize promotion")
            operator_id = execution.get("operator_id")
            if not isinstance(operator_id, str) or not operator_id.strip():
                raise ValueError("execution operator identity is missing")
            operator_ids.add(operator_id)
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
                if fixture_result_id in fixture_result_ids:
                    raise ValueError(f"fixture result is reused across runs: {fixture_result_id}")
                fixture_result_ids.add(fixture_result_id)
                inspected_ids.add(fixture_result_id)
                baseline_failure = key[2] == "baseline" and fixture and fixture.get("baseline_expected") == "fail"
                expected_outcome = "expected_assertion_failure" if baseline_failure else "pass"
                if (not fixture or fixture_result.get("fixture_id") != fixture_id
                        or any(fixture_result.get(field) != value for field, value in (
                            ("run_id", run_id), ("target_id", key[0]), ("trial", key[1]),
                            ("arm", key[2]), ("skill_fingerprint", expected_skill)))
                        or fixture_result.get("outcome") != expected_outcome
                        or fixture_result.get("resolved") is not (not baseline_failure)
                        or fixture_result.get("signature_matched") is not bool(baseline_failure)):
                    raise ValueError(f"fixture result missing or failed: {fixture_id}")
                if fixture.get("mode", "repo") == "repo":
                    signature = fixture["baseline_signature"]
                    report = fixture_result.get("test_report")
                    command = fixture_result.get("command")
                    captured = fixture_result.get("stdout_tail")
                    classification = classify_test_outcome(fixture_result, signature)
                    if (fixture_result.get("protected_files_ok") is not True
                            or fixture_result.get("tests_passed") is not (not baseline_failure)
                            or fixture_result.get("timed_out") is not False
                            or fixture_result.get("framework") != signature["framework"]
                            or not isinstance(command, list) or command[1:] != fixture["test_command"][1:]
                            or not isinstance(captured, str) or parse_test_report(captured, signature["framework"]) != report
                            or not isinstance(report, dict) or executed_test_count(report) is None
                            or executed_test_count(report) < signature["test_count_min"] or report.get("errors") != []
                            or classification["outcome"] != expected_outcome
                            or classification["signature_matched"] is not bool(baseline_failure)):
                        raise ValueError(f"fixture execution evidence incomplete: {fixture_id}")
                else:
                    actual_id, expected_id = fixture_entry.get("actual_artifact"), fixture_entry.get("expected_artifact")
                    if actual_id not in paths or expected_id not in paths:
                        raise ValueError(f"transcript artifacts missing: {fixture_id}")
                    inspected_ids.update((actual_id, expected_id))
                    accepted_expected = Path(fixture["_accepted_fixture_root"]) / "transcript.expected.md"
                    if not verify_transcript_fixture(fixture, fixture_result, fixture_entry, paths, output_id, accepted_expected, baseline_failure):
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
        reviewer_output = artifact_json(paths, reviewer_output_id)
        raw_result = reviewer_output.get("result")
        if isinstance(raw_result, str):
            raw_result = loads_strict(raw_result)
        reviewed_ids = reviewer.get("inspected_artifact_ids")
        inspected_hashes = {identity: digest(paths[identity]) for identity in inspected_ids}
        latest_run_end = max((parse_time(artifact_json(paths, entry["execution_artifact"]).get("ended_at")) for entry in run_entries if isinstance(entry, dict) and entry.get("execution_artifact") in paths), default=declared_at)
        reviewer_ok = (
            reviewer.get("verdict") == "approve" and reviewer.get("independent") is True
            and isinstance(reviewer.get("reviewer_id"), str) and reviewer["reviewer_id"].strip()
            and reviewer["reviewer_id"] not in operator_ids
            and isinstance(reviewed_ids, list) and all(isinstance(item, str) for item in reviewed_ids)
            and len(reviewed_ids) == len(set(reviewed_ids)) and set(reviewed_ids) == inspected_ids
            and reviewer.get("inspected_artifact_hashes") == inspected_hashes
            and reviewer.get("baseline_fingerprint") == current_hash
            and reviewer.get("candidate_fingerprint") == candidate_hash
            and reviewer.get("package_fingerprint") == candidate_hash
            and reviewer.get("controls") == actual_controls
            and reviewer_record.get("fresh_context") is True
            and reviewer_record.get("process_exit") == 0
            and isinstance(reviewer_record.get("argv"), list) and bool(reviewer_record["argv"])
            and reviewer_record.get("run_id") == reviewer.get("reviewer_run_id")
            and reviewer_record.get("reviewer_id") == reviewer.get("reviewer_id")
            and reviewer_record.get("run_id") not in run_ids
            and reviewer_output_id != bundle.get("review_artifact") and reviewer_output_id in paths
            and reviewer_output.get("type") == "result" and reviewer_output.get("is_error") is False
            and reviewer_output.get("session_id") == reviewer_record.get("run_id")
            and isinstance(reviewer_output.get("num_turns"), int) and reviewer_output["num_turns"] >= 1
            and raw_result == reviewer
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
            for name in ("training-lessons.md", "source-registry.md", "source-weights.json",
                         "research-canon.md", "principle-traceability.md", "hygiene-principles.md")
        )
        old_packs = {path.stem: digest(path) for path in (current / "references" / "source-packs").glob("*.md")}
        new_packs = {path.stem: digest(path) for path in (candidate / "references" / "source-packs").glob("*.md")}
        changed_packs = {source_id for source_id in old_packs.keys() | new_packs.keys() if old_packs.get(source_id) != new_packs.get(source_id)}
        source_changed = source_changed or tree_digest(current / "references" / "source-packs") != tree_digest(candidate / "references" / "source-packs")
    except (OSError, ValueError) as exc:
        gate(gates, "source_grounding", False, f"source comparison unavailable: {exc}")
        source_changed = None
        changed_packs = set()
    if source_changed is not None and source_changed and plan.get("source_backed") is not True:
        gate(gates, "source_grounding", False, "source or lesson content changed but plan omits source-backed honing")
    elif source_changed is not None and plan.get("source_backed") is True:
        try:
            from validate_honing_report import validate_report

            report = artifact_json(paths, bundle.get("honing_artifact"))
            report_errors = validate_report(report)
            activated = report.get("activated_sources")
            weighted_ids = source_ids - SOURCE_ID_FALLBACKS
            if not isinstance(activated, list) or any(not isinstance(source_id, str) or source_id not in weighted_ids for source_id in activated):
                report_errors.append("honing report must activate accepted weighted sources")
            weights_doc = loads_strict((accepted / "references" / "source-weights.json").read_text(encoding="utf-8-sig"))
            if not isinstance(weights_doc, dict):
                raise ValueError("accepted source weights are malformed")
            weights = weights_doc.get("weights")
            if not isinstance(weights, list) or any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in weights):
                raise ValueError("accepted source weights are malformed")
            always_ids = {item["id"] for item in weights if item.get("activation") == "always"}
            if isinstance(activated, list) and not always_ids.issubset({item for item in activated if isinstance(item, str)}):
                report_errors.append("honing report omits an always-activated source")
            if isinstance(activated, list) and not changed_packs.issubset({item for item in activated if isinstance(item, str)}):
                report_errors.append("honing report omits a changed source pack")
            if report.get("baseline_fingerprint") != current_hash or report.get("candidate_fingerprint") != candidate_hash:
                report_errors.append("honing report skill fingerprints do not match this candidate")
            if report.get("promotion_decision") != "promote":
                report_errors.append("honing report does not recommend promotion")
            gate(gates, "source_grounding", not report_errors, "; ".join(report_errors) if report_errors else "valid honing report")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            gate(gates, "source_grounding", False, str(exc))
    elif source_changed is not None:
        gates.append({"name": "source_grounding", "status": "not-applicable", "detail": "source and lesson content are unchanged"})

    if matched:
        baseline_totals: list[float] = []
        candidate_totals: list[float] = []
        regressions: list[str] = []
        scores_equal = True
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
                    if any(new["categories"][key] != old["categories"][key] for key in CATEGORY_KEYS):
                        scores_equal = False
                    baseline_totals.append(math.fsum(float(old["categories"][key]) for key in CATEGORY_KEYS))
                    candidate_totals.append(math.fsum(float(new["categories"][key]) for key in CATEGORY_KEYS))
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
            try:
                baseline_bytes, baseline_content = instruction_sizes(current)
                candidate_bytes, candidate_content = instruction_sizes(candidate)
                decision["instruction_bytes"] = {"baseline": baseline_bytes, "candidate": candidate_bytes}
                improved = (average_after is not None and average_before is not None and scores_equal
                            and baseline_bytes - candidate_bytes >= 32 and baseline_content - candidate_content >= 16)
            except (OSError, ValueError):
                improved = False
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
