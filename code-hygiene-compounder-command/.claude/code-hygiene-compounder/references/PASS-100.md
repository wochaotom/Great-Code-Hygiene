# PASS-100 Rubric

PASS-100 is a 100-point code hygiene scorecard. Use it for eval prompts, real tasks, code reviews, and candidate skill updates.

## Evidence Limits

PASS-100 is a structured rubric, not an external oracle.

- `audit-backed` scores are disciplined self-reports from observed work. They are useful for finding lessons, but they are not objective benchmark proof.
- `script-only` scores validate harness behavior, JSON shape, and promotion plumbing. They do not measure model code quality.
- `model-execution` scores are stronger evidence because they evaluate actual model outputs from task prompts.
- Do not compare different run types as if they were the same metric.
- Do not use `audit-backed` or `script-only` scores as final promotion evidence for major skill changes without a matching `model-execution` run or external review.
- Always record deductions, unrun checks, and residual risk. A high score without evidence is just a claim.

## Scoring

Score each run from 0 to 100. Record evidence for every deduction. Critical failures may cap the total even when other categories look strong.

| Category | Points | Checks |
| --- | ---: | --- |
| Correctness and behavior preservation | 15 | Solves the requested problem, preserves existing behavior, handles edge cases, avoids regressions. |
| Test quality and verification | 15 | Builds the smallest deterministic feedback loop for bugs/regressions/flakes before fixing when possible, runs meaningful checks, adds or updates tests when warranted, reports unrun checks, avoids false confidence. |
| Simplicity and maintainability | 15 | Keeps the change small, readable, cohesive, and free of unnecessary abstraction or churn. |
| Security and data safety | 10 | Handles validation, authorization, secrets, injection, unsafe deserialization, path traversal, privacy, and dependency risk. |
| Local integration | 10 | Fits existing architecture, APIs, naming, formatting, error patterns, and framework conventions. |
| Minimal reviewable diff | 10 | Avoids unrelated rewrites, generated noise, broad formatting, and accidental user-change reverts. |
| Error handling and observability | 10 | Covers failure modes, user-facing errors, logs, metrics, retries, timeouts, and debuggability. |
| Documentation and comments | 5 | Updates necessary docs, comments only where useful, removes misleading comments. |
| Dependency and config hygiene | 5 | Avoids needless dependencies, updates config safely, respects lockfiles and environment constraints. |
| Agent process hygiene | 5 | Grounds in repo facts, communicates assumptions, uses tools safely, records durable lessons. |

## Caps

- Cap at 60 if the solution likely breaks the main requested behavior.
- Cap at 70 if verification is absent for a risky behavior change.
- Cap at 72 if a bug, regression, or flaky behavior is patched from inspection only while a deterministic feedback loop was feasible.
- Cap at 75 if the diff includes unrelated rewrites or reverts user work.
- Cap at 80 if a security-sensitive path is changed without explicit safety review.
- Cap at 85 if tests pass but important edge cases are ignored.

## Result Schema

Use this JSON shape for script scoring:

```json
{
  "run_id": "phase0-smoke-001",
  "run_type": "audit-backed",
  "phase": 0,
  "prompt_ids": ["HYG-001"],
  "scores": [
    {
      "prompt_id": "HYG-001",
      "total": 88,
      "categories": {
        "correctness": 14,
        "tests": 12,
        "maintainability": 14,
        "security": 9,
        "local_integration": 9,
        "minimal_diff": 10,
        "observability": 8,
        "documentation": 4,
        "dependencies": 4,
        "agent_process": 4
      },
      "deductions": ["Did not test one error path."],
      "lessons": ["For payment-adjacent changes, include declined/error-path verification."]
    }
  ]
}
```

## Promotion Thresholds

- Smoke run: no critical failures and average score at least 80.
- Focused run: average score at least 85 and no category worse than the previous accepted generation.
- Full phase run: average score must not regress; critical categories must not regress.
- Tie-breaker: prefer shorter, clearer instructions with fewer special cases.

## Source Anchors

When a score includes a lesson or promotion candidate, record at least one source anchor:

- `source_id`: one of the IDs from `source-weights.json`, or `eval-failure` for a purely observed failure.
- `principle`: one concise principle from `hygiene-principles.md`.
- `evidence`: the artifact, prompt, failed check, or reviewer observation that supports the deduction or lesson.

Do not promote a skill update from source preference alone. The update must improve behavior against a PASS-100 category, a source-backed principle, or a concrete eval failure.
