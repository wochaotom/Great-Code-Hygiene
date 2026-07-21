from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = REPO_ROOT / "code-hygiene-compounder" / "scripts"
sys.path.insert(0, str(SCRIPTS_ROOT))

import validate_package  # noqa: E402


SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ReleaseContractTests(unittest.TestCase):
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
