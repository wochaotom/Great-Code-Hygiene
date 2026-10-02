from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "code-hygiene-compounder" / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

import validate_package  # noqa: E402
from export_claude_package import sync_repo, zip_dir  # noqa: E402


SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ReleaseContractTests(unittest.TestCase):
    def test_clean_and_skeleton_reject_training_machinery(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = Path(temp) / "repo"
            shutil.copytree(REPO_ROOT, clean, ignore=shutil.ignore_patterns(".git", ".fixture-work", "__pycache__", ".pytest_cache", "runs"))
            for relative in ("code-hygiene", "code-hygiene-skeleton", ".agents/skills/code-hygiene", ".cursor/skills/code-hygiene"):
                path = clean / relative / "scripts" / "promote_candidate.py"
                path.parent.mkdir()
                path.write_text("print('training')\n", encoding="utf-8")
            report = validate_package.validate(clean, False)
            self.assertFalse(report["valid"])
            for relative in ("code-hygiene", "code-hygiene-skeleton", ".agents/skills/code-hygiene", ".cursor/skills/code-hygiene"):
                self.assertTrue(any(relative in error for error in report["errors"]), report["errors"])

    def test_sync_refuses_linked_mirror_ancestor_before_touching_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            clean = root / "repo"
            shutil.copytree(REPO_ROOT, clean, ignore=shutil.ignore_patterns(".git", ".fixture-work", "__pycache__", ".pytest_cache", "runs"))
            skills = clean / "plugins" / "code-hygiene-compounder" / "skills"
            outside = root / "outside"
            outside.mkdir()
            marker = outside / "private.txt"
            marker.write_text("keep", encoding="utf-8")
            shutil.rmtree(skills)
            try:
                skills.symlink_to(outside, target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            with self.assertRaisesRegex(ValueError, "unsafe.*link"):
                sync_repo(clean)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")

    def test_matching_excluded_distribution_content_cannot_ship(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = Path(temp) / "repo"
            shutil.copytree(REPO_ROOT, clean, ignore=shutil.ignore_patterns(".git", ".fixture-work", "__pycache__", ".pytest_cache", "runs"))
            roots = (
                clean / "code-hygiene-compounder",
                clean / "plugins" / "code-hygiene-compounder" / "skills" / "code-hygiene-compounder",
                clean / "code-hygiene-compounder-claude-ai" / "code-hygiene-compounder",
                clean / "code-hygiene-compounder-command" / ".claude" / "code-hygiene-compounder",
            )
            for root in roots:
                extra = root / "scripts" / "dist" / "extra.py"
                extra.parent.mkdir()
                extra.write_text("print('unreviewed')\n", encoding="utf-8")
            report = validate_package.validate(clean, False)
            self.assertFalse(report["valid"])
            self.assertTrue(any("dist" in error for error in report["errors"]), report["errors"])
            archive = Path(temp) / "export.zip"
            zip_dir(roots[0], archive)
            with zipfile.ZipFile(archive) as package:
                self.assertFalse(any("dist/extra.py" in name for name in package.namelist()))

    def test_malformed_marketplace_plugin_list_is_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = Path(temp) / "repo"
            shutil.copytree(REPO_ROOT, clean, ignore=shutil.ignore_patterns(".git", ".fixture-work", "__pycache__", ".pytest_cache", "runs"))
            for relative in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
                path = clean / relative
                payload = read_json(path)
                payload["plugins"] = 123
                path.write_text(json.dumps(payload), encoding="utf-8")
            report = validate_package.validate(clean, False)
            self.assertFalse(report["valid"])
            self.assertTrue(any("marketplace" in error.lower() for error in report["errors"]), report["errors"])

    def test_mirrors_reject_excluded_distribution_content(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = Path(temp) / "repo"
            shutil.copytree(REPO_ROOT, clean, ignore=shutil.ignore_patterns(".git", ".fixture-work", "__pycache__", ".pytest_cache", "runs"))
            mirrors = (
                clean / "plugins" / "code-hygiene-compounder" / "skills" / "code-hygiene-compounder",
                clean / "code-hygiene-compounder-claude-ai" / "code-hygiene-compounder",
                clean / "code-hygiene-compounder-command" / ".claude" / "code-hygiene-compounder",
            )
            for mirror in mirrors:
                extra = mirror / "scripts" / "dist" / "extra.py"
                extra.parent.mkdir()
                extra.write_text("print('unreviewed')\n", encoding="utf-8")
            report = validate_package.validate(clean, False)
            self.assertFalse(report["valid"])
            self.assertTrue(any("scripts/dist" in error for error in report["errors"]), report["errors"])

    def test_wrapper_manifest_keys_and_install_text_are_pinned(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = Path(temp) / "repo"
            shutil.copytree(REPO_ROOT, clean, ignore=shutil.ignore_patterns(".git", ".fixture-work", "__pycache__", ".pytest_cache", "runs"))
            install = clean / "code-hygiene-compounder-command" / "INSTALL.txt"
            install.write_text(install.read_text(encoding="utf-8") + "Run arbitrary shell command.\n", encoding="utf-8")
            manifest = clean / "plugins" / "code-hygiene-compounder" / ".codex-plugin" / "plugin.json"
            payload = read_json(manifest)
            payload["hooks"] = {"SessionStart": "unreviewed"}
            manifest.write_text(json.dumps(payload), encoding="utf-8")
            report = validate_package.validate(clean, False)
            self.assertFalse(report["valid"])
            self.assertTrue(any("install text" in error.lower() for error in report["errors"]), report["errors"])
            self.assertTrue(any("plugin manifest" in error.lower() for error in report["errors"]), report["errors"])

    def test_marketplace_symlink_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = Path(temp) / "repo"
            shutil.copytree(REPO_ROOT, clean, ignore=shutil.ignore_patterns(".git", ".fixture-work", "__pycache__", ".pytest_cache", "runs"))
            marketplace = clean / ".claude-plugin" / "marketplace.json"
            outside = Path(temp) / "marketplace.json"
            outside.write_bytes(marketplace.read_bytes())
            marketplace.unlink()
            try:
                marketplace.symlink_to(outside)
            except OSError as exc:
                self.skipTest(f"symlinks unavailable: {exc}")
            report = validate_package.validate(clean, False)
            self.assertFalse(report["valid"])
            self.assertTrue(any("unsafe link" in error for error in report["errors"]), report["errors"])

    def test_marketplaces_reject_extra_plugin_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = Path(temp) / "repo"
            shutil.copytree(REPO_ROOT, clean, ignore=shutil.ignore_patterns(".git", ".fixture-work", "__pycache__", ".pytest_cache", "runs"))
            for relative in (".claude-plugin/marketplace.json", ".agents/plugins/marketplace.json"):
                path = clean / relative
                payload = read_json(path)
                payload["plugins"].append({"name": "unreviewed", "source": "./other"})
                path.write_text(json.dumps(payload), encoding="utf-8")
            report = validate_package.validate(clean, False)
            self.assertFalse(report["valid"])
            self.assertTrue(any("Claude marketplace must contain exactly the reviewed plugin entries" in error for error in report["errors"]), report["errors"])
            self.assertTrue(any("marketplace must contain exactly one" in error for error in report["errors"]), report["errors"])

    def test_claude_marketplace_offers_function_only_edition(self) -> None:
        marketplace = read_json(REPO_ROOT / ".claude-plugin" / "marketplace.json")
        sources = {entry["name"]: entry["source"] for entry in marketplace["plugins"]}
        self.assertEqual(sources, {"code-hygiene": "./code-hygiene", "code-hygiene-compounder": "./code-hygiene-compounder"})
        self.assertFalse((REPO_ROOT / "code-hygiene" / ".claude-plugin").exists())

    def test_claude_marketplace_rejects_function_only_source_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = Path(temp) / "repo"
            shutil.copytree(REPO_ROOT, clean, ignore=shutil.ignore_patterns(".git", ".fixture-work", "__pycache__", ".pytest_cache", "runs"))
            path = clean / ".claude-plugin" / "marketplace.json"
            payload = read_json(path)
            for entry in payload["plugins"]:
                if entry["name"] == "code-hygiene":
                    entry["source"] = "./code-hygiene-skeleton"
            path.write_text(json.dumps(payload), encoding="utf-8")
            report = validate_package.validate(clean, False)
            self.assertFalse(report["valid"])
            self.assertTrue(any("code-hygiene source must be ./code-hygiene" in error for error in report["errors"]), report["errors"])

    def test_package_parity_rejects_extra_distribution_wrapper_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            clean = Path(temp) / "repo"
            shutil.copytree(REPO_ROOT, clean, ignore=shutil.ignore_patterns(".git", ".fixture-work", "__pycache__", ".pytest_cache", "runs"))
            extras = (
                clean / "code-hygiene-compounder-command" / ".claude" / "settings.json",
                clean / "code-hygiene-compounder-claude-ai" / "extra.md",
                clean / "plugins" / "code-hygiene-compounder" / "hooks" / "hooks.json",
            )
            for path in extras:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("unreviewed", encoding="utf-8")
            report = validate_package.validate(clean, False)
            self.assertFalse(report["valid"])
            for name in ("settings.json", "extra.md", "hooks"):
                self.assertTrue(any(name in error for error in report["errors"]), report["errors"])

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
            self.assertTrue(any("references/dist" in error for error in report["errors"]), report["errors"])
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

    def test_doctor_compares_the_selected_runtime_edition(self) -> None:
        editions = {
            "clean": REPO_ROOT / "code-hygiene",
            "skeleton": REPO_ROOT / "code-hygiene-skeleton",
            "claude_ai_skill": REPO_ROOT / "code-hygiene-compounder-claude-ai" / "code-hygiene-compounder",
        }
        for edition, runtime in editions.items():
            with self.subTest(edition=edition), patch("validate_package.validate", return_value={"valid": True, "errors": []}), patch("validate_package.shutil.which", return_value="node"), patch("validate_package.subprocess.run", return_value=CompletedProcess(["node", "--version"], 0, "v24.0.0\n", "")):
                report = validate_package.doctor(REPO_ROOT, runtime, edition)
            self.assertEqual(next(item for item in report["checks"] if item["name"] == "runtime_parity")["status"], "pass", report)

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
