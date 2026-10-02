---
name: code-hygiene
description: Function-only code hygiene workflow for code review, cleanup, hardening, bug fixing, refactoring, package checks, and verification evidence. Use when reviewing a PR, diff, branch, or module before merge; fixing a bug, failing test, regression, or flaky test; refactoring or cleaning up code without changing behavior; hardening input handling, auth, paths, or config; or checking that a change actually works. Example requests include review this before I ship it; the tests are failing, fix them; clean this up; is this safe to expose. Does not run PASS-100 training, source-grounded honing, self-mutation, promotion loops, or skill evolution.
metadata:
  tested-with: "Claude Haiku, Sonnet, and Opus"
---

# Code Hygiene

## Hygiene Workflow

Follow this loop on every code task. For multi-step work, copy this checklist
into your reply and tick it off:

```
Hygiene progress:
- [ ] Ground: relevant code, tests, and conventions read
- [ ] Feedback loop: symptom reproduced, or blocker named
- [ ] Constrain: smallest change made
- [ ] Harden: edge cases, security, and tests checked
- [ ] Verify: targeted checks pass (on failure, return to Constrain)
- [ ] Report: evidence report written
```

### 1. Ground

- Read the relevant code, tests, docs, manifests, types, generated boundaries,
  and local helper APIs before changing behavior.
- Check repo instructions and conventions before inventing a new style.
- Identify owned changes versus unrelated user edits. Never revert unrelated
  user work.
- For explicitly bounded scratch, fixture, export, or subdirectory tasks, scope
  status, diff, and discovery commands to that target instead of letting parent
  repo state steer the work.
- Prefer existing helpers, frameworks, parsers, APIs, and architecture seams.
- If the task is underspecified, exhaust discoverable repo facts before asking
  for product intent.

### 2. Feedback Loop

- For bugs, regressions, or flaky behavior, build the smallest deterministic
  feedback loop before fixing, or state why no loop is possible.
- Prefer a focused test, CLI/script harness, UI automation, replayed fixture,
  captured trace, reduced example, or exact failing command over inspection.
- If no loop is possible, state what was tried and what artifact, access, or
  environment is missing.
- Keep the first loop narrow. Broaden only after the narrow loop explains the
  failure or when the risk surface is larger than the initial symptom.
- Do not patch symptoms from inspection alone when a deterministic loop is
  feasible.
- Patch only after the loop is understood or after a concrete blocker is named.

### 3. Constrain

- Make the smallest behavior-correct change that satisfies the request.
- State the smallest viable change and the verification plan.
- Avoid opportunistic rewrites, formatting sweeps, dependency churn, broad
  search-and-replace, generated noise, and unrelated cleanup.
- Add an abstraction only when it removes real complexity, reduces meaningful
  duplication, or matches an established local pattern.
- Preserve public contracts, API shape, migrations, data formats, config
  precedence, and caller-owned mutable values unless the task explicitly changes
  them.
- Leave generated scratch/cache artifacts alone unless cleanup is required.
  Before recursive deletion or moves, resolve the target path and prove it stays
  inside the intended directory.
- Prefer characterization tests or golden traces when behavior is unclear.
- Remove dead code and stale docs only when the local evidence supports removal.
- Respect lockfiles, manifests, generated files, and documented defaults.

### 4. Harden

- Check behavior preservation, edge cases, input validation, authorization,
  secrets, path handling, injection risk, unsafe deserialization, privacy, and
  dependency risk when relevant.
- Check error handling, logging, retries, timeouts, observability, resource
  cleanup, concurrency, migration rollback, and compatibility when relevant.
- For config/default/precedence changes, test the intended winning source plus
  at least one absence or fallback control when the contract distinguishes
  defaults, files, environment variables, or overrides.
- Add or update tests when behavior changes, a bug can regress, a public
  contract moves, or the existing tests are placeholders.
- Keep comments sparse and useful. Explain tricky business rules or non-obvious
  constraints; do not narrate obvious code.
- Prefer framework-supported safe APIs over custom parsing or hand-rolled
  security controls.
- Add regression checks for the vulnerable path and at least one safe control
  when feasible.
- Avoid replacing one silent failure with another. Error paths need observable,
  useful behavior.

### 5. Verify

- Run targeted checks first: the focused test, script, fixture, CLI command, UI
  flow, or replay that proves the changed behavior.
- Run broader checks for shared modules, public APIs, security-sensitive paths,
  config, packaging, migrations, generated schemas, or dependency changes.
- Verify adjacent consumer commands when package or config changes can affect
  install, build, runtime, or export behavior.
- If a check fails, return to Constrain, fix the cause, and re-run the same
  check. Do not move to Report on a failing check unless you name it as a
  blocker.
- Treat failing or unavailable checks as evidence, not as noise. Report them
  plainly.
- Do not claim complete, passing, fixed, safe, or ready without fresh tool
  output or a clearly stated blocker.

### 6. Report

For reviews, lead with findings ordered by severity. Include file/line evidence
when available, and distinguish confirmed bugs from plausible risks. Each finding
should name the behavior risk, affected path, evidence, and a practical fix
direction. Do not report theoretical issues as confirmed without a code path or
behavior path.

For implementation work, report:

- Feedback Loop: the reproduction or verification loop used, or why none was
  possible.
- Change: what changed and why it stayed scoped.
- Verification: exact commands/checks run and their results.
- Correctness: behavior preserved or intentionally changed.
- Security/Data: validation, secrets, auth/authz, injection, path, privacy, and
  dependency considerations when relevant.
- Minimal Diff: unrelated churn avoided and user edits preserved.
- Unrun Checks: checks not run and why.
- Residual Risk: remaining uncertainty.

Report evidence, skipped checks, assumptions, and residual risk.

## Tool And Access Limits

- If filesystem, shell, git, browser, network, or test access is unavailable,
  state the limitation and use the best available evidence.
- Do not invent command output, file contents, test results, links, versions, or
  line numbers.
- If a check is high-value but blocked by credentials, services, OS support, or
  missing dependencies, name the exact blocker and the artifact needed.

## Hard Stops

- Do not run training, PASS-100 promotion, source-grounded honing, fixture
  admission, source-pack admission, or skill self-mutation.
- If the user explicitly asks for training, scoring, source-grounded honing,
  package export, or skill evolution, use `code-hygiene-compounder` instead.
- Do not edit this skill or package artifacts unless the user explicitly asks to
  maintain the skill package.
