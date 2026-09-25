"""Regression checks for the v0.3 promotion and evaluation contracts."""

from __future__ import annotations

import sys
import tempfile
import unittest
import json
import shutil
import subprocess
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "code-hygiene-compounder" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from fixture_runner import classify_test_outcome, run_transcript_fixture, validate_fixture
from pass100_runner import CATEGORY_KEYS, cmd_score, load_failure_ids, select_batch
from promote_candidate import validate_apply_target
from source_audit_plan import build_context_index, context_role, context_values, query_context, READ_WHEN_RULES
from validate_results import load_json, validate_payload


def score(prompt_id: str, total: object = 100) -> dict:
    return {
        "prompt_id": prompt_id,
        "categories": dict(CATEGORY_KEYS),
        "total": total,
        "deductions": [],
        "lessons": [],
    }


def result(item: dict) -> dict:
    return {
        "run_id": "test-run",
        "run_type": "script-only",
        "phase": 0,
        "prompt_ids": ["HYG-001"],
        "scores": [item],
    }


class ResultValidationTests(unittest.TestCase):
    def test_duplicate_result_json_keys_are_rejected_by_loading_and_scoring(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "result.json"
            path.write_text('{"run_id":"first","run_id":"second"}', encoding="utf-8")
            with self.assertRaises(SystemExit):
                load_json(path)
            with self.assertRaises(SystemExit):
                cmd_score(__import__("argparse").Namespace(results=path, out=Path(temp) / "score.json", log=None, threshold=85))

    def test_nonfinite_and_boolean_numbers_fail(self) -> None:
        for value in (float("nan"), float("inf"), float("-inf"), True):
            with self.subTest(value=value):
                errors, _ = validate_payload(result(score("HYG-001", value)))
                self.assertTrue(errors)

    def test_nonfinite_category_and_cost_fail(self) -> None:
        item = score("HYG-001")
        item["categories"]["correctness"] = float("nan")
        item["cost_usd"] = float("inf")
        errors, _ = validate_payload(result(item))
        self.assertTrue(any("correctness" in error for error in errors))
        self.assertTrue(any("cost_usd" in error for error in errors))

    def test_nonfinite_nested_metadata_fails(self) -> None:
        payload = result(score("HYG-001"))
        payload["telemetry"] = {"ratio": float("inf")}
        errors, _ = validate_payload(payload)
        self.assertTrue(any("telemetry.ratio" in error for error in errors))

    def test_legacy_result_is_diagnostic_only(self) -> None:
        errors, _ = validate_payload(result(score("HYG-001")))
        self.assertEqual(errors, [])


class PromotionPathTests(unittest.TestCase):
    def test_nested_candidate_or_current_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current = root / "current"
            candidate = current / "candidate"
            candidate.mkdir(parents=True)
            (current / "SKILL.md").write_text("skill", encoding="utf-8")
            (candidate / "SKILL.md").write_text("skill", encoding="utf-8")
            self.assertTrue(validate_apply_target(current, candidate))
            self.assertTrue(validate_apply_target(candidate, current))


class FixtureOutcomeTests(unittest.TestCase):
    def test_assertion_failure_with_success_exit_is_not_confirmed(self) -> None:
        outcome = classify_test_outcome(
            {"exit_code": 0, "test_report": {"framework": "python-unittest", "tests_run": 1, "failures": ["test_contract"], "errors": []}},
            {"framework": "python-unittest", "expected_failures": ["test_contract"], "test_count_min": 1},
        )
        self.assertEqual(outcome["outcome"], "unexpected_test_error")

    def test_transcript_baseline_needs_exact_missing_marker_signature(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "transcript.actual.md").write_text("step one", encoding="utf-8")
            (root / "transcript.expected.md").write_text("step one\nverified", encoding="utf-8")
            fixture = {"id": "transcript-test", "mode": "transcript", "prompt_id": "HYG-001", "category": "tests", "title": "test", "pass_stat": "markers", "baseline_expected": "fail", "expected_markers": ["step one", "verified"], "baseline_signature": {"expected_missing_markers": ["verified"]}, "_fixture_root": str(root)}
            self.assertEqual(validate_fixture(fixture, None), [])
            outcome = run_transcript_fixture(fixture, root)
            self.assertEqual(outcome["outcome"], "expected_assertion_failure")
            self.assertTrue(outcome["signature_matched"])
            fixture["baseline_signature"]["expected_missing_markers"] = ["step one"]
            self.assertEqual(run_transcript_fixture(fixture, root)["outcome"], "unexpected_test_error")

    def test_unrelated_error_does_not_confirm_expected_failure(self) -> None:
        outcome = classify_test_outcome(
            {"exit_code": 1, "timed_out": False, "stdout_tail": "", "stderr_tail": "ImportError: broken environment"},
            {"framework": "python-unittest", "expected_failures": ["test_contract"], "test_count_min": 1},
        )
        self.assertEqual(outcome["outcome"], "unexpected_test_error")

    def test_timeout_does_not_confirm_expected_failure(self) -> None:
        outcome = classify_test_outcome(
            {"exit_code": None, "timed_out": True, "stdout_tail": "", "stderr_tail": ""},
            {"framework": "python-unittest", "expected_failures": ["test_contract"], "test_count_min": 1},
        )
        self.assertEqual(outcome["outcome"], "timeout")


class RoutingTests(unittest.TestCase):
    def test_rules_match_basename_or_directory_not_substrings(self) -> None:
        self.assertEqual(context_role("references/not-SKILL.md"), "reference material")
        self.assertEqual(context_values("references/not-SKILL.md", READ_WHEN_RULES, ("fallback",)), ["fallback"])

    def test_index_is_file_level_and_within_budget(self) -> None:
        root = SCRIPTS.parent
        payload = build_context_index(root)
        self.assertTrue(all("sections" not in entry for entry in payload["files"]))
        self.assertLessEqual(len(__import__("json").dumps(payload, indent=2, sort_keys=True).encode()), 24 * 1024)

    def test_daily_query_is_small_and_source_audit_includes_activated_packs(self) -> None:
        root = SCRIPTS.parent
        daily = query_context(root, "daily", [], None)
        self.assertLessEqual(len(json.dumps(daily).encode("utf-8")), 4 * 1024)
        self.assertEqual({item["path"] for item in daily["files"]}, {"SKILL.md", "references/HYGIENE_QUICK.md", "references/evidence-report.md"})
        audit = query_context(root, "source-audit", ["security"], None)
        self.assertTrue(audit["files"])
        self.assertTrue(all(item["path"].startswith("references/source-packs/") for item in audit["files"]))
        self.assertIn("references/source-packs/owasp-asvs.md", {item["path"] for item in audit["files"]})


class GuardrailTests(unittest.TestCase):
    def test_clean_distributable_passes_budget_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = Path(temp) / "code-hygiene-compounder"
            shutil.copytree(SCRIPTS.parent, clean, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "runs"))
            completed = subprocess.run(
                [sys.executable, "-B", str(SCRIPTS / "guardrail_check.py"), "--skill-root", str(clean), "--json"],
                capture_output=True, text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


class BatchTests(unittest.TestCase):
    def test_regression_history_rejects_duplicate_keys_and_nonfinite_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "failures.json"
            for payload in (
                '{"valid":true,"valid":true,"aggregate":{"low_scores":[{"prompt_id":"HYG-001","total":70}]}}',
                '{"valid":true,"aggregate":{"low_scores":[{"prompt_id":"HYG-001","total":70}],"ratio":NaN}}',
            ):
                with self.subTest(payload=payload):
                    path.write_text(payload, encoding="utf-8")
                    with self.assertRaises(SystemExit):
                        load_failure_ids(path)

    def test_regression_requires_recorded_low_scores(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "failures.json"
            path.write_text(json.dumps({"prompt_ids": ["HYG-001"]}), encoding="utf-8")
            with self.assertRaises(SystemExit):
                load_failure_ids(path)
            path.write_text(json.dumps({"valid": True, "aggregate": {"low_scores": [{"prompt_id": "HYG-001", "total": 70}, {"prompt_id": "HYG-002", "total": 90}]}}), encoding="utf-8")
            self.assertEqual(load_failure_ids(path), {"HYG-001"})

    def test_smoke_covers_all_categories(self) -> None:
        prompts = [{"id": f"HYG-{index:03}", "category": f"category-{index // 10}"} for index in range(100)]
        selected = select_batch(prompts, "smoke", 0, None)
        self.assertEqual(len({item["category"] for item in selected}), 10)


if __name__ == "__main__":
    unittest.main()
