# Code Hygiene Compounder

Use the bundled code hygiene workflow to improve, review, refactor, harden, test, or evaluate code. Treat `.claude/code-hygiene-compounder` as the local reference package.

First read repo instructions:
1. Read `CLAUDE.md`, `AGENTS.md`, and nearby package/module instructions when present.
2. Repo instructions and explicit user requests override this command.
3. Preserve user edits and local conventions.

Default to audit mode:
1. For review/audit requests, do not edit files.
2. For implementation requests, inspect first and state the smallest viable change before editing.
3. If the request is ambiguous, propose the edit and wait for approval before changing files.

Follow this hygiene loop:
1. For ordinary code work, read `.claude/code-hygiene-compounder/references/HYGIENE_QUICK.md`.
2. Ground in relevant code, tests, types, manifests, docs, and existing patterns; for bounded scratch, fixture, export, or subdirectory tasks, scope status, diff, and discovery commands to that target.
3. For bugs, regressions, or flaky behavior, build the smallest deterministic feedback loop that reproduces the symptom before fixing, or state what blocked that loop.
4. Make the smallest behavior-correct change; avoid unrelated rewrites, formatting churn, and dependency changes.
5. Check tests, security, error paths, observability, dependencies, and local conventions.
6. Verify with meaningful commands and include the evidence report from `.claude/code-hygiene-compounder/references/evidence-report.md` before claiming completion.
7. Do not trust agent reports, generated summaries, or intermediate files as proof; inspect the final user-facing artifact and verification output.
8. Score significant work with PASS-100 when requested or when compounding a lesson.
9. For broad training or scoring work, use `.claude/code-hygiene-compounder/references/context-index.json` as a router for smaller reference reads, not as a replacement for required source packs.
10. Use source-grounded honing only when requested; then read every activated source pack and validate the honing report before promotion.
11. Capture durable lessons and only promote instruction updates through the compound loop.

Read these files when needed:
- `.claude/code-hygiene-compounder/references/HYGIENE_QUICK.md`
- `.claude/code-hygiene-compounder/references/context-index.json`
- `.claude/code-hygiene-compounder/references/evidence-report.md`
- `.claude/code-hygiene-compounder/references/PASS-100.md`
- `.claude/code-hygiene-compounder/references/eval-prompts.md`
- `.claude/code-hygiene-compounder/references/compound-loop.md`
- `.claude/code-hygiene-compounder/references/research-canon.md`
- `.claude/code-hygiene-compounder/references/source-grounded-honing.md`
- `.claude/code-hygiene-compounder/references/training-lessons.md`
