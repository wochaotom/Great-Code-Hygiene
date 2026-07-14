# Contributing

Contributions should preserve Great Code Hygiene's evidence-first behavior and
keep the three public editions coherent.

## Development Setup

Normal skill installation needs Node.js and npm for `npx`. Maintainer checks
and the full trainer require Python 3.11 or newer. The project otherwise uses
the Python standard library and has no install step.

Clone the repository, create a branch, and run the narrowest check relevant to
your change. Before opening a pull request, run:

```bash
python -B -m unittest discover -s tests -v
python code-hygiene-compounder/scripts/validate_package.py --repo-root .
python code-hygiene-compounder/scripts/guardrail_check.py --skill-root code-hygiene-compounder
python code-hygiene-compounder/scripts/fixture_runner.py --fixtures code-hygiene-compounder/fixtures validate --suite code-hygiene-compounder/references/eval-prompts.md
python code-hygiene-compounder/scripts/fixture_runner.py --fixtures code-hygiene-compounder/fixtures baseline
```

## Source Of Truth

Edit `code-hygiene-compounder/` for full trainer changes. Do not hand-edit its
generated Claude packages, Codex plugin skill copy, context index, or portable
prompt. Regenerate and validate those artifacts from the canonical skill.

Edit `code-hygiene/` for function-only workflow changes and
`code-hygiene-skeleton/` for the blank template. Keep unrelated rewrites out of
the same pull request.

## Promotion Evidence

PASS-100 script output is not model-performance proof. A training promotion
must identify its evidence class, satisfy the documented gates, preserve
holdouts, and record the deterministic loop used. New sources remain candidate
evidence until the source audit and promotion gates pass.
