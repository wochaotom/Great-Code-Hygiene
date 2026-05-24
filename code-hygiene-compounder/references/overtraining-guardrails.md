# Overtraining Guardrails

Use these checks to keep the skill useful for ordinary coding rather than optimized only for its own evals.

## Budgets

- Keep `SKILL.md` procedural and under the guardrail checker's line and byte budgets.
- Keep promoted lessons in `references/training-lessons.md`; distill or merge old lessons before expanding the file.
- Keep executable fixtures sparse. A fixture should represent a repeated, measurable failure mode, not every prompt.
- Keep source packs locked and weighted. New sources need a measurable coverage reason.
- The current fixture and source-pack budgets are saturated. Adding either requires merging/removing an existing item or an explicit budget change backed by promotion evidence.
- Keep scripts deterministic and dependency-free unless a hard statistic cannot be produced otherwise.

## Promotion Questions

Before promoting a candidate lesson or fixture, answer:

1. What hard signal improves: score delta, fixture `resolved`, confidence interval, real-task failure reduction, or reviewer finding?
2. What existing lesson or rule can be removed, merged, or narrowed?
3. Does this improve normal code tasks, or only the current eval shape?
4. Is the evidence `model-execution`, `audit-backed`, or only `script-only`?
5. Does the change keep the active skill shorter than the references it points to?

Single scratch misses are candidate evidence, not promotion evidence. Promote only after recurrence on an independent target, a model-execution rerun showing improvement, or an audit-backed result on a real task.

Generated matrix variants can reveal coverage gaps, but they cannot justify new active lessons by themselves. Treat generated train and holdout results as candidate evidence until an independent model-execution failure or source-grounded audit supports the same lesson.

## Failure Signs

- PASS-100 averages rise while real tasks become slower, more verbose, or more timid.
- Fixtures grow faster than uncovered failure categories.
- Lessons repeat the same rule with new task names.
- The active skill starts carrying source text, long examples, or benchmark-specific tricks.
- Promotion gates reward artifacts without checking the user-facing result.

Run `scripts/guardrail_check.py` before promotion and after package sync.
