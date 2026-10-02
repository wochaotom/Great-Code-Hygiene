# Changelog

Notable user-facing changes are recorded here. This project uses semantic
versions for plugin releases.

## 0.3.0 - Unreleased

- Require a versioned, hashed evidence bundle with matched external model
  executions and independent review before training promotion can apply.
- Classify fixture outcomes explicitly and preserve test identities in Python
  and Node baseline checks.
- Make promotion installation staged and recoverable; keep legacy score files
  diagnostic-only.
- Add exact context routing, balanced smoke selection, deterministic package
  archives, a read-only package doctor, and three-platform CI configuration.
- Record the limits of retained historical promotion evidence without changing
  existing lessons or rewriting history.
- Offer the clean `code-hygiene` edition as a Claude Code plugin alongside the
  full trainer.
- Follow Anthropic's skill authoring guidance: contents lists on long
  reference files, a copyable progress checklist with a return-on-failure
  step, sharper skill descriptions, trainer script commands moved to a
  reference file, and recorded Claude model coverage.
- Add measured trigger wording to the `code-hygiene` description and document
  a `CLAUDE.md` line and explicit invocation for reliable skill loading.
- Add the return-on-failure step to the Cursor rule, chatbot profiles, and
  legacy Claude command; document the `AGENTS.md` line for Codex.
- Stop fixture runs from flagging Python bytecode caches as added test files,
  and run fixture tests with a private bytecode cache so planted cache files
  cannot replace protected tests.
- Add `tools/claude_model_check.py` to re-run the cross-model fixture and
  skill-trigger checks and to grade fixture runs against PASS-100 with a blind
  judge model.
- Record a PASS-100 comparison of all ten fixtures with and without
  `code-hygiene` on Claude Haiku, Sonnet, and Opus.
- Add `size`, `metrics`, `guard`, and `compare` to `tools/claude_model_check.py`.
  Also add a cost ledger, `--skill-file` arms, and one judge retry for replies
  that break the rubric's cap rule.
- Freeze the load-bearing sentences and frontmatter of `code-hygiene/SKILL.md`
  with `tests/test_code_hygiene_core_rules.py`.
- Shorten `code-hygiene/SKILL.md` by 27.9 percent and scale its report to the
  change (token-diet experiment). `docs/specs/code-hygiene-token-diet.md`
  records the results, including the two acceptance criteria it missed: cost
  per session and Sonnet quality.

## 0.2.0 - 2026-07-14

- Align Claude Code and Codex plugin manifests on one release version.
- Add pinned Linux and Windows CI checks plus release-gated package publishing.
- Add function-only clean and blank skeleton editions alongside the full
  trainer.
- Expand installation guidance for Claude Code, Codex, Cursor, Antigravity,
  ChatGPT, Claude, and Gemini.
- Harden deterministic feedback loops, evidence reporting, source audits, and
  promotion guardrails.

## 0.1.0 - 2026-05-24

- Publish the initial plugin manifests and code hygiene skill packages.
