"""Analysis cannot hide mixed cohorts or manufacture one-sample confidence."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "code-hygiene-compounder" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from analyze_runs import compare_paired_runs, load_valid_payloads, normal_mean_interval, wilson_interval
from internal.policy import CATEGORY_KEYS
from internal.policy import RUBRIC_CAPS


def result(run_id: str, run_type: str) -> dict:
    return {"run_id": run_id, "run_type": run_type, "phase": 0, "prompt_ids": ["HYG-001"], "scores": [{"prompt_id": "HYG-001", "categories": CATEGORY_KEYS, "total": 100, "deductions": [], "lessons": []}]}


class AnalysisContractTests(unittest.TestCase):
    def test_mixed_runtime_cohort_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = [Path(temp) / f"run-{index}.json" for index in (1, 2)]
            for index, path in enumerate(paths, 1):
                payload = result(f"run-{index}", "model-execution")
                payload.update(schema_version=2, target_id=f"target-{index}", trial=1, arm="candidate", model="test-model", harness="test-harness", runtime={"os": "windows", "python": "3.13", "node": str(23 + index), "codex": "test"}, skill_version="0.3.0", started_at="2026-01-01T00:00:00Z", completed_at="2026-01-01T00:01:00Z")
                payload["scores"][0]["rubric_flags"] = {key: False for key in RUBRIC_CAPS}
                path.write_text(json.dumps(payload), encoding="utf-8")
            _, validations = load_valid_payloads(paths, None, None)
            self.assertTrue(any("mixed run cohort" in error for item in validations for error in item["errors"]))

    def test_single_observation_has_no_estimated_interval(self) -> None:
        self.assertIsNone(normal_mean_interval([90.0], 0.0, 100.0)["low"])
        self.assertIsNone(wilson_interval(1, 1)["low"])

    def test_mixed_run_types_and_duplicate_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / "first.json", Path(temp) / "second.json"
            first.write_text(json.dumps(result("same", "script-only")), encoding="utf-8")
            second.write_text(json.dumps(result("same", "audit-backed")), encoding="utf-8")
            _, validations = load_valid_payloads([first, second], None, None)
            self.assertTrue(any(not item["valid"] for item in validations))

    def test_missing_trial_pair_is_rejected(self) -> None:
        plan = {"target_ids": ["target-a"], "trial_count": 2, "critical_prompt_ids": ["HYG-001"]}
        baseline = [{"target_id": "target-a", "trial": 1, "scores": [{"prompt_id": "HYG-001", "total": 90, "categories": CATEGORY_KEYS}]}]
        candidate = [{"target_id": "target-a", "trial": 1, "scores": [{"prompt_id": "HYG-001", "total": 100, "categories": CATEGORY_KEYS}]}]
        comparison, errors = compare_paired_runs(candidate, baseline, plan)
        self.assertTrue(errors)
        self.assertIsNone(comparison)

    def test_paired_runs_must_match_predeclared_prompt_set(self) -> None:
        plan = {"target_ids": ["target-a"], "trial_count": 1, "prompt_ids": ["HYG-001"], "critical_prompt_ids": ["HYG-001"]}
        baseline = [{"target_id": "target-a", "trial": 1, "scores": [{"prompt_id": "HYG-001", "total": 90, "categories": CATEGORY_KEYS}, {"prompt_id": "HYG-002", "total": 90, "categories": CATEGORY_KEYS}]}]
        candidate = [{"target_id": "target-a", "trial": 1, "scores": [{"prompt_id": "HYG-001", "total": 100, "categories": CATEGORY_KEYS}, {"prompt_id": "HYG-002", "total": 100, "categories": CATEGORY_KEYS}]}]
        baseline[0].update(schema_version=2, arm="baseline", run_type="model-execution")
        candidate[0].update(schema_version=2, arm="candidate", run_type="model-execution")
        comparison, errors = compare_paired_runs(candidate, baseline, plan)
        self.assertIsNone(comparison)
        self.assertTrue(errors)


if __name__ == "__main__":
    unittest.main()
