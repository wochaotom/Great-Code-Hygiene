#!/usr/bin/env python3
"""Run tiny executable hygiene fixtures for objective PASS-100 signals."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
sys.dont_write_bytecode = True
from pass100_runner import load_prompts
ALLOWED_BASELINE_EXPECTATIONS = {"fail", "pass"}
ALLOWED_MODES = {"repo", "transcript"}
RESULT_PREFIX = "CODE_HYGIENE_TEST_RESULT="
EVENT_PREFIX = "CODE_HYGIENE_TEST_EVENT="


def parse_test_report(stdout: str, framework: str) -> dict | None:
    if framework == "python-unittest":
        lines = [line[len(RESULT_PREFIX):] for line in stdout.splitlines() if line.startswith(RESULT_PREFIX)]
        if len(lines) != 1:
            return None
        try:
            report = json.loads(lines[0])
        except json.JSONDecodeError:
            return None
        return report if isinstance(report, dict) and report.get("framework") == framework else None
    if framework == "node-test":
        try:
            events = [json.loads(line[len(EVENT_PREFIX):]) for line in stdout.splitlines() if line.startswith(EVENT_PREFIX)]
        except json.JSONDecodeError:
            return None
        if any(not isinstance(event, dict) for event in events):
            return None
        summaries = [event for event in events if event.get("event") == "test:summary"]
        if len(summaries) != 1:
            return None
        counts = summaries[0].get("counts")
        if not isinstance(counts, dict):
            return None
        result_events = [event for event in events if event.get("event") in {"test:pass", "test:fail"}]
        if any(event.get("test_type") not in {"test", "suite"} for event in result_events):
            return None
        suite_errors = [event for event in result_events if event.get("test_type") == "suite" and event.get("event") == "test:fail"]
        test_events = [event for event in result_events if event.get("test_type") == "test"]
        if any(not isinstance(event.get("name"), str) or not event["name"] for event in result_events):
            return None
        failures = [event for event in test_events if event.get("event") == "test:fail" and event.get("error_code") == "ERR_ASSERTION"]
        errors = [event for event in test_events if event.get("event") == "test:fail" and event not in failures]
        return {
            "framework": framework,
            "tests_run": counts.get("tests"),
            "skipped": counts.get("skipped", 0),
            "todo": counts.get("todo", 0),
            "failures": sorted(event["name"] for event in failures),
            "errors": sorted(event["name"] for event in errors),
            "suite_errors": sorted(event["name"] for event in suite_errors),
            "passed": sorted(event["name"] for event in test_events if event.get("event") == "test:pass" and not event.get("skip") and not event.get("todo")),
        }
    return None


def executed_test_count(report: dict) -> int | None:
    count = report.get("tests_run")
    exclusions = [report.get(key, 0) for key in ("skipped", "todo", "expected_failures")]
    if (not isinstance(count, int) or isinstance(count, bool) or count < 0
            or any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in exclusions)):
        return None
    executed = count - sum(exclusions)
    if executed < 0:
        return None
    identities = [report.get(key) for key in ("passed", "failures", "errors")]
    if executed == 0 and any(item is None for item in identities):
        return 0
    if any(not isinstance(item, list) or any(not isinstance(value, str) or not value for value in item) for item in identities):
        return None
    all_ids = [identity for group in identities for identity in group]
    return executed if len(all_ids) == executed and len(set(all_ids)) == executed else None


def classify_test_outcome(command_result: dict, signature: dict) -> dict:
    if command_result.get("timed_out"):
        return {"outcome": "timeout", "signature_matched": False}
    if command_result.get("infrastructure_error"):
        return {"outcome": "infrastructure_error", "signature_matched": False}
    report = command_result.get("test_report")
    if not isinstance(report, dict):
        return {"outcome": "unexpected_test_error", "signature_matched": False}
    if report.get("suite_errors"):
        return {"outcome": "unexpected_test_error", "signature_matched": False}
    if signature.get("framework") and report.get("framework") != signature["framework"]:
        return {"outcome": "unexpected_test_error", "signature_matched": False}
    count = executed_test_count(report)
    if count is None:
        return {"outcome": "unexpected_test_error", "signature_matched": False}
    if count == 0:
        return {"outcome": "no_tests", "signature_matched": False}
    failures = report.get("failures")
    errors = report.get("errors")
    if not isinstance(failures, list) or not isinstance(errors, list):
        return {"outcome": "unexpected_test_error", "signature_matched": False}
    if count < signature.get("test_count_min", 1) or errors:
        return {"outcome": "unexpected_test_error", "signature_matched": False}
    if failures:
        expected = signature.get("expected_failures")
        matched = isinstance(expected, list) and sorted(expected) == sorted(failures) and isinstance(command_result.get("exit_code"), int) and command_result["exit_code"] != 0
        return {"outcome": "expected_assertion_failure" if matched else "unexpected_test_error", "signature_matched": matched}
    expected = signature.get("expected_failures", [])
    passed = report.get("passed")
    if expected and (not isinstance(passed, list) or not set(expected).issubset(passed)):
        return {"outcome": "unexpected_test_error", "signature_matched": False}
    return {"outcome": "pass" if command_result.get("exit_code") == 0 else "unexpected_test_error", "signature_matched": False}
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    return payload


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

def file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]

def load_fixtures(fixtures: Path) -> list[dict]:
    fixtures = fixtures.resolve()
    manifests = sorted(fixtures.glob("*/fixture.json"))
    items: list[dict] = []
    for manifest in manifests:
        item = read_json(manifest)
        item["_manifest_path"] = str(manifest)
        item["_fixture_root"] = str(manifest.parent)
        items.append(item)
    return items

def require_string(item: dict, key: str, label: str, errors: list[str]) -> None:
    value = item.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label}.{key} must be a non-empty string")

def validate_command(value: object, label: str, errors: list[str]) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{label}.test_command must be a non-empty array")
        return
    invalid_parts = False
    for index, part in enumerate(value):
        if not isinstance(part, str) or not part.strip():
            errors.append(f"{label}.test_command[{index}] must be a non-empty string")
            invalid_parts = True
    if invalid_parts:
        return
    python_discovery = len(value) == 6 and value[:5] == ["{python}", "-m", "unittest", "discover", "-s"]
    node_test = len(value) == 3 and value[:2] == ["node", "--test"]
    if not (python_discovery or node_test):
        errors.append(f"{label}.test_command must use supported structured unittest discovery or node --test form")

def fixture_mode(item: dict) -> str:
    return item["mode"] if "mode" in item and isinstance(item["mode"], str) else ("repo" if "mode" not in item else "invalid")

def validate_fixture(item: dict, known_prompt_ids: set[str] | None) -> list[str]:
    fixture_id = item.get("id")
    label = fixture_id if isinstance(fixture_id, str) and fixture_id else item.get("_manifest_path", "fixture")
    errors: list[str] = []
    mode = fixture_mode(item)
    for key in ("id", "prompt_id", "category", "title", "pass_stat"):
        require_string(item, key, str(label), errors)
    if mode not in ALLOWED_MODES:
        errors.append(f"{label}.mode must be one of: {', '.join(sorted(ALLOWED_MODES))}")
    if item.get("baseline_expected") not in ALLOWED_BASELINE_EXPECTATIONS:
        errors.append(f"{label}.baseline_expected must be fail or pass")
    if mode == "repo":
        require_string(item, "repo_dir", str(label), errors)
        validate_command(item.get("test_command"), str(label), errors)
        signature = item.get("baseline_signature")
        if item.get("baseline_expected") == "fail":
            if not isinstance(signature, dict):
                errors.append(f"{label}.baseline_signature must declare expected assertion failures")
            elif not isinstance(signature.get("expected_failures"), list) or not signature["expected_failures"]:
                errors.append(f"{label}.baseline_signature.expected_failures must be non-empty")
            elif any(not isinstance(name, str) or not name for name in signature["expected_failures"]):
                errors.append(f"{label}.baseline_signature.expected_failures values must be non-empty strings")
            if isinstance(signature, dict):
                if signature.get("framework") not in {"python-unittest", "node-test"}:
                    errors.append(f"{label}.baseline_signature.framework is unsupported")
                count_min = signature.get("test_count_min")
                if not isinstance(count_min, int) or isinstance(count_min, bool) or count_min < 1:
                    errors.append(f"{label}.baseline_signature.test_count_min must be positive")
                failures = signature.get("expected_failures")
                if isinstance(failures, list) and all(isinstance(name, str) for name in failures) and len(failures) != len(set(failures)):
                    errors.append(f"{label}.baseline_signature.expected_failures must be unique")
    if mode == "transcript":
        markers = item.get("expected_markers")
        if not isinstance(markers, list) or not markers:
            errors.append(f"{label}.expected_markers must be a non-empty array")
        elif any(not isinstance(marker, str) or not marker.strip() for marker in markers):
            errors.append(f"{label}.expected_markers values must be non-empty strings")
        if item.get("baseline_expected") == "fail":
            signature = item.get("baseline_signature")
            missing = signature.get("expected_missing_markers") if isinstance(signature, dict) else None
            if not isinstance(missing, list) or not missing or any(not isinstance(marker, str) or not marker.strip() for marker in missing):
                errors.append(f"{label}.baseline_signature.expected_missing_markers must be a non-empty string array")
            elif isinstance(markers, list) and (len(set(missing)) != len(missing) or not set(missing).issubset(markers)):
                errors.append(f"{label}.baseline_signature.expected_missing_markers must be unique expected markers")

    prompt_id = item.get("prompt_id")
    if known_prompt_ids is not None and isinstance(prompt_id, str) and prompt_id not in known_prompt_ids:
        errors.append(f"{label}.prompt_id is not in the prompt suite: {prompt_id}")
    root = Path(str(item.get("_fixture_root", "")))
    repo_dir = item.get("repo_dir")
    if mode == "repo" and isinstance(repo_dir, str):
        repo_path = root / repo_dir
        if not repo_path.is_dir():
            errors.append(f"{label}.repo_dir does not exist: {repo_dir}")
    if mode == "transcript":
        missing = [name for name in ("transcript.actual.md", "transcript.expected.md") if not (root / name).is_file()]
        errors.extend(f"{label}.{name} does not exist" for name in missing)
    protected = item.get("protected_files", [])
    if protected is None:
        protected = []
    if not isinstance(protected, list):
        errors.append(f"{label}.protected_files must be an array when present")
    else:
        for index, relative in enumerate(protected):
            if not isinstance(relative, str) or not relative.strip():
                errors.append(f"{label}.protected_files[{index}] must be a non-empty string")
                continue
            if mode == "repo" and isinstance(repo_dir, str) and not (root / repo_dir / relative).is_file():
                errors.append(f"{label}.protected_files[{index}] does not exist: {relative}")
    return errors

def load_known_prompt_ids(suite: Path | None) -> set[str] | None:
    if suite is None:
        return None
    return {prompt["id"] for prompt in load_prompts(suite)}

def find_fixture(fixtures: Path, fixture_id: str) -> dict:
    for item in load_fixtures(fixtures):
        if item.get("id") == fixture_id:
            return item
    raise SystemExit(f"Unknown fixture id: {fixture_id}")


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def validate_prepare_target(item: dict, target: Path, force: bool) -> Path:
    resolved = target.resolve(strict=False)
    repo_root = Path.cwd().resolve()
    fixture_root_path = Path(str(item["_fixture_root"]))
    source_root = (fixture_root_path / str(item["repo_dir"]) if fixture_mode(item) == "repo" else fixture_root_path).resolve(strict=True)
    dangerous_roots = {repo_root, Path.home().resolve(), Path(resolved.anchor).resolve()}
    protected_roots = {
        repo_root / ".git",
        repo_root / ".github",
        repo_root / "code-hygiene-compounder",
        repo_root / "code-hygiene-compounder-claude-ai",
        repo_root / "code-hygiene-compounder-command",
        repo_root / "portable-prompts",
    }
    scratch_roots = {repo_root / ".fixture-work", repo_root / "runs"}
    if resolved in dangerous_roots:
        raise SystemExit(f"refusing to prepare fixture into dangerous target: {resolved}")
    for protected in protected_roots:
        if is_relative_to(resolved, protected) or is_relative_to(protected, resolved):
            raise SystemExit(f"refusing to prepare fixture into tracked package/control path: {resolved}")
    if is_relative_to(source_root, resolved) or is_relative_to(resolved, source_root):
        raise SystemExit("refusing to prepare fixture inside its source tree")
    if resolved.exists() and force and not any(is_relative_to(resolved, root) for root in scratch_roots):
        raise SystemExit(f"refusing --force outside fixture scratch roots: {resolved}")
    if resolved.exists() and not force:
        raise SystemExit(f"target already exists: {resolved}")
    return resolved


def command_for_current_python(command: list[str]) -> list[str]:
    return [sys.executable if part == "{python}" else part for part in command]


def structured_command(command: list[str], report_path: Path) -> tuple[list[str], str]:
    internal = Path(__file__).resolve().parent / "internal"
    if len(command) == 6 and command[1:4] == ["-m", "unittest", "discover"] and command[4] == "-s":
        return [command[0], str(internal / "unittest_reporter.py"), command[5], str(report_path)], "python-unittest"
    if len(command) >= 3 and command[1] == "--test":
        return [command[0], f"--test-reporter={(internal / 'node_reporter.mjs').as_uri()}", *command[1:]], "node-test"
    raise SystemExit("fixture test command has no supported structured reporter")


def run_fixture_command(item: dict, target: Path, timeout: int) -> dict:
    command = item.get("test_command")
    if not isinstance(command, list):
        raise SystemExit(f"{item.get('id')}: invalid test_command")
    command = command_for_current_python(command)
    with tempfile.TemporaryDirectory(prefix="hygiene-report-") as report_dir:
        report_path = Path(report_dir) / "result.json"
        effective_command, framework = structured_command(command, report_path)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        started = time.monotonic()
        try:
            completed = subprocess.run(
                effective_command,
                cwd=target,
                text=True,
                capture_output=True,
                timeout=timeout,
                env=env,
            )
            duration_ms = int((time.monotonic() - started) * 1000)
            report = parse_test_report(completed.stdout, framework)
            if framework == "python-unittest":
                try:
                    sidecar = json.loads(report_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    sidecar = None
                if report != sidecar:
                    report = None
            return {
                "command": command,
                "effective_command": effective_command,
                "framework": framework,
                "test_report": report,
                "exit_code": completed.returncode,
                "duration_ms": duration_ms,
                "tests_passed": completed.returncode == 0 and isinstance(report, dict) and (executed_test_count(report) or 0) > 0 and not report.get("failures") and not report.get("errors") and not report.get("suite_errors"),
                "stdout_tail": tail(completed.stdout),
                "stderr_tail": tail(completed.stderr),
                "timed_out": False,
            }
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.monotonic() - started) * 1000)
            return {
                "command": command,
                "effective_command": effective_command,
                "framework": framework,
                "test_report": None,
                "exit_code": None,
                "duration_ms": duration_ms,
                "tests_passed": False,
                "stdout_tail": tail((exc.stdout or b"").decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")),
                "stderr_tail": tail((exc.stderr or b"").decode("utf-8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")),
                "timed_out": True,
            }
        except OSError as exc:
            return {
                "command": command,
                "effective_command": effective_command,
                "framework": framework,
                "test_report": None,
                "exit_code": None,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "tests_passed": False,
                "stdout_tail": "",
                "stderr_tail": str(exc),
                "timed_out": False,
                "infrastructure_error": True,
            }


def protected_file_failures(item: dict, target: Path) -> list[dict]:
    root = Path(str(item["_fixture_root"])) / str(item["repo_dir"])
    failures: list[dict] = []
    def test_paths(tree: Path) -> set[str]:
        return {
            path.relative_to(tree).as_posix()
            for path in (tree / "tests").rglob("*")
            if path.is_file() or path.is_symlink()
        }

    baseline_tests, candidate_tests = test_paths(root), test_paths(target)
    for relative in sorted(candidate_tests - baseline_tests):
        failures.append({"path": relative, "reason": "added test file"})
    for relative in sorted(baseline_tests - candidate_tests):
        failures.append({"path": relative, "reason": "missing test file"})
    for relative in item.get("protected_files", []) or []:
        baseline = root / relative
        candidate = target / relative
        if not candidate.exists():
            failures.append({"path": relative, "reason": "missing"})
            continue
        if not candidate.is_file():
            failures.append({"path": relative, "reason": "not a file"})
            continue
        if file_digest(candidate) != file_digest(baseline):
            failures.append({"path": relative, "reason": "changed"})
    return failures


def run_fixture_target(item: dict, target: Path, timeout: int) -> dict:
    if fixture_mode(item) == "transcript":
        return run_transcript_fixture(item, target)
    if not target.is_dir():
        raise SystemExit(f"target does not exist or is not a directory: {target}")
    command_result = run_fixture_command(item, target, timeout)
    outcome = classify_test_outcome(command_result, item.get("baseline_signature", {}))
    protected_failures = protected_file_failures(item, target)
    resolved = outcome["outcome"] == "pass" and not protected_failures
    return {
        "fixture_id": item["id"],
        "prompt_id": item["prompt_id"],
        "category": item["category"],
        "target": str(target),
        "resolved": resolved,
        "protected_files_ok": not protected_failures,
        "protected_file_failures": protected_failures,
        **outcome,
        **command_result,
    }


def copy_fixture_repo(item: dict, target: Path, force: bool = False) -> None:
    fixture_root_path = Path(str(item["_fixture_root"]))
    source = fixture_root_path / str(item["repo_dir"]) if fixture_mode(item) == "repo" else fixture_root_path
    if target.exists():
        if not force:
            raise SystemExit(f"target already exists: {target}")
        shutil.rmtree(target)
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", ".mypy_cache", "repo"),
    )


def run_transcript_fixture(item: dict, target: Path) -> dict:
    actual_path, expected_path = target / "transcript.actual.md", target / "transcript.expected.md"
    for path in (actual_path, expected_path):
        if not path.is_file():
            raise SystemExit(f"missing {path.name} in target: {target}")
    markers = item.get("expected_markers", [])
    actual_text = actual_path.read_text(encoding="utf-8-sig").casefold()
    expected_text = expected_path.read_text(encoding="utf-8-sig").casefold()
    missing = [marker for marker in markers if isinstance(marker, str) and marker.casefold() not in actual_text]
    expected_missing = [marker for marker in markers if isinstance(marker, str) and marker.casefold() not in expected_text]
    resolved = not missing and not expected_missing
    declared = item.get("baseline_signature", {}).get("expected_missing_markers", [])
    signature_matched = bool(missing) and not expected_missing and sorted(missing) == sorted(declared)
    outcome = "pass" if resolved else "expected_assertion_failure" if signature_matched else "unexpected_test_error"
    return {
        "fixture_id": item["id"],
        "prompt_id": item["prompt_id"],
        "category": item["category"],
        "mode": "transcript",
        "target": str(target),
        "resolved": resolved,
        "outcome": outcome,
        "signature_matched": signature_matched,
        "protected_files_ok": True,
        "missing_markers": missing,
        "expected_missing_markers": expected_missing,
        "actual_transcript": str(actual_path),
        "expected_transcript": str(expected_path),
        "tests_passed": resolved,
    }


def cmd_list(args: argparse.Namespace) -> None:
    items = load_fixtures(args.fixtures)
    payload = {
        "count": len(items),
        "fixtures": [
            {
                "id": item.get("id"),
                "prompt_id": item.get("prompt_id"),
                "category": item.get("category"),
                "title": item.get("title"),
                "baseline_expected": item.get("baseline_expected"),
            }
            for item in items
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


def cmd_validate(args: argparse.Namespace) -> None:
    known_prompt_ids = load_known_prompt_ids(args.suite)
    items = load_fixtures(args.fixtures)
    errors: list[str] = []
    ids: list[str] = []
    for item in items:
        fixture_id = item.get("id")
        if isinstance(fixture_id, str):
            ids.append(fixture_id)
        errors.extend(validate_fixture(item, known_prompt_ids))
    duplicates = sorted({fixture_id for fixture_id in ids if ids.count(fixture_id) > 1})
    if duplicates:
        errors.append("duplicate fixture ids: " + ", ".join(duplicates))
    payload = {"valid": not errors, "count": len(items), "errors": errors}
    print(json.dumps(payload, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(1)


def cmd_prepare(args: argparse.Namespace) -> None:
    item = find_fixture(args.fixtures, args.fixture)
    errors = validate_fixture(item, None)
    if errors:
        raise SystemExit("\n".join(errors))
    target = validate_prepare_target(item, args.target, args.force)
    copy_fixture_repo(item, target, force=args.force)
    print(json.dumps({"fixture_id": item["id"], "target": str(target)}, indent=2, sort_keys=True))


def cmd_run(args: argparse.Namespace) -> None:
    item = find_fixture(args.fixtures, args.fixture)
    errors = validate_fixture(item, None)
    if errors:
        raise SystemExit("\n".join(errors))
    result = run_fixture_target(item, args.target, args.timeout)
    if args.out:
        write_json(args.out, result)
    print(json.dumps(result, indent=2, sort_keys=True))
    if not result["resolved"]:
        raise SystemExit(1)


def default_work_root() -> Path | None:
    env_root = os.environ.get("CODE_HYGIENE_FIXTURE_TMP")
    if env_root:
        return Path(env_root)
    return Path.cwd() / ".fixture-work"


def cmd_baseline(args: argparse.Namespace) -> None:
    items = load_fixtures(args.fixtures)
    results: list[dict] = []
    work_root = args.work_root or default_work_root()
    created_work_root = False
    if work_root:
        created_work_root = not work_root.exists()
        work_root.mkdir(parents=True, exist_ok=True)
    temp_root = work_root / f"hygiene-fixtures-{uuid.uuid4().hex[:12]}"
    try:
        temp_root.mkdir(parents=True)
        for item in items:
            errors = validate_fixture(item, None)
            if errors:
                results.append({"fixture_id": item.get("id"), "valid": False, "errors": errors})
                continue
            target = temp_root / str(item["id"])
            copy_fixture_repo(item, target)
            result = run_fixture_target(item, target, args.timeout)
            expected = item["baseline_expected"]
            result["baseline_expected"] = expected
            result["expected_outcome_met"] = (
                (expected == "fail" and result.get("outcome") == "expected_assertion_failure" and result["protected_files_ok"])
                or (expected == "pass" and result["resolved"])
            )
            results.append(result)
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
        if work_root and created_work_root:
            try:
                work_root.rmdir()
            except OSError:
                pass

    confirmed = sum(1 for item in results if item.get("expected_outcome_met"))
    payload = {
        "checked_at": utc_now(),
        "valid": confirmed == len(results) and bool(results),
        "count": len(results),
        "expected_outcomes_confirmed": confirmed,
        "results": results,
    }
    if args.out:
        write_json(args.out, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not payload["valid"]:
        raise SystemExit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage executable hygiene fixtures.")
    parser.add_argument("--fixtures", type=Path, default=Path("fixtures"))
    parser.add_argument("--timeout", type=int, default=30)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="List fixture metadata.")
    list_parser.set_defaults(func=cmd_list)

    validate_parser = subparsers.add_parser("validate", help="Validate fixture metadata.")
    validate_parser.add_argument("--suite", type=Path)
    validate_parser.set_defaults(func=cmd_validate)

    prepare_parser = subparsers.add_parser("prepare", help="Copy a fixture repo to a target directory.")
    prepare_parser.add_argument("--fixture", required=True)
    prepare_parser.add_argument("--target", type=Path, required=True)
    prepare_parser.add_argument("--force", action="store_true")
    prepare_parser.set_defaults(func=cmd_prepare)

    run_parser = subparsers.add_parser("run", help="Run a fixture against an edited target repo.")
    run_parser.add_argument("--fixture", required=True)
    run_parser.add_argument("--target", type=Path, required=True)
    run_parser.add_argument("--out", type=Path)
    run_parser.set_defaults(func=cmd_run)

    baseline_parser = subparsers.add_parser("baseline", help="Confirm baseline fixtures fail or pass as declared.")
    baseline_parser.add_argument("--out", type=Path)
    baseline_parser.add_argument("--work-root", type=Path)
    baseline_parser.set_defaults(func=cmd_baseline)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
