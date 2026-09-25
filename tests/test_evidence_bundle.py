"""Fail-closed evidence bundle contract tests."""

from __future__ import annotations

import json
import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "code-hygiene-compounder" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from internal.evidence import artifact_registry, control_hashes, evaluate_bundle, tree_digest
from internal.policy import CATEGORY_KEYS, RUBRIC_CAPS


class EvidenceBundleTests(unittest.TestCase):
    def test_unreadable_tree_directory_fails_fingerprinting(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)

            def inaccessible(_root, onerror=None):
                if onerror:
                    onerror(PermissionError("directory read denied"))
                return iter(())

            with patch("internal.evidence.os.walk", side_effect=inaccessible):
                with self.assertRaisesRegex(PermissionError, "directory read denied"):
                    tree_digest(root)

    def add_artifact(self, manifest: Path, identity: str, payload: dict) -> None:
        bundle = json.loads(manifest.read_text(encoding="utf-8"))
        path = manifest.parent / f"{identity}.json"
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        bundle["artifacts"].append({"id": identity, "path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        manifest.write_text(json.dumps(bundle), encoding="utf-8")

    def test_unreadable_artifact_is_reported_as_integrity_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            artifact = root / "record.json"
            artifact.write_text("{}", encoding="utf-8")
            manifest = root / "bundle.json"
            entry = [{"id": "record", "path": artifact.name, "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}]
            with patch("internal.evidence.digest", side_effect=OSError("read denied")):
                _, errors = artifact_registry(manifest, entry)
            self.assertTrue(errors)
            self.assertIn("read denied", errors[0])

    def rewrite_artifact(self, manifest: Path, identity: str, transform) -> None:
        bundle = json.loads(manifest.read_text(encoding="utf-8"))
        entry = next(item for item in bundle["artifacts"] if item["id"] == identity)
        path = manifest.parent / entry["path"]
        payload = json.loads(path.read_text(encoding="utf-8"))
        transform(payload)
        path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
        entry["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest.write_text(json.dumps(bundle), encoding="utf-8")

    def make_synthetic_bundle(self, root: Path) -> tuple[Path, Path, Path]:
        current, candidate, package = root / "current", root / "candidate", root / "package"
        for target in (current, candidate):
            shutil.copytree(SCRIPTS.parent, target, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "runs"))
        (candidate / "agents" / "openai.yaml").write_text((candidate / "agents" / "openai.yaml").read_text(encoding="utf-8") + "\n# synthetic change\n", encoding="utf-8")
        package.mkdir()
        shutil.copytree(candidate, package / "code-hygiene-compounder")
        controls = control_hashes(SCRIPTS.parent)
        runtime = {"os": "test-os", "python": "3.13", "node": "24", "codex": "test-cli"}
        artifacts: list[dict] = []

        def add(identity: str, content: object) -> str:
            path = root / f"{identity}.json"
            data = content if isinstance(content, str) else json.dumps(content, sort_keys=True)
            path.write_text(data, encoding="utf-8")
            artifacts.append({"id": identity, "path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
            return identity

        target_artifact = add("target-a-snapshot", "synthetic target source snapshot")
        add("plan", {"schema_version": 2, "declared_at": "2026-01-01T00:00:00Z", "run_type": "model-execution", "mode": "focused", "target_ids": ["target-a"], "target_artifacts": {"target-a": target_artifact}, "trial_count": 1, "prompt_ids": ["HYG-001"], "critical_prompt_ids": ["HYG-001"], "model": "test-model", "harness": "test-harness", "runtime": runtime, "controls": controls, "applicable_fixture_ids": [], "fixture_na_reason": "No fixture maps to synthetic prompt HYG-001", "improvement": {"type": "score"}, "source_backed": False})
        runs = []
        inspected = [target_artifact]
        for arm in ("baseline", "candidate"):
            run_id = f"run-{arm}"
            categories = dict(CATEGORY_KEYS)
            if arm == "baseline":
                categories["maintainability"] = 5
            item = {"prompt_id": "HYG-001", "categories": categories, "total": sum(categories.values()), "deductions": ["baseline gap"] if arm == "baseline" else [], "lessons": [], "rubric_flags": {key: False for key in RUBRIC_CAPS}}
            skill_fingerprint = tree_digest(current if arm == "baseline" else candidate)
            result = {"schema_version": 2, "run_id": run_id, "run_type": "model-execution", "phase": 0, "target_id": "target-a", "trial": 1, "arm": arm, "model": "test-model", "harness": "test-harness", "runtime": runtime, "skill_version": "0.3.0", "skill_fingerprint": skill_fingerprint, "started_at": "2026-01-02T00:00:00Z", "completed_at": "2026-01-02T00:01:00Z", "prompt_ids": ["HYG-001"], "scores": [item]}
            output_id = add(f"output-{arm}", f"captured {arm} model output")
            output_sha = next(entry["sha256"] for entry in artifacts if entry["id"] == output_id)
            execution_id = add(f"execution-{arm}", {"run_id": run_id, "target_id": "target-a", "target_artifact": target_artifact, "trial": 1, "arm": arm, "model": "test-model", "harness": "test-harness", "runtime": runtime, "skill_fingerprint": skill_fingerprint, "fresh_context": True, "process_exit": 0, "argv": ["codex", "exec"], "output_artifact": output_id, "output_sha256": output_sha, "started_at": "2026-01-02T00:00:00Z", "ended_at": "2026-01-02T00:01:00Z"})
            verification_id = add(f"verification-{arm}", {"run_id": run_id, "status": "pass", "fixture_results": []})
            result_id = add(f"result-{arm}", result)
            runs.append({"target_id": "target-a", "trial": 1, "arm": arm, "result_artifact": result_id, "execution_artifact": execution_id, "output_artifact": output_id, "verification_artifact": verification_id})
            inspected.extend((result_id, execution_id, output_id, verification_id))
        reviewer_output = add("reviewer-output", "reviewed all captured records")
        reviewer_sha = next(entry["sha256"] for entry in artifacts if entry["id"] == reviewer_output)
        add("reviewer-execution", {"run_id": "review-run", "fresh_context": True, "process_exit": 0, "argv": ["claude", "-p"], "output_artifact": reviewer_output, "output_sha256": reviewer_sha, "started_at": "2026-01-03T00:00:00Z", "ended_at": "2026-01-03T00:01:00Z"})
        add("review", {"verdict": "approve", "independent": True, "reviewer_id": "independent-test-reviewer", "reviewer_run_id": "review-run", "inspected_artifact_ids": inspected})
        manifest = root / "bundle.json"
        manifest.write_text(json.dumps({"schema_version": 2, "baseline_fingerprint": tree_digest(current), "candidate_fingerprint": tree_digest(candidate), "controls": controls, "plan_artifact": "plan", "review_artifact": "review", "reviewer_execution_artifact": "reviewer-execution", "package_repo_root": "package", "runs": runs, "artifacts": artifacts}, indent=2), encoding="utf-8")
        return manifest, current, candidate

    def test_synthetic_accepted_path_and_tampered_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
                self.assertTrue(decision["promotion_ready"], decision["gates"])
                (Path(temp) / "output-candidate.json").write_text("altered", encoding="utf-8")
                tampered = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
                self.assertFalse(tampered["promotion_ready"])
                self.assertEqual(tampered["gates"][1]["name"], "artifact_integrity")

    def test_mixed_cohort_and_rubric_cap_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "result-candidate", lambda payload: payload.update(run_type="script-only"))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
                self.assertFalse(decision["promotion_ready"])
                self.assertEqual(next(g for g in decision["gates"] if g["name"] == "matched_trials")["status"], "fail")

    def test_candidate_control_and_source_claim_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            rubric = candidate / "references" / "PASS-100.md"
            rubric.write_text(rubric.read_text(encoding="utf-8") + "\nchanged cap\n", encoding="utf-8")
            lesson = candidate / "references" / "training-lessons.md"
            lesson.write_text(lesson.read_text(encoding="utf-8") + "\nunsupported lesson\n", encoding="utf-8")
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
            bundle["candidate_fingerprint"] = tree_digest(candidate)
            manifest.write_text(json.dumps(bundle), encoding="utf-8")
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
                self.assertFalse(decision["promotion_ready"])
                self.assertEqual(next(g for g in decision["gates"] if g["name"] == "candidate_control_isolation")["status"], "fail")
                self.assertEqual(next(g for g in decision["gates"] if g["name"] == "source_grounding")["status"], "fail")

    def test_missing_artifact_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            for path in (current, candidate):
                (path / "SKILL.md").write_text("---\nname: test\ndescription: test\n---\n", encoding="utf-8")
            manifest = root / "bundle.json"
            manifest.write_text(json.dumps({"schema_version": 2, "artifacts": [{"id": "plan", "path": "missing.json", "sha256": "0" * 64}]}), encoding="utf-8")
            decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertTrue(any(gate["status"] == "fail" for gate in decision["gates"]))

    def test_duplicate_json_keys_fail_bundle_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            manifest = root / "bundle.json"
            manifest.write_text('{"schema_version":2,"schema_version":2,"artifacts":[]}', encoding="utf-8")
            decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertEqual(decision["gates"][0]["name"], "bundle_format")
            self.assertEqual(decision["gates"][0]["status"], "fail")

    def test_nonfinite_exponent_fails_bundle_format(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            manifest = root / "bundle.json"
            manifest.write_text('{"schema_version":2,"note":1e999,"artifacts":[]}', encoding="utf-8")
            decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertEqual(decision["gates"][0]["status"], "fail")

    def test_missing_source_reference_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            (candidate / "references" / "training-lessons.md").unlink()
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
            bundle["candidate_fingerprint"] = tree_digest(candidate)
            manifest.write_text(json.dumps(bundle), encoding="utf-8")
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "source_grounding")["status"], "fail")

    def test_execution_must_identify_exact_skill_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "execution-candidate", lambda payload: payload.update(skill_fingerprint="0" * 64))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "execution_capture")["status"], "fail")

    def test_result_must_fall_within_execution_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "result-candidate", lambda payload: payload.update(completed_at="2026-01-02T00:02:00Z"))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "execution_capture")["status"], "fail")

    def test_duplicate_reviewer_inspection_ids_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "review", lambda payload: payload["inspected_artifact_ids"].append(payload["inspected_artifact_ids"][0]))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "independent_review")["status"], "fail")

    def test_fixture_not_applicable_requires_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.pop("fixture_na_reason"))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])

    def test_matching_fixture_cannot_be_waived(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(prompt_ids=["HYG-006"], critical_prompt_ids=["HYG-006"]))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "fixture_applicability")["status"], "fail")

    def test_invented_prompt_cannot_authorize_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(prompt_ids=["HYG-999"], critical_prompt_ids=["HYG-999"]))
            for arm in ("baseline", "candidate"):
                self.rewrite_artifact(manifest, f"result-{arm}", lambda payload: (payload.update(prompt_ids=["HYG-999"]), payload["scores"][0].update(prompt_id="HYG-999")))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "predeclared_plan")["status"], "fail")

    def test_critical_set_cannot_omit_an_evaluated_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(prompt_ids=["HYG-001", "HYG-002"], critical_prompt_ids=["HYG-001"]))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "predeclared_plan")["status"], "fail")

    def test_matching_fixture_requires_verified_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            fixture_id = "hyg-006-currency-rounding"
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(prompt_ids=["HYG-006"], critical_prompt_ids=["HYG-006"], applicable_fixture_ids=[fixture_id]))
            for arm in ("baseline", "candidate"):
                self.rewrite_artifact(manifest, f"result-{arm}", lambda payload: (payload.update(prompt_ids=["HYG-006"]), payload["scores"][0].update(prompt_id="HYG-006")))
                report = {"framework": "python-unittest", "tests_run": 4, "failures": [], "errors": []}
                artifact_id = f"fixture-{arm}"
                self.add_artifact(manifest, artifact_id, {"fixture_id": fixture_id, "outcome": "pass", "resolved": True, "protected_files_ok": True, "tests_passed": True, "exit_code": 0, "timed_out": False, "framework": "python-unittest", "command": [sys.executable, "-m", "unittest", "discover", "-s", "tests"], "stdout_tail": "CODE_HYGIENE_TEST_RESULT=" + json.dumps(report), "test_report": report})
                self.rewrite_artifact(manifest, f"verification-{arm}", lambda payload: payload.update(fixture_results=[{"fixture_id": fixture_id, "result_artifact": artifact_id}]))
                self.rewrite_artifact(manifest, "review", lambda payload: payload["inspected_artifact_ids"].append(artifact_id))
            with patch("validate_package.validate", return_value={"valid": True}):
                passing = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
                self.assertTrue(passing["promotion_ready"], passing["gates"])
                self.rewrite_artifact(manifest, "fixture-candidate", lambda payload: payload.update(outcome="timeout"))
                failing = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(failing["promotion_ready"])

    def test_minimal_fixture_pass_claim_is_not_execution_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            fixture_id = "hyg-006-currency-rounding"
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(prompt_ids=["HYG-006"], critical_prompt_ids=["HYG-006"], applicable_fixture_ids=[fixture_id]))
            for arm in ("baseline", "candidate"):
                self.rewrite_artifact(manifest, f"result-{arm}", lambda payload: (payload.update(prompt_ids=["HYG-006"]), payload["scores"][0].update(prompt_id="HYG-006")))
                self.rewrite_artifact(manifest, f"verification-{arm}", lambda payload: payload.update(fixture_results=[{"fixture_id": fixture_id, "outcome": "pass"}]))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])

    def test_independent_review_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "review", lambda payload: payload.update(verdict="reject"))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "independent_review")["status"], "fail")

    def test_package_parity_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            (Path(temp) / "package" / "code-hygiene-compounder" / "SKILL.md").write_text("wrong", encoding="utf-8")
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "package_parity")["status"], "fail")

    def test_hard_mode_requires_three_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(mode="hard"))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "hard_target_count")["status"], "fail")

    def test_hard_mode_rejects_three_labels_for_one_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(mode="hard", target_ids=["target-a", "target-b", "target-c"], target_artifacts={"target-a": "target-a-snapshot", "target-b": "target-a-snapshot", "target-c": "target-a-snapshot"}))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "hard_target_count")["status"], "fail")

    def test_hard_mode_accepts_three_distinct_snapshots_and_matched_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, current, candidate = self.make_synthetic_bundle(root)
            target_artifacts = {"target-a": "target-a-snapshot"}
            for target in ("target-b", "target-c"):
                snapshot_id = f"{target}-snapshot"
                self.add_artifact(manifest, snapshot_id, {"source": target})
                target_artifacts[target] = snapshot_id
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(mode="hard", target_ids=list(target_artifacts), target_artifacts=target_artifacts))
            added_runs = []
            inspected = ["target-b-snapshot", "target-c-snapshot"]
            for target in ("target-b", "target-c"):
                for arm in ("baseline", "candidate"):
                    run_id = f"run-{target}-{arm}"
                    result = json.loads((root / f"result-{arm}.json").read_text(encoding="utf-8"))
                    result.update(run_id=run_id, target_id=target)
                    result_id = f"result-{target}-{arm}"
                    self.add_artifact(manifest, result_id, result)
                    output_id = f"output-{target}-{arm}"
                    self.add_artifact(manifest, output_id, {"captured": run_id})
                    execution = json.loads((root / f"execution-{arm}.json").read_text(encoding="utf-8"))
                    execution.update(run_id=run_id, target_id=target, target_artifact=target_artifacts[target], output_artifact=output_id, output_sha256=hashlib.sha256((root / f"{output_id}.json").read_bytes()).hexdigest())
                    execution_id = f"execution-{target}-{arm}"
                    self.add_artifact(manifest, execution_id, execution)
                    verification = {"run_id": run_id, "status": "pass", "fixture_results": []}
                    verification_id = f"verification-{target}-{arm}"
                    self.add_artifact(manifest, verification_id, verification)
                    added_runs.append({"target_id": target, "trial": 1, "arm": arm, "result_artifact": result_id, "execution_artifact": execution_id, "output_artifact": output_id, "verification_artifact": verification_id})
                    inspected.extend((result_id, execution_id, output_id, verification_id))
            self.rewrite_artifact(manifest, "review", lambda payload: payload["inspected_artifact_ids"].extend(inspected))
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
            bundle["runs"].extend(added_runs)
            manifest.write_text(json.dumps(bundle), encoding="utf-8")
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertTrue(decision["promotion_ready"], decision["gates"])

    def test_runtime_identity_is_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "execution-candidate", lambda payload: payload["runtime"].update(node="23"))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "execution_capture")["status"], "fail")

    def test_accepted_verifier_fingerprint_covers_internal_modules(self) -> None:
        controls = control_hashes(SCRIPTS.parent)
        self.assertEqual(tree_digest(SCRIPTS), controls["verifier"])

    def test_legacy_score_cannot_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            for path in (current, candidate):
                (path / "SKILL.md").write_text("---\nname: test\ndescription: test\n---\n", encoding="utf-8")
            score = root / "score.json"
            score.write_text(json.dumps({"average": 100, "promotion_ready": True, "run_type": "model-execution", "evidence_warning": {"run_type": "model-execution", "major_promotion_evidence": True}}), encoding="utf-8")
            completed = subprocess.run([sys.executable, "-B", str(SCRIPTS / "promote_candidate.py"), "--current", str(current), "--candidate", str(candidate), "--score", str(score), "--apply"], capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), (candidate / "SKILL.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
