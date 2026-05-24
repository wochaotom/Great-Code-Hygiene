# Hygiene Quick Entry

Use this file for ordinary code review, refactor, cleanup, hardening, and implementation work. Use the full skill references only when training, scoring, exporting, or source-grounded honing is requested.

## Quick Loop

1. **Ground:** inspect the relevant code, tests, types, manifests, docs, and local conventions before proposing or editing; for bounded scratch, fixture, export, or subdirectory tasks, scope status, diff, and discovery commands to that target.
2. **Loop:** for bugs, regressions, or flaky behavior, build the smallest deterministic feedback loop that reproduces the symptom before fixing; if no loop exists, state the attempted loops and the missing artifact or access.
3. **Constrain:** make the smallest behavior-correct change; avoid unrelated rewrites, formatting churn, dependency noise, optional scratch/cache cleanup, and user-change reverts. If cleanup is required, resolve and constrain recursive-delete targets first.
4. **Harden:** check correctness, tests, security/data safety, error handling, observability, compatibility, and local integration; for config precedence changes, include a winning-source test plus an absence/fallback control when the contract names multiple config sources.
5. **Verify:** run the narrowest meaningful checks first, broaden when shared contracts or risky behavior changed, and report unrun checks.
6. **Report:** include the evidence report from `evidence-report.md` before claiming completion or readiness.

For package validation, fixture generation, matrix generation, exports, or context indexing changes, report runtime before and after when scale can be affected. Do not require timing gates for ordinary small code fixes.

## High-Signal Anti-Patterns

- Hard-coded secrets or deploy-varying config.
- Missing validation at trust boundaries.
- Unsafe string-built SQL, shell commands, file paths, HTML, or code execution.
- Authorization based on caller-controlled identifiers.
- Swallowed errors, vague errors, or logs that hide the root cause.
- Sensitive data in logs, errors, telemetry, fixtures, or generated artifacts.
- Broad refactors attached to narrow fixes.
- Tests that only bless output without proving behavior.
- Dependency additions where existing tools suffice.
- Public API or config changes without compatibility and documentation review.
