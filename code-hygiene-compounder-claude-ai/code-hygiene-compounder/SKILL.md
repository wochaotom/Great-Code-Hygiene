---
name: code-hygiene-compounder
description: Improve, review, refactor, harden, test, and evaluate code hygiene with PASS-100 scoring and source-grounded compounding.
---

# Code Hygiene Compounder

## Quick Start

Use this skill to make code changes safer, smaller, more testable, and easier to review. Treat the Codex skill as the source of truth; export Claude Code packages from the current Codex skill state when needed.

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

Follow this loop on every code task:

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

Use the bundled scripts with the active Python runtime:

```powershell
python scripts/pass100_runner.py list --suite references/eval-prompts.md
python scripts/pass100_runner.py batch --suite references/eval-prompts.md --mode smoke --out runs/smoke.json
python scripts/validate_results.py --results runs/results.json --suite references/eval-prompts.md
python scripts/pass100_runner.py score --results runs/results.json --out runs/score.json
python scripts/analyze_runs.py --results runs/results.json --baseline runs/baseline-results.json --suite references/eval-prompts.md --out runs/analysis.json
python scripts/guardrail_check.py --skill-root .
python scripts/fixture_runner.py --fixtures fixtures list
python scripts/fixture_runner.py --fixtures fixtures baseline
python scripts/fixture_runner.py --fixtures fixtures prepare --fixture hyg-001-null-helper --target runs/fixtures/hyg-001-null-helper
python scripts/fixture_runner.py --fixtures fixtures run --fixture hyg-001-null-helper --target runs/fixtures/hyg-001-null-helper
python scripts/matrix_runner.py run --split all --loops 50 --variants-per-family 20 --work-root runs/matrix --out runs/matrix-50x.json
python scripts/matrix_runner.py review --work-root runs/matrix-review --out runs/matrix-review.json
python scripts/promote_candidate.py --current . --candidate path/to/candidate --score runs/score.json
python scripts/export_claude_package.py --skill-root . --out-dir path/to/export
python scripts/export_claude_package.py --skill-root . --out-dir path/to/export --format claude-ai-skill --zip-name code-hygiene-compounder-claude-ai.zip
python scripts/export_claude_package.py --skill-root . --out-dir path/to/export --format legacy-command --zip-name code-hygiene-compounder-command.zip
```

The scripts are deterministic gatekeepers. `validate_results.py` rejects malformed PASS-100 evidence before it enters the loop. `analyze_runs.py` computes comparable averages, confidence intervals, pass rates, and baseline deltas. `guardrail_check.py` keeps active instructions, lessons, sources, fixtures, and scripts inside anti-overtraining budgets. `fixture_runner.py` provides a small objective path for executable fixtures. `matrix_runner.py` generates larger scratch target matrices for target-quality validation, with train/holdout/all split selection and review-style visible/hidden contract checks; do not treat oracle-green matrix stats as model-execution proof. The agent still performs code review, eval execution, candidate lesson extraction, and skill editing unless the surrounding environment provides a model runner.

## References

- `references/research-canon.md`: distilled research basis and source links.
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
