"""Release archives must not vary with source timestamps."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "code-hygiene-compounder" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from export_claude_package import copy_tree, export_claude_ai_skill, validate_export_paths, zip_dir
from internal.evidence import tree_digest, unsafe_link


class ExportDeterminismTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "junctions are Windows-specific")
    def test_windows_junction_is_rejected_even_without_path_is_junction(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, outside = root / "source", root / "outside"
            source.mkdir()
            outside.mkdir()
            (outside / "secret.txt").write_text("private", encoding="utf-8")
            junction = source / "linked"
            created = subprocess.run(["cmd", "/c", "mklink", "/J", str(junction), str(outside)], capture_output=True, text=True)
            if created.returncode != 0:
                self.skipTest(f"junction creation unavailable: {created.stderr}")
            self.assertTrue(unsafe_link(junction))
            with self.assertRaisesRegex(ValueError, "unsafe link"):
                tree_digest(source)

    def test_cli_repeatable_export_rejects_later_user_edits(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            command = [sys.executable, "-B", str(SCRIPTS / "export_claude_package.py"),
                       "--skill-root", str(SCRIPTS.parent), "--out-dir", str(root),
                       "--zip-name", "smoke.zip", "--format", "claude-ai-skill"]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 0, first.stderr)
            original_hash = hashlib.sha256((root / "smoke.zip").read_bytes()).hexdigest()
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(hashlib.sha256((root / "smoke.zip").read_bytes()).hexdigest(), original_hash)
            changed = root / "smoke" / "code-hygiene-compounder" / "references" / ".great-code-hygiene-export.json"
            changed.write_text("keep", encoding="utf-8")
            third = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(third.returncode, 0)
            self.assertEqual(changed.read_text(encoding="utf-8"), "keep")

    def test_export_rejects_output_that_contains_skill_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            skill = root / "repository" / "code-hygiene-compounder"
            skill.mkdir(parents=True)
            with self.assertRaises(SystemExit):
                validate_export_paths(skill, root / "repository", root / "repository.zip")
            self.assertTrue(skill.is_dir())

    def test_cli_preserves_unowned_existing_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "smoke"
            output.mkdir()
            keep = output / "keep.txt"
            keep.write_text("user data", encoding="utf-8")
            completed = subprocess.run([
                sys.executable, "-B", str(SCRIPTS / "export_claude_package.py"),
                "--skill-root", str(SCRIPTS.parent), "--out-dir", str(root),
                "--zip-name", "smoke.zip", "--format", "claude-ai-skill",
            ], capture_output=True, text=True)
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(keep.read_text(encoding="utf-8"), "user data")

    def test_copy_rejects_source_symlink_before_replacing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, destination = root / "source", root / "destination"
            source.mkdir()
            destination.mkdir()
            (destination / "keep.txt").write_text("original", encoding="utf-8")
            outside = root / "secret.txt"
            outside.write_text("private", encoding="utf-8")
            try:
                (source / "leak.txt").symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with self.assertRaisesRegex(ValueError, "unsafe export link"):
                copy_tree(source, destination)
            self.assertEqual((destination / "keep.txt").read_text(encoding="utf-8"), "original")

    def test_real_claude_export_is_repeatable_and_contains_internal_modules(self) -> None:
        source = SCRIPTS.parent
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            hashes = []
            for index in (1, 2):
                package = root / f"package-{index}"
                export_claude_ai_skill(source, package)
                archive = root / f"package-{index}.zip"
                zip_dir(package, archive)
                hashes.append(hashlib.sha256(archive.read_bytes()).hexdigest())
                with zipfile.ZipFile(archive) as zipped:
                    names = set(zipped.namelist())
                    self.assertIn("code-hygiene-compounder/scripts/internal/evidence.py", names)
                    self.assertFalse(any("__pycache__" in name for name in names))
            self.assertEqual(hashes[0], hashes[1])

    def test_plugin_mirror_excludes_nested_claude_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, destination = root / "source", root / "plugin"
            (source / ".claude-plugin").mkdir(parents=True)
            (source / ".claude-plugin" / "plugin.json").write_text("{}", encoding="utf-8")
            (source / "SKILL.md").write_text("skill", encoding="utf-8")
            copy_tree(source, destination, extra_excludes=(".claude-plugin",))
            self.assertTrue((destination / "SKILL.md").is_file())
            self.assertFalse((destination / ".claude-plugin").exists())

    def test_archive_hash_ignores_source_mtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            file = source / "SKILL.md"
            file.write_text("skill", encoding="utf-8")
            first, second = root / "first.zip", root / "second.zip"
            zip_dir(source, first)
            os.utime(file, (1_800_000_000, 1_800_000_000))
            zip_dir(source, second)
            self.assertEqual(hashlib.sha256(first.read_bytes()).digest(), hashlib.sha256(second.read_bytes()).digest())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), ["SKILL.md"])


if __name__ == "__main__":
    unittest.main()
