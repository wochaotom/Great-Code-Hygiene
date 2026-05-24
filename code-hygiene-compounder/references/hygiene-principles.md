# Hygiene Principles

These are the distilled training targets from the source registry. Compound the skill against these principles rather than copying long source text into `SKILL.md`.

## Universal Principles

1. **Preserve or improve code health.** A change should not decrease maintainability, clarity, security, or testability while solving the immediate problem.
2. **Make behavior correct and user-appropriate.** Check intended behavior, edge cases, concurrency, compatibility, and user/developer impact.
3. **Keep changes small and reviewable.** Avoid unrelated rewrites, broad formatting churn, accidental generated-file changes, and dependency noise.
4. **Prefer simplicity over speculative flexibility.** Do not add abstractions for needs that are not present.
5. **Match the local system.** Use existing architecture, helpers, naming, error patterns, framework conventions, and test style unless they are the problem.
6. **Use deterministic loops as fast feedback.** For bugs, regressions, or flaky behavior, reproduce the symptom with the smallest reliable test, harness, UI automation, fixture, or trace before fixing when feasible; add integration/end-to-end coverage only where it proves real integration risk.
7. **Treat security as design, not cleanup.** Validate inputs, encode outputs, enforce auth/authz, protect secrets, handle crypto carefully, and prevent common CWE classes.
8. **Handle failure deliberately.** Include bounded retries, timeouts, checked return values, useful errors, and safe logging where relevant.
9. **Protect data.** Avoid leaking secrets/PII in logs, APIs, exceptions, telemetry, test fixtures, or generated artifacts.
10. **Keep deploy-varying config out of code.** Hard-coded secrets, hostnames, credentials, ports, regions, and environment-specific handles are hygiene failures.
11. **Make public interfaces evolvable.** Consider versioning, compatibility, migration, docs, deprecation, and rollback.
12. **Make builds and releases traceable.** When packaging or releasing, prefer reproducible scripted builds, provenance, signed artifacts, and supply-chain checks.
13. **Make web UI accessible.** For frontend work, consider keyboard access, focus, labels, contrast, target size, error messages, and robust semantics.
14. **Instrument what operators need.** Logs, metrics, and traces should help debug real failures without exposing sensitive data.
15. **State residual risk honestly.** Report checks run, checks not run, assumptions, and remaining risks.

## Source-Weighted Application

- Always apply Google Engineering Practices and basic test-feedback principles.
- Keep security and data-protection principles in mind on every task, but activate NIST SSDF, OWASP Secure Coding, CWE Top 25, and related security source packs for security-sensitive changes, trust-boundary work, public APIs, deploy/release risk, or explicit security reviews.
- Apply ASVS, OWASP Cheat Sheets, WCAG, REST API guidelines, OpenTelemetry, SLSA, Scorecard, SemVer, Twelve-Factor, Python source packs, and language-specific standards when the task touches their domain.
- Apply HTTP semantics guidance when code parses, forwards, combines, or adapts protocol fields; preserve documented field cardinality, ordering, and list/non-list value semantics.
- Apply NASA/JPL Power of Ten only for safety-critical, embedded, firmware, hard real-time, or similarly high-reliability code unless the repo already follows those constraints.
- Apply agent-evaluation methodology when training, scoring, or reviewing agent traces; judge goal fulfillment, plan quality, plan adherence, tool-call validity, logical consistency, execution efficiency, and failure localization rather than final output alone.

## Python Conditional Principles

- For Python code, prefer explicit error boundaries, context managers, structured path handling, safe subprocess calls, and small import-time side effects.
- Let local style lead; use PEP 8 and PEP 257 as fallback standards for naming, layout, and useful public docstrings.
- For pytest work, keep tests behavior-focused, isolated, and import-realistic.
- For Python packaging work, keep `pyproject.toml`, build metadata, dependencies, extras, entry points, and lock/tool files coherent with the repo's packaging model.

## Developer Documentation Conditional Principles

- For README, API, setup, troubleshooting, deprecation, and usage docs, optimize the reader's next task: make the purpose, prerequisites, sequence, examples, and expected results easy to scan.
- Keep documentation tied to real behavior. Update or remove docs when behavior, setup, public APIs, flags, or examples change; avoid unrelated wording churn.
- Prefer descriptive headings, link text, code formatting, and sequential lists that help global developer readers follow procedures without guessing.
- Keep examples minimal, current, runnable where feasible, and consistent with the local project; do not let docs examples drift from tested behavior.

## LLM Tool Schema Conditional Principles

- For provider-facing tool calls, structured outputs, AI SDK adapters, and MCP bridges, keep the canonical local schema separate from provider-specific normalized schemas.
- Verify provider schema adapters with local canaries for accepted and rejected schema shapes before relying on remote API behavior or issue-body error strings.
- Record the provider, model/API mode, schema version or hash, and unsupported-field diagnostics without leaking prompts, secrets, or user data.

## Anti-Patterns To Penalize

- Hard-coded deploy-varying config or secrets.
- Magic numbers without domain names.
- Duplicated business/security logic.
- Swallowed errors or logs that hide the root cause.
- Missing validation on trust boundaries.
- Unsafe string-built SQL, shell, file paths, HTML, or code execution.
- Authorization checks based on caller-controlled identifiers.
- Overly broad refactors attached to narrow bug fixes.
- Test changes that only bless current output without checking behavior.
- Snapshot-only coverage for important UI behavior.
- Dependency additions where existing tools suffice.
- Public API changes without compatibility handling.
- Documentation examples, setup steps, or deprecation notes that contradict the current code.
- Provider tool or structured-output schemas mutated globally to satisfy one LLM provider instead of using an explicit boundary adapter.
- Comments that repeat obvious code or contradict behavior.
- Telemetry that cannot be correlated or that leaks sensitive data.
- Skill updates based on style preference rather than evidence.

## Training Implications

- Eval fixtures should map each failure to one or more principles and source families.
- Agent evals should inspect the trace when available: did the response satisfy the goal, did the plan fit the goal, did actions follow the plan, were tool calls valid, and where did any failure originate?
- Promotion decisions should compare category scores and principle coverage, not only total score.
- A candidate skill update should name the source-backed principle it strengthens.
- Later source additions should be rare and quarantined until classified, weighted, and converted into principles.
