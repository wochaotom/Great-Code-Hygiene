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

from internal.evidence import artifact_registry, control_hashes, evaluate_bundle, instruction_bytes, tree_digest, verify_transcript_fixture
from internal.policy import CATEGORY_KEYS, RUBRIC_CAPS
from pass100_runner import load_prompts


SYNTHETIC_CATEGORY = "Documentation and Comments"
SYNTHETIC_PROMPTS = [item["id"] for item in load_prompts(SCRIPTS.parent / "references" / "eval-prompts.md") if item["category"] == SYNTHETIC_CATEGORY]


class EvidenceBundleTests(unittest.TestCase):
    def test_non_markdown_reference_content_is_counted_for_size_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            current, candidate = Path(temp) / "current", Path(temp) / "candidate"
            for tree in (current, candidate):
                (tree / "references").mkdir(parents=True)
                (tree / "SKILL.md").write_text("Read references/quick.md\n", encoding="utf-8")
                (tree / "references" / "quick.md").write_text("Keep the verification loop deterministic.\n", encoding="utf-8")
            (candidate / "references" / "quick.md").write_text("", encoding="utf-8")
            (candidate / "references" / "quick.txt").write_text("Keep the verification loop deterministic.\n", encoding="utf-8")
            self.assertGreaterEqual(instruction_bytes(candidate), instruction_bytes(current))

    def test_candidate_excluded_directory_cannot_authorize_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            hidden = candidate / "references" / ".git"
            hidden.mkdir()
            (hidden / "guidance.md").write_text("Candidate-only instruction", encoding="utf-8")
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])

    def test_missing_honing_artifact_is_a_logged_gate_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(source_backed=True))
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
            bundle["honing_artifact"] = "not-registered"
            manifest.write_text(json.dumps(bundle), encoding="utf-8")
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "source_grounding")["status"], "fail")

    def test_transcript_evidence_must_use_run_output_and_accepted_expectation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            actual, expected, fake, accepted = (root / name for name in ("actual.md", "expected.md", "fake.md", "accepted.md"))
            actual.write_text("checked regression test", encoding="utf-8")
            expected.write_text("checked regression test", encoding="utf-8")
            fake.write_text("checked regression test", encoding="utf-8")
            accepted.write_text("checked regression test", encoding="utf-8")
            paths = {"actual": actual, "expected": expected, "fake": fake}
            fixture = {"expected_markers": ["checked regression test"], "baseline_signature": {"expected_missing_markers": ["checked regression test"]}}
            result = {"mode": "transcript", "missing_markers": [], "expected_missing_markers": []}
            self.assertTrue(verify_transcript_fixture(fixture, result, {"actual_artifact": "actual", "expected_artifact": "expected"}, paths, "actual", accepted, False))
            self.assertFalse(verify_transcript_fixture(fixture, result, {"actual_artifact": "fake", "expected_artifact": "expected"}, paths, "actual", accepted, False))
            expected.write_text("unaccepted marker text", encoding="utf-8")
            self.assertFalse(verify_transcript_fixture(fixture, result, {"actual_artifact": "actual", "expected_artifact": "expected"}, paths, "actual", accepted, False))
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

    def rebind_review(self, manifest: Path) -> None:
        bundle = json.loads(manifest.read_text(encoding="utf-8"))
        artifacts = {entry["id"]: entry["sha256"] for entry in bundle["artifacts"]}
        review = json.loads((manifest.parent / "review.json").read_text(encoding="utf-8"))
        inspected = review["inspected_artifact_ids"]
        if "plan" not in inspected:
            inspected.append("plan")
        self.rewrite_artifact(manifest, "review", lambda payload: payload.update(
            inspected_artifact_ids=inspected,
            inspected_artifact_hashes={identity: artifacts[identity] for identity in inspected},
            baseline_fingerprint=bundle["baseline_fingerprint"],
            candidate_fingerprint=bundle["candidate_fingerprint"],
            package_fingerprint=bundle["candidate_fingerprint"],
            controls=bundle["controls"],
        ))
        review = json.loads((manifest.parent / "review.json").read_text(encoding="utf-8"))
        self.rewrite_artifact(manifest, "reviewer-output", lambda payload: payload.update(result=json.dumps(review, sort_keys=True)))
        output_hash = hashlib.sha256((manifest.parent / "reviewer-output.json").read_bytes()).hexdigest()
        self.rewrite_artifact(manifest, "reviewer-execution", lambda payload: payload.update(output_artifact="reviewer-output", output_sha256=output_hash, reviewer_id="independent-test-reviewer"))

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
        add("plan", {"schema_version": 2, "declared_at": "2026-01-01T00:00:00Z", "run_type": "model-execution", "mode": "focused", "categories": [SYNTHETIC_CATEGORY], "target_ids": ["target-a"], "target_artifacts": {"target-a": target_artifact}, "trial_count": 1, "prompt_ids": SYNTHETIC_PROMPTS, "critical_prompt_ids": SYNTHETIC_PROMPTS, "model": "test-model", "harness": "test-harness", "runtime": runtime, "controls": controls, "applicable_fixture_ids": [], "fixture_na_reason": "No fixture maps to synthetic documentation category", "improvement": {"type": "score"}, "source_backed": False})
        runs = []
        inspected = [target_artifact, "plan"]
        for arm in ("baseline", "candidate"):
            run_id = f"run-{arm}"
            categories = dict(CATEGORY_KEYS)
            if arm == "baseline":
                categories["maintainability"] = 5
            item = {"prompt_id": SYNTHETIC_PROMPTS[0], "categories": categories, "total": sum(categories.values()), "deductions": ["baseline gap"] if arm == "baseline" else [], "lessons": [], "rubric_flags": {key: False for key in RUBRIC_CAPS}}
            scores = [item]
            for prompt_id in SYNTHETIC_PROMPTS[1:]:
                scores.append({"prompt_id": prompt_id, "categories": dict(CATEGORY_KEYS), "total": 100, "deductions": [], "lessons": [], "rubric_flags": {key: False for key in RUBRIC_CAPS}})
            skill_fingerprint = tree_digest(current if arm == "baseline" else candidate)
            result = {"schema_version": 2, "run_id": run_id, "run_type": "model-execution", "phase": 0, "target_id": "target-a", "trial": 1, "arm": arm, "model": "test-model", "harness": "test-harness", "runtime": runtime, "skill_version": "0.3.0", "skill_fingerprint": skill_fingerprint, "started_at": "2026-01-02T00:00:00Z", "completed_at": "2026-01-02T00:01:00Z", "prompt_ids": SYNTHETIC_PROMPTS, "scores": scores}
            output_id = add(f"output-{arm}", f"captured {arm} model output")
            output_sha = next(entry["sha256"] for entry in artifacts if entry["id"] == output_id)
            execution_id = add(f"execution-{arm}", {"run_id": run_id, "operator_id": "test-operator", "target_id": "target-a", "target_artifact": target_artifact, "trial": 1, "arm": arm, "model": "test-model", "harness": "test-harness", "runtime": runtime, "skill_fingerprint": skill_fingerprint, "fresh_context": True, "process_exit": 0, "argv": ["codex", "exec"], "output_artifact": output_id, "output_sha256": output_sha, "started_at": "2026-01-02T00:00:00Z", "ended_at": "2026-01-02T00:01:00Z"})
            verification_id = add(f"verification-{arm}", {"run_id": run_id, "status": "pass", "fixture_results": []})
            result_id = add(f"result-{arm}", result)
            runs.append({"target_id": "target-a", "trial": 1, "arm": arm, "result_artifact": result_id, "execution_artifact": execution_id, "output_artifact": output_id, "verification_artifact": verification_id})
            inspected.extend((result_id, execution_id, output_id, verification_id))
        inspected_hashes = {entry["id"]: entry["sha256"] for entry in artifacts if entry["id"] in inspected}
        add("review", {"verdict": "approve", "independent": True, "reviewer_id": "independent-test-reviewer", "reviewer_run_id": "review-run", "inspected_artifact_ids": inspected, "inspected_artifact_hashes": inspected_hashes, "baseline_fingerprint": tree_digest(current), "candidate_fingerprint": tree_digest(candidate), "package_fingerprint": tree_digest(candidate), "controls": controls})
        raw_review = add("reviewer-output", {"type": "result", "is_error": False, "session_id": "review-run", "num_turns": 1, "result": json.dumps(json.loads((root / "review.json").read_text(encoding="utf-8")), sort_keys=True)})
        reviewer_sha = next(entry["sha256"] for entry in artifacts if entry["id"] == raw_review)
        add("reviewer-execution", {"run_id": "review-run", "reviewer_id": "independent-test-reviewer", "fresh_context": True, "process_exit": 0, "argv": ["claude", "-p"], "output_artifact": raw_review, "output_sha256": reviewer_sha, "started_at": "2026-01-03T00:00:00Z", "ended_at": "2026-01-03T00:01:00Z"})
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

    def test_reviewer_report_cannot_serve_as_its_own_raw_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            review_hash = hashlib.sha256((Path(temp) / "review.json").read_bytes()).hexdigest()
            self.rewrite_artifact(manifest, "reviewer-execution", lambda payload: payload.update(output_artifact="review", output_sha256=review_hash))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "independent_review")["status"], "fail")

    def test_review_report_must_match_captured_reviewer_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "reviewer-output", lambda payload: payload.update(result='{"verdict":"approve"}'))
            output_hash = hashlib.sha256((Path(temp) / "reviewer-output.json").read_bytes()).hexdigest()
            self.rewrite_artifact(manifest, "reviewer-execution", lambda payload: payload.update(output_sha256=output_hash))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "independent_review")["status"], "fail")

    def test_focused_mode_rejects_one_prompt_subset(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            selected = [SYNTHETIC_PROMPTS[0]]
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(prompt_ids=selected, critical_prompt_ids=selected))
            for arm in ("baseline", "candidate"):
                self.rewrite_artifact(manifest, f"result-{arm}", lambda payload: payload.update(prompt_ids=selected, scores=payload["scores"][:1]))
            self.rebind_review(manifest)
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "focused_selection")["status"], "fail")

    def test_fixture_baseline_failure_and_candidate_pass_are_matched(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, current, candidate = self.make_synthetic_bundle(root)
            fixture_id = "hyg-031-sql-injection"
            prompt_id = "HYG-031"
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(
                prompt_ids=[prompt_id], critical_prompt_ids=[prompt_id], applicable_fixture_ids=[fixture_id], fixture_na_reason="",
            ))
            signature = ["test_users.UserQueryTests.test_injected_role_does_not_return_admins"]
            for arm in ("baseline", "candidate"):
                self.rewrite_artifact(manifest, f"result-{arm}", lambda payload: (
                    payload.update(prompt_ids=[prompt_id], scores=payload["scores"][:1]), payload["scores"][0].update(prompt_id=prompt_id),
                ))
                failure = arm == "baseline"
                report = {"framework": "python-unittest", "tests_run": 2, "skipped": 0, "expected_failures": 0,
                          "failures": signature if failure else [], "errors": [], "passed": ["test_users.UserQueryTests.test_safe_role_returns_users"] if failure else signature + ["test_users.UserQueryTests.test_safe_role_returns_users"]}
                identity = f"fixture-{arm}"
                self.add_artifact(manifest, identity, {
                    "fixture_id": fixture_id, "run_id": f"run-{arm}", "target_id": "target-a", "trial": 1, "arm": arm,
                    "skill_fingerprint": tree_digest(current if failure else candidate),
                    "outcome": "expected_assertion_failure" if failure else "pass", "resolved": not failure,
                    "signature_matched": failure, "protected_files_ok": True, "tests_passed": not failure,
                    "exit_code": 1 if failure else 0, "timed_out": False, "framework": "python-unittest",
                    "command": ["python", "-m", "unittest", "discover", "-s", "tests"],
                    "stdout_tail": "CODE_HYGIENE_TEST_RESULT=" + json.dumps(report, sort_keys=True), "test_report": report,
                })
                self.rewrite_artifact(manifest, f"verification-{arm}", lambda payload: payload.update(
                    fixture_results=[{"fixture_id": fixture_id, "result_artifact": identity}],
                ))
            self.rewrite_artifact(manifest, "review", lambda payload: payload["inspected_artifact_ids"].extend(["fixture-baseline", "fixture-candidate"]))
            self.rebind_review(manifest)
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "matched_trials")["status"], "pass", decision["gates"])

    def test_equal_scores_require_smaller_instruction_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            skill = candidate / "SKILL.md"
            skill.write_text(skill.read_text(encoding="utf-8").rstrip("\n"), encoding="utf-8", newline="\n")
            quick = candidate / "references" / "HYGIENE_QUICK.md"
            quick.write_text(quick.read_text(encoding="utf-8") + "\nAlways inspect the full repository.\n", encoding="utf-8", newline="\n")
            package_skill = Path(temp) / "package" / "code-hygiene-compounder"
            shutil.copy2(skill, package_skill / "SKILL.md")
            shutil.copy2(quick, package_skill / "references" / "HYGIENE_QUICK.md")

            candidate_hash = tree_digest(candidate)
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
            bundle["candidate_fingerprint"] = candidate_hash
            manifest.write_text(json.dumps(bundle), encoding="utf-8")
            self.rewrite_artifact(manifest, "plan", lambda payload: payload["improvement"].update(type="smaller"))
            self.rewrite_artifact(manifest, "result-candidate", lambda payload: (
                payload["scores"][0]["categories"].update(maintainability=5),
                payload["scores"][0].update(total=90, deductions=["baseline gap"]),
                payload.update(skill_fingerprint=candidate_hash),
            ))
            self.rewrite_artifact(manifest, "execution-candidate", lambda payload: payload.update(skill_fingerprint=candidate_hash))

            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(gate for gate in decision["gates"] if gate["name"] == "predeclared_improvement")["status"], "fail")

            quick.write_bytes((current / "references" / "HYGIENE_QUICK.md").read_bytes())
            shutil.copy2(quick, package_skill / "references" / "HYGIENE_QUICK.md")
            candidate_hash = tree_digest(candidate)
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
            bundle["candidate_fingerprint"] = candidate_hash
            manifest.write_text(json.dumps(bundle), encoding="utf-8")
            self.rewrite_artifact(manifest, "result-candidate", lambda payload: payload.update(skill_fingerprint=candidate_hash))
            self.rewrite_artifact(manifest, "execution-candidate", lambda payload: payload.update(skill_fingerprint=candidate_hash))
            self.rebind_review(manifest)
            with patch("validate_package.validate", return_value={"valid": True}):
                smaller = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(smaller["promotion_ready"], smaller["gates"])
            self.assertEqual(next(g for g in smaller["gates"] if g["name"] == "predeclared_improvement")["status"], "fail")

            old_sentence = "Use this skill to make code changes safer, smaller, more testable, and easier to review."
            skill.write_text(skill.read_text(encoding="utf-8").replace(old_sentence, "Use this skill to improve code."), encoding="utf-8", newline="\n")
            shutil.copy2(skill, package_skill / "SKILL.md")
            candidate_hash = tree_digest(candidate)
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
            bundle["candidate_fingerprint"] = candidate_hash
            manifest.write_text(json.dumps(bundle), encoding="utf-8")
            self.rewrite_artifact(manifest, "result-candidate", lambda payload: payload.update(skill_fingerprint=candidate_hash))
            self.rewrite_artifact(manifest, "execution-candidate", lambda payload: payload.update(skill_fingerprint=candidate_hash))
            self.rebind_review(manifest)
            with patch("validate_package.validate", return_value={"valid": True}):
                meaningful = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertTrue(meaningful["promotion_ready"], meaningful["gates"])

    def test_mixed_cohort_and_rubric_cap_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "result-candidate", lambda payload: payload.update(run_type="script-only"))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
                self.assertFalse(decision["promotion_ready"])
                self.assertEqual(next(g for g in decision["gates"] if g["name"] == "matched_trials")["status"], "fail")

    def test_unknown_source_anchor_cannot_authorize_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "result-candidate", lambda payload: payload["scores"][0].update(
                source_anchors=[{"source_id": "not-an-accepted-source", "principle": "test", "evidence": "test"}],
            ))
            self.rebind_review(manifest)
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
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

    def test_modified_external_verifier_must_match_installed_baseline_controls(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, current, candidate = self.make_synthetic_bundle(root)
            accepted = root / "accepted"
            shutil.copytree(SCRIPTS.parent, accepted, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "runs"))
            relative = Path("scripts/internal/policy.py")
            for skill in (accepted, candidate):
                policy = skill / relative
                policy.write_text(policy.read_text(encoding="utf-8") + "\n# altered accepted control\n", encoding="utf-8")
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
            bundle["controls"] = control_hashes(accepted)
            bundle["candidate_fingerprint"] = tree_digest(candidate)
            manifest.write_text(json.dumps(bundle), encoding="utf-8")
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(controls=control_hashes(accepted)))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, accepted)
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "accepted_controls")["status"], "fail")

    def test_modified_external_source_weights_must_match_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, current, candidate = self.make_synthetic_bundle(root)
            accepted = root / "accepted"
            shutil.copytree(SCRIPTS.parent, accepted, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache", "runs"))
            for skill in (accepted, candidate):
                weights = skill / "references" / "source-weights.json"
                weights.write_text(weights.read_text(encoding="utf-8") + "\n", encoding="utf-8")
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
            bundle["controls"] = control_hashes(accepted)
            bundle["candidate_fingerprint"] = tree_digest(candidate)
            manifest.write_text(json.dumps(bundle), encoding="utf-8")
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(controls=control_hashes(accepted)))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, accepted)
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "accepted_controls")["status"], "fail")

    def test_honing_report_must_identify_the_candidate_it_supports(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest, current, candidate = self.make_synthetic_bundle(root)
            lesson = candidate / "references" / "training-lessons.md"
            lesson.write_text(lesson.read_text(encoding="utf-8") + "\n- Synthetic source-backed lesson.\n", encoding="utf-8")
            shutil.copy2(lesson, root / "package" / "code-hygiene-compounder" / "references" / "training-lessons.md")
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
            bundle["candidate_fingerprint"] = tree_digest(candidate)
            manifest.write_text(json.dumps(bundle), encoding="utf-8")
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(source_backed=True))
            for identity in ("result-candidate", "execution-candidate"):
                self.rewrite_artifact(manifest, identity, lambda payload: payload.update(skill_fingerprint=tree_digest(candidate)))
            self.add_artifact(manifest, "honing", {"run_type": "source-grounded", "activated_sources": ["nist-ssdf"], "principles_checked": ["repeatable verification"], "checklist_results": [{"source_id": "nist-ssdf", "checked": ["tests"], "findings": [], "deductions": []}], "pass100_score": 90, "promotion_decision": "promote", "lessons": [{"source_id": "nist-ssdf", "principle": "repeatable verification", "evidence": "synthetic evidence"}]})
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
            bundle["honing_artifact"] = "honing"
            manifest.write_text(json.dumps(bundle), encoding="utf-8")
            self.rewrite_artifact(manifest, "review", lambda payload: payload["inspected_artifact_ids"].append("honing"))
            self.rebind_review(manifest)
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "source_grounding")["status"], "fail")

            self.rewrite_artifact(manifest, "honing", lambda payload: payload.update(
                baseline_fingerprint=tree_digest(current), candidate_fingerprint=tree_digest(candidate),
            ))
            self.rebind_review(manifest)
            with patch("validate_package.validate", return_value={"valid": True}):
                approved = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertTrue(approved["promotion_ready"], approved["gates"])

            self.rewrite_artifact(manifest, "honing", lambda payload: payload.update(promotion_decision="reject"))
            self.rebind_review(manifest)
            with patch("validate_package.validate", return_value={"valid": True}):
                rejected = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertEqual(next(g for g in rejected["gates"] if g["name"] == "source_grounding")["status"], "fail")

            self.rewrite_artifact(manifest, "honing", lambda payload: (
                payload.update(promotion_decision="promote", activated_sources=["invented-source"]),
                payload["checklist_results"][0].update(source_id="invented-source"),
                payload["lessons"][0].update(source_id="invented-source"),
            ))
            self.rebind_review(manifest)
            with patch("validate_package.validate", return_value={"valid": True}):
                unknown_source = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertEqual(next(g for g in unknown_source["gates"] if g["name"] == "source_grounding")["status"], "fail")

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

    def test_captured_output_cannot_be_reused_across_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            shared_output = Path(temp) / "output-baseline.json"
            self.rewrite_artifact(manifest, "execution-candidate", lambda payload: payload.update(
                output_artifact="output-baseline",
                output_sha256=hashlib.sha256(shared_output.read_bytes()).hexdigest(),
            ))
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
            bundle["runs"][1]["output_artifact"] = "output-baseline"
            manifest.write_text(json.dumps(bundle), encoding="utf-8")
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "matched_trials")["status"], "fail")

    def test_fixture_result_cannot_be_claimed_by_another_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            fixture_id = "hyg-006-currency-rounding"
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(prompt_ids=["HYG-006"], critical_prompt_ids=["HYG-006"], applicable_fixture_ids=[fixture_id]))
            for arm in ("baseline", "candidate"):
                self.rewrite_artifact(manifest, f"result-{arm}", lambda payload: (payload.update(prompt_ids=["HYG-006"]), payload["scores"][0].update(prompt_id="HYG-006")))
                report = {"framework": "python-unittest", "tests_run": 4, "failures": [], "errors": []}
                artifact_id = f"fixture-{arm}"
                self.add_artifact(manifest, artifact_id, {"fixture_id": fixture_id, "run_id": "run-baseline", "target_id": "target-a", "trial": 1, "arm": arm, "skill_fingerprint": tree_digest(current if arm == "baseline" else candidate), "outcome": "pass", "resolved": True, "protected_files_ok": True, "tests_passed": True, "exit_code": 0, "timed_out": False, "framework": "python-unittest", "command": [sys.executable, "-m", "unittest", "discover", "-s", "tests"], "stdout_tail": "CODE_HYGIENE_TEST_RESULT=" + json.dumps(report), "test_report": report})
                self.rewrite_artifact(manifest, f"verification-{arm}", lambda payload: payload.update(fixture_results=[{"fixture_id": fixture_id, "result_artifact": artifact_id}]))
                self.rewrite_artifact(manifest, "review", lambda payload: payload["inspected_artifact_ids"].append(artifact_id))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "matched_trials")["status"], "fail")

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

    def test_unknown_reviewer_inspection_id_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "review", lambda payload: payload["inspected_artifact_ids"].append("not-registered"))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertFalse(decision["promotion_ready"])
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "independent_review")["status"], "fail")

    def test_review_cannot_be_reused_after_captured_output_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            output = Path(temp) / "output-candidate.json"
            output.write_text("a different captured candidate output", encoding="utf-8")
            bundle = json.loads(manifest.read_text(encoding="utf-8"))
            next(item for item in bundle["artifacts"] if item["id"] == "output-candidate")["sha256"] = hashlib.sha256(output.read_bytes()).hexdigest()
            manifest.write_text(json.dumps(bundle), encoding="utf-8")
            self.rewrite_artifact(manifest, "execution-candidate", lambda payload: payload.update(output_sha256=hashlib.sha256(output.read_bytes()).hexdigest()))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "independent_review")["status"], "fail")

    def test_review_must_cover_predeclared_plan_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            self.rewrite_artifact(manifest, "plan", lambda payload: payload.update(declared_at="2026-01-01T01:00:00Z"))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertEqual(next(g for g in decision["gates"] if g["name"] == "independent_review")["status"], "fail")

    def test_trial_operator_cannot_review_own_runs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            manifest, current, candidate = self.make_synthetic_bundle(Path(temp))
            for arm in ("baseline", "candidate"):
                self.rewrite_artifact(manifest, f"execution-{arm}", lambda payload: payload.update(operator_id="independent-test-reviewer"))
            with patch("validate_package.validate", return_value={"valid": True}):
                decision = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
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
            signature = json.loads((SCRIPTS.parent / "fixtures" / "hyg-006-currency-rounding" / "fixture.json").read_text(encoding="utf-8"))["baseline_signature"]["expected_failures"]
            for arm in ("baseline", "candidate"):
                self.rewrite_artifact(manifest, f"result-{arm}", lambda payload: (payload.update(prompt_ids=["HYG-006"], scores=payload["scores"][:1]), payload["scores"][0].update(prompt_id="HYG-006")))
                baseline_failure = arm == "baseline"
                other = "test_pricing.PricingTests.test_whole_dollar_total"
                report = {"framework": "python-unittest", "tests_run": 4, "skipped": 0, "expected_failures": 0,
                          "failures": signature if baseline_failure else [], "errors": [],
                          "passed": [other] if baseline_failure else sorted(signature + [other])}
                artifact_id = f"fixture-{arm}"
                self.add_artifact(manifest, artifact_id, {"fixture_id": fixture_id, "run_id": f"run-{arm}", "target_id": "target-a", "trial": 1, "arm": arm, "skill_fingerprint": tree_digest(current if baseline_failure else candidate), "outcome": "expected_assertion_failure" if baseline_failure else "pass", "resolved": not baseline_failure, "signature_matched": baseline_failure, "protected_files_ok": True, "tests_passed": not baseline_failure, "exit_code": 1 if baseline_failure else 0, "timed_out": False, "framework": "python-unittest", "command": [sys.executable, "-m", "unittest", "discover", "-s", "tests"], "stdout_tail": "CODE_HYGIENE_TEST_RESULT=" + json.dumps(report), "test_report": report})
                self.rewrite_artifact(manifest, f"verification-{arm}", lambda payload: payload.update(fixture_results=[{"fixture_id": fixture_id, "result_artifact": artifact_id}]))
                self.rewrite_artifact(manifest, "review", lambda payload: payload["inspected_artifact_ids"].append(artifact_id))
            self.rebind_review(manifest)
            with patch("validate_package.validate", return_value={"valid": True}):
                passing = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
                self.assertFalse(passing["promotion_ready"])
                self.assertEqual(next(g for g in passing["gates"] if g["name"] == "matched_trials")["status"], "pass", passing["gates"])
                self.rewrite_artifact(manifest, "fixture-candidate", lambda payload: payload.update(outcome="timeout"))
                failing = evaluate_bundle(manifest, current, candidate, SCRIPTS.parent)
            self.assertEqual(next(g for g in failing["gates"] if g["name"] == "matched_trials")["status"], "fail")

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
            self.rebind_review(manifest)
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
            diagnostic = subprocess.run([sys.executable, "-B", str(SCRIPTS / "promote_candidate.py"), "--current", str(current), "--candidate", str(candidate), "--score", str(score)], capture_output=True, text=True)
            self.assertNotEqual(diagnostic.returncode, 0)
            self.assertFalse(json.loads(diagnostic.stdout)["promotion_ready"])
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), (candidate / "SKILL.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
