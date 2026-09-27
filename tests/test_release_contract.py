from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "code-hygiene-compounder" / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

import validate_package  # noqa: E402


SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ReleaseContractTests(unittest.TestCase):
    def test_clean_edition_symlink_is_not_accepted_as_package_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = Path(temp) / "repo"
            shutil.copytree(REPO_ROOT, clean, ignore=shutil.ignore_patterns(".git", ".fixture-work", "__pycache__", ".pytest_cache", "runs"))
            outside = Path(temp) / "outside.md"
            outside.write_text("unreviewed", encoding="utf-8")
            link = clean / "code-hygiene" / "outside.md"
            try:
                link.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            report = validate_package.validate(clean, False)
            self.assertFalse(report["valid"])
            self.assertTrue(any("link" in error for error in report["errors"]), report["errors"])

    def test_package_parity_detects_nested_dist_and_extra_claude_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = Path(temp) / "repo"
            shutil.copytree(REPO_ROOT, clean, ignore=shutil.ignore_patterns(".git", ".fixture-work", "__pycache__", ".pytest_cache", "runs"))
            nested = clean / "code-hygiene-compounder-claude-ai" / "code-hygiene-compounder" / "references" / "dist"
            nested.mkdir()
            (nested / "override.md").write_text("unreviewed", encoding="utf-8")
            extra = clean / "code-hygiene-compounder-claude-ai" / "code-hygiene-compounder" / "hooks"
            extra.mkdir()
            (extra / "extra.md").write_text("unreviewed", encoding="utf-8")
            report = validate_package.validate(clean, False)
            self.assertFalse(report["valid"])
            self.assertTrue(any("override.md" in error for error in report["errors"]), report["errors"])
            self.assertTrue(any("hooks" in error for error in report["errors"]), report["errors"])

    def test_clean_repository_package_is_consistent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = Path(temp) / "repo"
            shutil.copytree(REPO_ROOT, clean, ignore=shutil.ignore_patterns(".git", ".fixture-work", "__pycache__", ".pytest_cache", "runs"))
            report = validate_package.validate(clean, False)
            self.assertTrue(report["valid"], report["errors"])

    def test_doctor_is_read_only_and_explicit_runtime_mismatch_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            canonical = root / "code-hygiene-compounder"
            runtime = root / "runtime"
            canonical.mkdir()
            runtime.mkdir()
            (canonical / "SKILL.md").write_text("canonical", encoding="utf-8")
            (runtime / "SKILL.md").write_text("stale", encoding="utf-8")
            with patch("validate_package.validate", return_value={"valid": True, "errors": []}), patch("validate_package.shutil.which", return_value="node"), patch("validate_package.subprocess.run", return_value=CompletedProcess(["node", "--version"], 0, "v24.0.0\n", "")):
                report = validate_package.doctor(root, runtime)
            self.assertFalse(report["valid"])
            self.assertEqual(next(item for item in report["checks"] if item["name"] == "runtime_parity")["status"], "fail")
            self.assertEqual((canonical / "SKILL.md").read_text(encoding="utf-8"), "canonical")
            self.assertEqual((runtime / "SKILL.md").read_text(encoding="utf-8"), "stale")

    def test_full_suite_runs_on_three_platforms_with_node_24(self) -> None:
        workflow = (REPO_ROOT / ".github" / "workflows" / "hygiene.yml").read_text(
            encoding="utf-8"
        )
        for platform in ("ubuntu-latest", "windows-latest", "macos-latest"):
            self.assertIn(platform, workflow)
        self.assertIn('node-version: "24"', workflow)
        self.assertIn("python -B -m unittest discover -s tests -v", workflow)

    def test_release_requires_main_commit_and_three_platform_gates(self) -> None:
        hygiene = (REPO_ROOT / ".github" / "workflows" / "hygiene.yml").read_text(encoding="utf-8")
        release = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("workflow_call:", hygiene)
        self.assertIn("uses: ./.github/workflows/hygiene.yml", release)
        self.assertIn("needs: verify", release)
        self.assertIn("git merge-base --is-ancestor HEAD origin/main", release)

    def test_public_plugin_manifests_share_semver(self) -> None:
        claude = read_json(
            REPO_ROOT / "code-hygiene-compounder" / ".claude-plugin" / "plugin.json"
        )
        codex = read_json(
            REPO_ROOT
            / "plugins"
            / "code-hygiene-compounder"
            / ".codex-plugin"
            / "plugin.json"
        )

        self.assertRegex(claude["version"], SEMVER)
        self.assertEqual(claude["version"], codex["version"])
        self.assertEqual(claude["version"], validate_package.PLUGIN_VERSION)

    def test_readme_version_badge_matches_plugin_version(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        badge = re.search(
            r"img\.shields\.io/badge/version-(\d+\.\d+\.\d+)-[^)]+", readme
        )

        self.assertIsNotNone(badge)
        assert badge is not None
        self.assertEqual(validate_package.PLUGIN_VERSION, badge.group(1))

    def test_claude_validator_rejects_missing_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            repo_root = Path(temp_dir)
            marketplace_path = repo_root / ".claude-plugin" / "marketplace.json"
            manifest_path = (
                repo_root
                / "code-hygiene-compounder"
                / ".claude-plugin"
                / "plugin.json"
            )
            marketplace_path.parent.mkdir(parents=True)
            manifest_path.parent.mkdir(parents=True)
            marketplace_path.write_text(
                (REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text(
                    encoding="utf-8"
                ),
                encoding="utf-8",
            )
            manifest = read_json(
                REPO_ROOT
                / "code-hygiene-compounder"
                / ".claude-plugin"
                / "plugin.json"
            )
            manifest.pop("version", None)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            reporter = validate_package.Reporter()
            validate_package.check_claude_plugin_marketplace(repo_root, reporter)

            self.assertTrue(reporter.errors)
            self.assertIn("version", reporter.errors[0])


if __name__ == "__main__":
    unittest.main()
