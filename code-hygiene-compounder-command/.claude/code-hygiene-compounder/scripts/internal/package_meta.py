"""Canonical package identities and export exclusions."""

from pathlib import Path


PLUGIN_VERSION = "0.3.0"
SKILL_NAME = "code-hygiene-compounder"
PACKAGE_DIRS = {
    "codex_skill": Path("code-hygiene-compounder"),
    "codex_plugin_skill": Path("plugins/code-hygiene-compounder/skills/code-hygiene-compounder"),
    "claude_ai_skill": Path("code-hygiene-compounder-claude-ai/code-hygiene-compounder"),
    "claude_command_package": Path("code-hygiene-compounder-command/.claude/code-hygiene-compounder"),
}
FUNCTION_ONLY_DIR = Path("code-hygiene")
SKELETON_DIR = Path("code-hygiene-skeleton")
EXCLUDED_NAMES = frozenset({
    "runs", "__pycache__", ".pytest_cache", ".mypy_cache", ".fixture-tmp", ".fixture-work", ".git", "dist",
})
