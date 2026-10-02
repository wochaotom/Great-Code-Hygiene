# Automation Commands

Run these scripts; do not read them into context unless a script fails and you need its logic. They need Python 3.11 or newer and use only the standard library, so there is nothing to install. Run them from the skill directory: every path below is relative to it. Use `python3` where `python` is not on PATH.

## Commands

```bash
python scripts/pass100_runner.py list --suite references/eval-prompts.md
python scripts/pass100_runner.py batch --suite references/eval-prompts.md --mode smoke --out runs/smoke.json
python scripts/validate_results.py --results runs/results.json --suite references/eval-prompts.md
python scripts/pass100_runner.py score --results runs/results.json --out runs/score.json
python scripts/analyze_runs.py --results runs/results.json --baseline runs/baseline-results.json --suite references/eval-prompts.md --out runs/analysis.json
python scripts/guardrail_check.py --skill-root .
python scripts/fixture_runner.py --fixtures fixtures list
python scripts/fixture_runner.py --fixtures fixtures baseline
python scripts/fixture_runner.py --fixtures fixtures prepare --fixture hyg-006-currency-rounding --target runs/fixtures/hyg-006-currency-rounding
python scripts/fixture_runner.py --fixtures fixtures run --fixture hyg-006-currency-rounding --target runs/fixtures/hyg-006-currency-rounding
python scripts/fixture_runner.py --fixtures fixtures snapshot --fixture hyg-006-currency-rounding --target runs/fixtures/hyg-006-currency-rounding --out runs/fixtures/hyg-006-target.zip
python scripts/matrix_runner.py run --split all --loops 50 --variants-per-family 20 --work-root runs/matrix --out runs/matrix-50x.json
python scripts/matrix_runner.py review --work-root runs/matrix-review --out runs/matrix-review.json
python scripts/promote_candidate.py --current path/to/canonical-trainer --candidate path/to/candidate --evidence-bundle path/to/promotion-bundle.json
python scripts/export_claude_package.py --skill-root . --out-dir path/to/export
python scripts/export_claude_package.py --skill-root . --out-dir path/to/export --format claude-ai-skill --zip-name code-hygiene-compounder-claude-ai.zip
python scripts/export_claude_package.py --skill-root . --out-dir path/to/export --format legacy-command --zip-name code-hygiene-compounder-command.zip
```

## Gate Rules

The scripts are deterministic gatekeepers. Run promotion commands from outside the `--current` canonical trainer directory; add `--apply --log path/to/promotion-audit.jsonl` only after all gates pass. Legacy `--score` calls are diagnostic only and cannot authorize `--apply`. A versioned bundle must contain matched external model executions, hashed outputs, verification, and independent review; see `references/compound-loop.md`.

## What Each Script Proves

- `validate_results.py` rejects malformed PASS-100 evidence before it enters the loop.
- `analyze_runs.py` computes comparable averages, confidence intervals, pass rates, and baseline deltas.
- `guardrail_check.py` keeps active instructions, lessons, sources, fixtures, and scripts inside anti-overtraining budgets.
- `fixture_runner.py` provides a small objective path for executable fixtures.
- `matrix_runner.py` generates larger scratch target matrices for target-quality validation, with train/holdout/all split selection and review-style visible/hidden contract checks; do not treat oracle-green matrix stats as model-execution proof.

The agent still performs code review, eval execution, candidate lesson extraction, and skill editing unless the surrounding environment provides a model runner.
