---
name: code-hygiene-compounder
description: Trainer edition of the code hygiene workflow that scores agent code work with PASS-100, hones it against authoritative sources, and compounds lessons from coding or review misses into the skill. Use when running PASS-100 or fixture evaluations, scoring or improving code hygiene behavior, auditing sources, promoting lessons, or exporting the skill packages. Also handles ordinary review, refactor, cleanup, hardening, and test work when the function-only code-hygiene skill is not installed.
---

# Code Hygiene Compounder

## Quick Start

Use this skill to make code changes safer, smaller, more testable, and easier to review. When the function-only `code-hygiene` skill is also installed, prefer it for ordinary code work and use this skill for training, scoring, and export.

For ordinary coding or review work:
1. Read `references/HYGIENE_QUICK.md`.
2. Inspect the existing system before changing behavior.
3. For bugs, regressions, or flaky behavior, build the smallest deterministic feedback loop before fixing, or state why no loop is possible.
4. State the smallest viable change and the verification plan.
5. Preserve user edits and local conventions.
6. Prefer focused fixes over broad rewrites.
7. Verify with the narrowest meaningful checks, then broaden when risk warrants.
8. Use the report shape in `references/evidence-report.md` before claiming completion or readiness.
9. Capture any durable lesson if the work exposed a repeatable hygiene miss.

For training or evaluation:
1. Read `references/PASS-100.md`.
2. For broad or ambiguous training work, read `references/context-index.json` to choose the smallest needed reference files; treat it as a router, not a replacement for the references it points to.
3. Read `references/source-registry.md`, `references/hygiene-principles.md`, and `references/source-weights.json` when source-backed reasoning matters.
4. For source-grounded honing, read `references/source-grounded-honing.md` and generate an audit plan with `scripts/source_audit_plan.py`.
5. Read every activated source pack under `references/source-packs/` before scoring or promoting; the context index does not satisfy this requirement.
6. Select prompts from `references/eval-prompts.md`.
7. Run `scripts/pass100_runner.py` to create batches, score result files, and update phase logs.
8. Validate source-grounded reports with `scripts/validate_honing_report.py`.
9. Apply the compounding rules in `references/compound-loop.md`.
10. Check `references/overtraining-guardrails.md` before adding rules, fixtures, or sources.
11. Check `references/training-lessons.md` for compact lessons already promoted from target-dummy runs.
12. Promote a candidate skill update only when score, evidence, and guardrail gates pass.

## Hygiene Workflow

Follow this loop on every code task. For multi-step work, copy this checklist into your reply and tick it off:

```
Hygiene progress:
- [ ] Ground: relevant code, tests, and conventions read
- [ ] Feedback loop: symptom reproduced, or blocker named
- [ ] Constrain: smallest change made
- [ ] Harden: edge cases, security, and tests checked
- [ ] Verify: targeted checks pass (on failure, return to Constrain)
- [ ] Report: evidence report written
- [ ] Compound: candidate lesson recorded, if any
```

1. **Ground**
   - Read relevant files, tests, types, manifests, and local patterns first.
   - Identify owned versus user-modified changes before editing.
   - For explicitly bounded scratch, fixture, export, or subdirectory tasks, scope status, diff, and discovery commands to that target instead of parent repo state.
   - Prefer existing helpers, conventions, and frameworks.

2. **Feedback Loop**
   - For bugs, regressions, or flaky behavior, build the smallest deterministic loop that reproduces the symptom before fixing.
   - Prefer a focused test, CLI/script harness, UI automation, replayed fixture, or captured trace over manual inspection.
   - If no loop is possible, state what was tried and what artifact, access, or environment is missing.

3. **Constrain**
   - Make the smallest change that satisfies the request.
   - Avoid opportunistic rewrites, formatting churn, dependency changes, and unrelated cleanup.
   - Leave generated scratch/cache artifacts alone unless cleanup is required; before recursive deletion, resolve and constrain the target path.
   - Add abstractions only when they remove real complexity or match a local pattern.

4. **Harden**
   - Check behavior preservation, input validation, error handling, logging, security-sensitive paths, migrations, concurrency, and compatibility.
   - For config, default, or precedence fixes, test the intended winning source plus at least one absence/fallback control when the contract distinguishes defaults, files, environment, or overrides.
   - Add tests when behavior changes, the bug can regress, or shared contracts move.
   - Keep comments sparse and useful.

