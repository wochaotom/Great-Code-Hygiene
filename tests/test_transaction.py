"""Promotion installation must preserve the previous skill on failure."""

from __future__ import annotations

import sys
import os
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPTS = Path(__file__).resolve().parents[1] / "code-hygiene-compounder" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from internal.transaction import apply_transaction, journal_path, recover_transaction, write_journal
from internal.evidence import tree_digest


def approved_apply(candidate: Path, current: Path, after_phase=None) -> None:
    apply_transaction(candidate, current, tree_digest(current), tree_digest(candidate), after_phase=after_phase)


class TransactionTests(unittest.TestCase):
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
            self.assertFalse(journal_path(current).exists())

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
            self.assertEqual((current / "SKILL.md").read_text(encoding="utf-8"), "old")

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
