# Development Guide

## Running Tests

The test suite verifies the skill, trainer scripts, promotion machinery, and
deterministic gates. Run tests with the `-B` flag to prevent Python from writing
bytecode caches during import, since security validation at module load time
depends on a clean bytecode state:

```bash
python -B -m unittest discover -s tests -v
```

Before running tests, clean any prior bytecode to avoid false positives from
security checks:

```bash
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
python -B -m unittest discover -s tests -v
```

## Pattern: Security Validation at Module Import

The `promote_candidate.py` script and related promotion tools reject untrusted
bytecode at module load time via `reject_verifier_bytecode()`. This prevents
an attacker from planting compiled `.pyc` files to bypass security checks.

**Critical Design Point**: Import-time environment validation that rejects
bytecode cannot tolerate leftover `.pyc` files from prior test runs or imports.
When adding similar security checks:

1. **Run the check at module load time** (not lazy) to fail fast
2. **Clean prior bytecode** before running tests that import the module
3. **Run test discovery with `-B`** to prevent bytecode creation during import
4. **Document the bytecode requirement** for anyone running the verifier module

This pattern is defensible only if both the validator and its test environment
prevent bytecode creation. Without both, the check either fails on leftover
cache or passes an unclean state.

## Editing the Skill

Edit `code-hygiene-compounder/SKILL.md` for changes to the trainer workflow and
sources. Generated copies (`code-hygiene/SKILL.md`, plugin manifests) are kept
in sync by the export machinery; do not hand-edit them.

Run regeneration and validation after editing the trainer:

```bash
python code-hygiene-compounder/scripts/export_claude_package.py \
  --skill-root code-hygiene-compounder --out-dir . --validate
python code-hygiene-compounder/scripts/validate_package.py --repo-root .
```
