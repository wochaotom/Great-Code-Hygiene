"""Promotion installation must preserve the previous skill on failure."""

from __future__ import annotations

import sys
import os
import json
import subprocess
import io
from contextlib import redirect_stdout
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "code-hygiene-compounder" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from internal.transaction import apply_transaction, journal_path, recover_transaction, write_journal
from internal.evidence import tree_digest
from promote_candidate import main as promote_main


def approved_apply(candidate: Path, current: Path, after_phase=None) -> None:
    apply_transaction(candidate, current, tree_digest(current), tree_digest(candidate), after_phase=after_phase)


class TransactionTests(unittest.TestCase):
    def test_staging_is_journaled_before_copy_and_recoverable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def interrupted_copy(_source, stage, **_kwargs) -> None:
                self.assertTrue(journal_path(current).is_file())
                self.assertEqual(json.loads(journal_path(current).read_text(encoding="utf-8"))["phase"], "staging")
                stage.mkdir()
                (stage / "partial.md").write_text("partial", encoding="utf-8")
                raise SystemExit("interrupted copy")

            with patch("internal.transaction.shutil.copytree", side_effect=interrupted_copy):
                with self.assertRaisesRegex(SystemExit, "interrupted copy"):
                    approved_apply(candidate, current)
            self.assertTrue(journal_path(current).is_file())
            report = {}
            recover_transaction(current, report=report)
            self.assertEqual(report["action"], "cleared_staging")
            self.assertFalse(list(root.glob(".current.promotion-stage-*")))
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")

    def test_journal_keeps_approved_evidence_hash_for_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def interrupt(phase: str) -> None:
                if phase == "prepared":
                    raise RuntimeError("interrupted")

            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                apply_transaction(candidate, current, tree_digest(current), tree_digest(candidate),
                                  after_phase=interrupt, evidence_bundle_sha256="a" * 64)
            state = json.loads(journal_path(current).read_text(encoding="utf-8"))
            self.assertEqual(state["evidence_bundle_sha256"], "a" * 64)

    def test_case_variant_runtime_folder_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")
            history = current / "Runs" / "history.jsonl"
            history.parent.mkdir()
            history.write_text("keep", encoding="utf-8")
            retained = apply_transaction(candidate, current, tree_digest(current), tree_digest(candidate))
            self.assertEqual((current / "Runs" / "history.jsonl").read_text(encoding="utf-8"), "keep")
            self.assertFalse((retained / "Runs").exists())

    def test_failed_first_journal_serialization_leaves_no_journal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")
            with patch("internal.transaction.json.dumps", side_effect=ValueError("serializing")):
                with self.assertRaisesRegex(ValueError, "serializing"):
                    approved_apply(candidate, current)
            self.assertFalse(journal_path(current).exists())
            self.assertFalse(list(root.glob(".current.promotion-stage-*")))

    def test_journal_update_cannot_follow_predictable_temp_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")
            victim = root / "victim.txt"
            victim.write_text("keep", encoding="utf-8")
            predictable = journal_path(current).with_name(journal_path(current).name + ".tmp")
            try:
                predictable.symlink_to(victim)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            approved_apply(candidate, current)
            self.assertEqual(victim.read_text(encoding="utf-8"), "keep")

    @unittest.skipUnless(os.name == "nt", "case-insensitive recovery is Windows-specific")
    def test_recovery_accepts_case_variant_of_target_name(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "skill", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def interrupt(phase: str) -> None:
                if phase == "backed_up":
                    raise RuntimeError("interrupted")

            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                approved_apply(candidate, current, after_phase=interrupt)
            recover_transaction(root / "SKILL")
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")
            self.assertIn("skill", [path.name for path in root.iterdir() if path.is_dir()])
            self.assertFalse(journal_path(current).exists())

    def test_second_writer_cannot_replace_existing_prepared_journal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")
            original_write = write_journal
            interleaved = False

            def race(path: Path, payload: dict, *args, **kwargs) -> None:
                nonlocal interleaved
                if payload["phase"] == "staging" and not interleaved:
                    interleaved = True

                    def interrupt(phase: str) -> None:
                        if phase == "prepared":
                            raise RuntimeError("interrupted competing apply")

                    with self.assertRaisesRegex(RuntimeError, "interrupted competing apply"):
                        approved_apply(candidate, current, after_phase=interrupt)
                original_write(path, payload, *args, **kwargs)

            with patch("internal.transaction.write_journal", side_effect=race):
                with self.assertRaises(FileExistsError):
                    approved_apply(candidate, current)
            self.assertTrue(journal_path(current).is_file())
            self.assertEqual(len(list(root.glob(".current.promotion-stage-*"))), 1)
            recover_transaction(current)
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")

    def test_cli_recovery_writes_requested_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate, log = root / "current", root / "candidate", root / "recovery.jsonl"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def interrupt(phase: str) -> None:
                if phase == "backed_up":
                    raise RuntimeError("interrupted")

            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                approved_apply(candidate, current, after_phase=interrupt)
            completed = subprocess.run([sys.executable, "-B", str(SCRIPTS / "promote_candidate.py"), "--current", str(current), "--recover", "--log", str(log)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["recovered"], True)
            self.assertIn("decided_at", record)
            self.assertEqual(record["action"], "rolled_back")
            self.assertEqual(record["phase"], "backed_up")
            self.assertEqual(record["installed_fingerprint"], tree_digest(current))
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")

    def test_recovery_reports_rollback_when_swap_precedes_phase_update(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate, log = root / "current", root / "candidate", root / "recovery.jsonl"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")
            original = write_journal

            def interrupt(path: Path, payload: dict, **kwargs) -> None:
                if payload["phase"] == "backed_up":
                    raise RuntimeError("before phase update")
                original(path, payload, **kwargs)

            with patch("internal.transaction.write_journal", side_effect=interrupt):
                with self.assertRaisesRegex(RuntimeError, "before phase update"):
                    approved_apply(candidate, current)
            state = json.loads(journal_path(current).read_text(encoding="utf-8"))
            self.assertEqual(state["phase"], "prepared")
            completed = subprocess.run([sys.executable, "-B", str(SCRIPTS / "promote_candidate.py"),
                                        "--current", str(current), "--recover", "--log", str(log)], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            record = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["action"], "rolled_back")
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")

    def test_failed_recovery_is_logged_without_touching_journal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate, log = root / "current", root / "candidate", root / "recovery.jsonl"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def interrupt(phase: str) -> None:
                if phase == "backed_up":
                    raise RuntimeError("interrupted")

            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                approved_apply(candidate, current, after_phase=interrupt)
            journal = journal_path(current)
            backup = Path(json.loads(journal.read_text(encoding="utf-8"))["backup"])
            (backup / "SKILL.md").write_text("changed backup", encoding="utf-8")
            completed = subprocess.run([sys.executable, "-B", str(SCRIPTS / "promote_candidate.py"), "--current", str(current), "--recover", "--log", str(log)], capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertTrue(journal.is_file())
            record = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(record["recovered"], False)
            self.assertIn("backup fingerprint mismatch", record["error"])

    def test_failed_apply_is_logged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate, log = root / "current", root / "candidate", root / "apply.jsonl"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("---\nname: candidate\ndescription: test\n---\nnew\n", encoding="utf-8")
            decision = {"promotion_ready": True, "baseline_fingerprint": tree_digest(current),
                        "candidate_fingerprint": tree_digest(candidate), "evidence_bundle_sha256": "a" * 64, "gates": []}
            argv = ["promote_candidate.py", "--current", str(current), "--candidate", str(candidate),
                    "--evidence-bundle", str(root / "bundle.json"), "--apply", "--log", str(log)]
            with patch.object(sys, "argv", argv), patch("promote_candidate.evaluate_bundle", return_value=decision), patch("promote_candidate.apply_transaction", side_effect=ValueError("injected stage failure")):
                with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()):
                    promote_main()
            record = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
            self.assertFalse(record["applied"])
            self.assertIn("injected stage failure", record["apply_error"])
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")

    def test_started_record_precedes_installation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate, log = root / "current", root / "candidate", root / "apply.jsonl"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("---\nname: candidate\ndescription: test\n---\nnew\n", encoding="utf-8")
            decision = {"promotion_ready": True, "baseline_fingerprint": tree_digest(current),
                        "candidate_fingerprint": tree_digest(candidate), "evidence_bundle_sha256": "a" * 64, "gates": []}
            argv = ["promote_candidate.py", "--current", str(current), "--candidate", str(candidate),
                    "--evidence-bundle", str(root / "bundle.json"), "--apply", "--log", str(log)]

            def assert_started(*_args):
                records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]["event"], "apply_started")
                self.assertEqual(records[0]["candidate_fingerprint"], decision["candidate_fingerprint"])
                raise KeyboardInterrupt()

            with patch.object(sys, "argv", argv), patch("promote_candidate.evaluate_bundle", return_value=decision), patch("promote_candidate.apply_transaction", side_effect=assert_started):
                with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()):
                    promote_main()
            records = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(records[-1]["event"], "apply_failed")

    def test_pending_recovery_is_not_logged_as_applied(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate, log = root / "current", root / "candidate", root / "apply.jsonl"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("---\nname: candidate\ndescription: test\n---\nnew\n", encoding="utf-8")
            decision = {"promotion_ready": True, "baseline_fingerprint": tree_digest(current),
                        "candidate_fingerprint": tree_digest(candidate), "evidence_bundle_sha256": "a" * 64, "gates": []}
            argv = ["promote_candidate.py", "--current", str(current), "--candidate", str(candidate),
                    "--evidence-bundle", str(root / "bundle.json"), "--apply", "--log", str(log)]

            def fail_after_install(*_args, **_kwargs):
                (current / "SKILL.md").write_bytes((candidate / "SKILL.md").read_bytes())
                journal_path(current).write_text(json.dumps({"phase": "installed"}), encoding="utf-8")
                raise ValueError("runtime move failed")

            with patch.object(sys, "argv", argv), patch("promote_candidate.evaluate_bundle", return_value=decision), patch("promote_candidate.apply_transaction", side_effect=fail_after_install):
                with self.assertRaises(SystemExit), redirect_stdout(io.StringIO()):
                    promote_main()
            record = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
            self.assertFalse(record["applied"])
            self.assertEqual(record["journal_phase"], "installed")
            self.assertEqual(record["installation_state"], "candidate-pending-recovery")

    def test_recovery_accepts_same_aliased_parent_used_for_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            real, alias = root / "real", root / "alias"
            real.mkdir()
            try:
                alias.symlink_to(real, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            current, candidate = alias / "current", alias / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def interrupt(phase: str) -> None:
                if phase == "backed_up":
                    raise RuntimeError("interrupted")

            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                approved_apply(candidate, current, after_phase=interrupt)
            recover_transaction(current)
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")

    def test_journal_bytes_are_flushed_before_swap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            journal = Path(temp) / "journal.json"
            with patch("internal.transaction.os.fsync", wraps=os.fsync) as flush:
                write_journal(journal, {"phase": "prepared"})
            self.assertGreaterEqual(flush.call_count, 1)
            self.assertEqual(__import__("json").loads(journal.read_text(encoding="utf-8"))["phase"], "prepared")

    def test_candidate_changed_after_approval_is_not_installed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("approved", encoding="utf-8")
            old_hash, approved_hash = tree_digest(current), tree_digest(candidate)
            (candidate / "SKILL.md").write_text("unreviewed", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "approved candidate fingerprint"):
                apply_transaction(candidate, current, old_hash, approved_hash)
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")

    def test_current_changed_after_staging_is_preserved_without_journal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("approved", encoding="utf-8")

            def user_edit(phase: str) -> None:
                if phase == "prepared":
                    (current / "SKILL.md").write_text("user edit", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "approved baseline fingerprint changed before swap"):
                approved_apply(candidate, current, after_phase=user_edit)
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "user edit")
            self.assertFalse(journal_path(current).exists())

    def test_runtime_data_changed_after_staging_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")
            (current / "runs").mkdir()
            (current / "runs" / "evidence.json").write_text("before", encoding="utf-8")

            def runtime_edit(phase: str) -> None:
                if phase == "prepared":
                    (current / "runs" / "evidence.json").write_text("after", encoding="utf-8")

            approved_apply(candidate, current, after_phase=runtime_edit)
            self.assertEqual((current / "runs" / "evidence.json").read_text(encoding="utf-8"), "after")

    def test_runtime_data_changed_after_install_before_transfer_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")
            (current / "runs").mkdir()
            (current / "runs" / "evidence.json").write_text("before", encoding="utf-8")

            def runtime_edit(phase: str) -> None:
                if phase == "installed":
                    state = __import__("json").loads(journal_path(current).read_text(encoding="utf-8"))
                    (Path(state["backup"]) / "runs" / "evidence.json").write_text("after", encoding="utf-8")

            approved_apply(candidate, current, after_phase=runtime_edit)
            self.assertEqual((current / "runs" / "evidence.json").read_text(encoding="utf-8"), "after")

    def test_partial_runtime_transfer_recovers_original_and_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")
            (current / "runs").mkdir()
            (current / "runs" / "evidence.json").write_text("retained", encoding="utf-8")
            (current / ".pytest_cache").mkdir()
            (current / ".pytest_cache" / "state").write_text("retained cache", encoding="utf-8")

            def interrupt(phase: str) -> None:
                if phase == "runtime_moved":
                    raise RuntimeError("injected runtime interruption")

            with self.assertRaisesRegex(RuntimeError, "injected runtime interruption"):
                approved_apply(candidate, current, after_phase=interrupt)
            recover_transaction(current)
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")
            self.assertEqual((current / "runs" / "evidence.json").read_text(encoding="utf-8"), "retained")
            self.assertEqual((current / ".pytest_cache" / "state").read_text(encoding="utf-8"), "retained cache")

    def test_new_runtime_data_in_backup_blocks_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def late_writer(phase: str) -> None:
                if phase == "committed":
                    state = __import__("json").loads(journal_path(current).read_text(encoding="utf-8"))
                    (Path(state["backup"]) / "runs").mkdir()
                    (Path(state["backup"]) / "runs" / "late.json").write_text("late", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "runtime data remains in backup"):
                approved_apply(candidate, current, after_phase=late_writer)
            self.assertTrue(journal_path(current).exists())
            with self.assertRaisesRegex(ValueError, "runtime data remains in backup"):
                recover_transaction(current)

    def test_late_write_after_backup_check_is_retained(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")
            from internal.transaction import ensure_no_runtime_data

            def late_write(backup: Path) -> None:
                ensure_no_runtime_data(backup)
                (backup / "runs").mkdir()
                (backup / "runs" / "late.json").write_text("late", encoding="utf-8")

            with patch("internal.transaction.ensure_no_runtime_data", side_effect=late_write):
                retained_backup = apply_transaction(candidate, current, tree_digest(current), tree_digest(candidate))
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "new")
            self.assertEqual((retained_backup / "runs" / "late.json").read_text(encoding="utf-8"), "late")
            self.assertFalse(journal_path(current).exists())

    def test_candidate_link_is_rejected_before_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")
            alias = root / "candidate-link"
            try:
                alias.symlink_to(candidate, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")
            with self.assertRaisesRegex(ValueError, "link or junction"):
                apply_transaction(alias, current, tree_digest(current), tree_digest(candidate))
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")

    def test_success_preserves_runtime_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")
            (current / "runs").mkdir()
            (current / "runs" / "evidence.json").write_text("retained", encoding="utf-8")
            approved_apply(candidate, current)
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "new")
            self.assertEqual((current / "runs" / "evidence.json").read_text(encoding="utf-8"), "retained")
            self.assertFalse(journal_path(current).exists())

    def test_success_retains_executable_caches_only_in_backup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")
            cache = current / "scripts" / "internal" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "evidence.pyc").write_bytes(b"old bytecode")
            dist = current / "scripts" / "dist"
            dist.mkdir()
            (dist / "payload.py").write_text("print('old')\n", encoding="utf-8")
            backup = apply_transaction(candidate, current, tree_digest(current), tree_digest(candidate))
            self.assertFalse((current / "scripts" / "internal" / "__pycache__").exists())
            self.assertFalse((current / "scripts" / "dist").exists())
            self.assertEqual((backup / "scripts" / "internal" / "__pycache__" / "evidence.pyc").read_bytes(), b"old bytecode")
            self.assertTrue((backup / "scripts" / "dist" / "payload.py").is_file())
            self.assertFalse(journal_path(current).exists())

    def test_nested_runtime_data_is_preserved_and_backup_is_clean(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            (current / "references" / "runs").mkdir(parents=True)
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")
            (current / "references" / "runs" / "evidence.json").write_text("retained", encoding="utf-8")
            backup = apply_transaction(candidate, current, tree_digest(current), tree_digest(candidate))
            self.assertEqual((current / "references" / "runs" / "evidence.json").read_text(encoding="utf-8"), "retained")
            self.assertFalse((backup / "references" / "runs").exists())

    def test_nested_runtime_data_in_backup_blocks_committed_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def late_writer(phase: str) -> None:
                if phase == "committed":
                    state = __import__("json").loads(journal_path(current).read_text(encoding="utf-8"))
                    path = Path(state["backup"]) / "references" / "runs"
                    path.mkdir(parents=True)
                    (path / "late.json").write_text("late", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "runtime data remains in backup"):
                approved_apply(candidate, current, after_phase=late_writer)
            self.assertTrue(journal_path(current).exists())

    def test_interrupted_transaction_blocks_and_recovers(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def interrupt(phase: str) -> None:
                if phase == "backed_up":
                    raise RuntimeError("injected interruption")

            old_hash, new_hash = tree_digest(current), tree_digest(candidate)
            with self.assertRaises(RuntimeError):
                apply_transaction(candidate, current, old_hash, new_hash, after_phase=interrupt)
            self.assertTrue(journal_path(current).exists())
            with self.assertRaises(RuntimeError):
                apply_transaction(candidate, current, old_hash, new_hash)
            recover_transaction(current)
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")
            self.assertFalse(journal_path(current).exists())

    def test_each_interruption_phase_recovers_original(self) -> None:
        for interrupted_phase in ("prepared", "backed_up", "installed"):
            with self.subTest(phase=interrupted_phase), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                current, candidate = root / "current", root / "candidate"
                current.mkdir()
                candidate.mkdir()
                (current / "SKILL.md").write_text("old", encoding="utf-8")
                (candidate / "SKILL.md").write_text("new", encoding="utf-8")

                def interrupt(phase: str) -> None:
                    if phase == interrupted_phase:
                        raise RuntimeError("injected interruption")

                with self.assertRaisesRegex(RuntimeError, "injected interruption"):
                    approved_apply(candidate, current, after_phase=interrupt)
                recover_transaction(current)
                self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")
                self.assertFalse(journal_path(current).exists())

    def test_recovery_does_not_discard_user_edits_after_install(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def interrupt(phase: str) -> None:
                if phase == "installed":
                    raise RuntimeError("injected interruption")

            with self.assertRaises(RuntimeError):
                approved_apply(candidate, current, after_phase=interrupt)
            (current / "SKILL.md").write_text("user edit", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed since installation"):
                recover_transaction(current)
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "user edit")
            self.assertTrue(journal_path(current).exists())

    def test_late_runtime_write_during_rollback_is_retained(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def interrupt(phase: str) -> None:
                if phase == "installed":
                    raise RuntimeError("interrupted")

            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                approved_apply(candidate, current, after_phase=interrupt)
            real_replace = os.replace

            def write_before_discard(source, destination):
                if Path(source) == current and ".promotion-discard-" in Path(destination).name:
                    late = current / "Runs" / "late.txt"
                    late.parent.mkdir()
                    late.write_text("preserve", encoding="utf-8")
                return real_replace(source, destination)

            report = {}
            with patch("internal.transaction.os.replace", side_effect=write_before_discard):
                recover_transaction(current, report=report)
            discarded = Path(report["retained_discard"])
            self.assertEqual((discarded / "Runs" / "late.txt").read_text(encoding="utf-8"), "preserve")
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")

    def test_recovery_resumes_after_displacing_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def interrupt(phase: str) -> None:
                if phase == "installed":
                    raise RuntimeError("interrupted")

            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                approved_apply(candidate, current, after_phase=interrupt)
            state = json.loads(journal_path(current).read_text(encoding="utf-8"))
            backup = Path(state["backup"])
            real_replace = os.replace
            blocked = False

            def fail_once(source, destination):
                nonlocal blocked
                if Path(source) == backup and Path(destination) == current and not blocked:
                    blocked = True
                    raise OSError("injected recovery interruption")
                return real_replace(source, destination)

            with patch("internal.transaction.os.replace", side_effect=fail_once):
                with self.assertRaisesRegex(OSError, "injected recovery interruption"):
                    recover_transaction(current)
            self.assertFalse(current.exists())
            report = {}
            recover_transaction(current, report=report)
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")
            self.assertEqual((Path(report["retained_discard"]) / "SKILL.md").read_text(encoding="utf-8"), "new")
            self.assertFalse(journal_path(current).exists())

    def test_committed_cleanup_can_resume_after_partial_backup_removal(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def interrupt(phase: str) -> None:
                if phase == "committed":
                    raise RuntimeError("cleanup interrupted")

            with self.assertRaisesRegex(RuntimeError, "cleanup interrupted"):
                approved_apply(candidate, current, after_phase=interrupt)
            journal = journal_path(current)
            state = __import__("json").loads(journal.read_text(encoding="utf-8"))
            self.assertEqual(state["phase"], "committed")
            (Path(state["backup"]) / "SKILL.md").unlink()
            recover_transaction(current)
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "new")
            self.assertFalse(journal.exists())

    def test_committed_cleanup_can_resume_when_backup_is_already_gone(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def interrupt(phase: str) -> None:
                if phase == "committed":
                    raise RuntimeError("cleanup interrupted")

            with self.assertRaisesRegex(RuntimeError, "cleanup interrupted"):
                approved_apply(candidate, current, after_phase=interrupt)
            journal = journal_path(current)
            state = __import__("json").loads(journal.read_text(encoding="utf-8"))
            (Path(state["backup"]) / "SKILL.md").unlink()
            Path(state["backup"]).rmdir()
            recover_transaction(current)
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "new")
            self.assertFalse(journal.exists())

    def test_committed_recovery_preserves_post_install_user_edit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            current, candidate = root / "current", root / "candidate"
            current.mkdir()
            candidate.mkdir()
            (current / "SKILL.md").write_text("old", encoding="utf-8")
            (candidate / "SKILL.md").write_text("new", encoding="utf-8")

            def interrupt(phase: str) -> None:
                if phase == "committed":
                    raise RuntimeError("cleanup interrupted")

            with self.assertRaises(RuntimeError):
                approved_apply(candidate, current, after_phase=interrupt)
            (current / "SKILL.md").write_text("user edit", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed since installation"):
                recover_transaction(current)
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "user edit")


if __name__ == "__main__":
    unittest.main()
