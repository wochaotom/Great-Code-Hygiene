# Evidence Report

Use this report shape for code changes, reviews, refactors, hardening, and hygiene audits. It is the lightweight enforcement hook for the skill: missing sections make skipped checks visible.

## Required Shape

```markdown
**Hygiene Evidence**
- Feedback Loop: <smallest repro loop used before fixing, or why no deterministic loop was possible>
- Verification: <commands/checks run, exact result, or "not run">
- Evidence Table:
  | Check | Expected | Actual | Status | Artifact |
  | --- | --- | --- | --- | --- |
  | <gate or behavior checked> | <expected value> | <actual value> | <pass/fail> | <file/command/output> |
- Correctness: <main behavior preserved/changed, edge cases considered>
- Security/Data: <validation, secrets, auth/authz, injection/path/data leak considerations>
- Minimal Diff: <why the change is scoped and what unrelated churn was avoided>
- Unrun Checks: <checks not run and why>
- Residual Risk: <remaining uncertainty or "none identified">
```

## Rules

- Do not claim work is complete, fixed, passing, ready, correct, or safe unless the `Verification` line has fresh evidence.
- For bugs, regressions, or flaky behavior, do not skip `Feedback Loop`; record the focused test, CLI/script harness, UI automation, replayed fixture, captured trace, or the missing artifact/access/environment that blocked a deterministic loop.
- For failed checks, include the exact expected value, actual value, and artifact path when available.
- If no tools are available, write the exact command or inspection still needed under `Verification` and `Unrun Checks`.
- For review-only tasks, use the same shape after findings to state what was and was not verified.
- For high-risk changes, include targeted details under `Correctness` and `Security/Data` instead of generic "looks good" language.
- For changes to package validation, fixture generation, matrix generation, exports, or context indexing, report runtime before and after when the change can affect scale. Do not require performance gates for ordinary small code fixes.

## Timing Example

```powershell
Measure-Command { python code-hygiene-compounder/scripts/validate_package.py --repo-root . }
```