5. **Verify**
   - Run targeted tests first.
   - Run broader checks for shared modules, public APIs, security-sensitive changes, or migrations.
   - If a check fails, return to Constrain, fix the cause, and re-run the same check. Do not move to Report on a failing check unless you name it as a blocker.
   - Report unrun checks and remaining risk plainly.

6. **Report**
   - Use `references/evidence-report.md` for verification, correctness, security/data, minimal diff, unrun checks, and residual risk.
   - Do not claim completion, readiness, or passing status without fresh verification evidence.

7. **Compound**
   - Record repeatable failures or misses as candidate lessons.
   - Keep lessons concrete: trigger, observed failure, improved behavior, verification.
   - Tie each durable lesson to a source-backed principle or a concrete eval failure.
   - Update the skill only through the PASS-100 promotion gates.

## Source Corpus Workflow

Use Phase R before expanding evals or making broad skill changes:

1. Treat `references/source-registry.md` as the locked authoritative corpus.
2. Use `references/hygiene-principles.md` as the operational target for everyday coding and scoring.
3. Use `references/source-weights.json` to activate conditional sources only when the task domain matches.
4. Quarantine new sources until they are classified, distilled, weighted, and shown to add measurable coverage.
5. Do not paste long source text into `SKILL.md`; keep the skill body procedural and concise.

Use Phase R2 for source-grounded honing:

1. Determine relevant task domains, such as `security`, `api`, `frontend`, `config`, `build`, `observability`, `package`, `safety-critical`, or `training`.
2. Generate an audit plan, for example:

```powershell
python scripts/source_audit_plan.py --skill-root . --domain security --domain api --out runs/source-audit-plan.json
```

3. Read every source pack listed in the generated plan.
4. Score the work against PASS-100 and record source IDs, principles checked, evidence, and missed checks.
5. Continue honing until the current phase threshold is reached or failures stop producing useful lessons.

## PASS-100 Modes

- **Smoke:** 10 prompts for quick sanity checks.
- **Focused:** 25-50 prompts from categories touched by a failure or change.
- **Regression:** 75-100 prompts weighted toward recent failures.
- **Phase promotion:** all prompts in the current phase.
- **Statistical promotion:** target 384+ prompts when a phase needs stronger confidence.

PASS-100 is the 100-point scorecard, not a fixed test count. Phase 0 starts with 100 prototype prompts. Later phases may expand to 150-250, 384+, or more only when gaps justify it.

## Automation Commands

The scripts need Python 3.11 or newer and use only the standard library, so there is nothing to install. Run them from this skill's directory, since command paths are relative to it, and use `python3` where `python` is not on PATH. Execute the scripts rather than reading them; `references/automation-commands.md` lists every command, the gate rules, and what each script proves.

Promotion is low freedom: run `scripts/promote_candidate.py` exactly as documented there, and add `--apply` only after every gate passes.

## References

- `references/research-canon.md`: distilled research basis and source links.
- `references/automation-commands.md`: every script command, gate rules, and what each script proves.
- `references/context-index.json`: machine-readable router for selecting smaller reference reads.
- `references/HYGIENE_QUICK.md`: short daily checklist for ordinary code work.
- `references/evidence-report.md`: required lightweight report shape for code changes and reviews.
- `references/source-registry.md`: Phase R authoritative source corpus.
- `references/hygiene-principles.md`: distilled principles to train and score against.
- `references/source-weights.json`: source weights and activation rules.
- `references/principle-traceability.md`: audit map from principles to sources and PASS-100 categories.
- `references/source-grounded-honing.md`: protocol for honing against individual source packs.
- `references/overtraining-guardrails.md`: budgets and promotion questions to prevent self-eval overfit.
- `references/training-lessons.md`: compact promoted lessons from scored training targets.
- `references/source-packs/`: per-source distilled checklists with official links.
- `references/PASS-100.md`: scoring rubric and category weights.
- `references/eval-prompts.md`: Phase 0 100-prompt prototype eval bank.
- `references/compound-loop.md`: full-auto improvement protocol and phase rules.
