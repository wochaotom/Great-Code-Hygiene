"""Release archives must not vary with source timestamps."""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "code-hygiene-compounder" / "scripts"
sys.path.insert(0, str(SCRIPTS))

from export_claude_package import copy_tree, export_claude_ai_skill, zip_dir


class ExportDeterminismTests(unittest.TestCase):
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
