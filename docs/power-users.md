# Power User Guide

This page keeps maintainer and package-shape details out of the front page.
Start with the root [README](../README.md) if you only want to install and use
Great Code Hygiene.

## Requirements

- Normal `npx skills` installs: Node.js and npm with `npx`.
- Clean or skeleton runtime: no Python dependency imposed by the skill.
- Full trainer and maintainer checks: Python 3.11 or newer.
- Manual fallbacks: Git plus the target coding agent.

## Install Matrix

| Surface | Clean | Full trainer | Skeleton | Notes |
| --- | --- | --- | --- | --- |
| Claude Code skill install | Yes | Yes | Yes | Use `npx skills@latest add ... --agent claude-code`. |
| Codex skill install | Yes | Yes | Yes | Use `npx skills@latest add ... --agent codex`. |
| Cursor skill install | Yes | Yes | Yes | Use `npx skills@latest add ... --agent cursor`. |
| Antigravity skill install | Yes | Yes | Yes | Use `npx skills@latest add ... --agent antigravity`. |
| Claude Code plugin marketplace | Yes | Yes | No | Plugins `code-hygiene` and `code-hygiene-compounder`. |
| Codex plugin marketplace | No | Yes | No | Plugin bundle installs `code-hygiene-compounder`. |
| ChatGPT, Claude web, Gemini | Profile/prompt | Profile/prompt | Manual adaptation | Chatbots need files, connectors, or pasted context. |

## Update Commands

Clean:

```bash
npx skills@latest update code-hygiene --global --yes
```

Full trainer:

```bash
npx skills@latest update code-hygiene-compounder --global --yes
```

Skeleton:

```bash
npx skills@latest update code-hygiene-skeleton --global --yes
```

## Removal Commands

Remove a skill installed through `npx skills` by its edition name:

```bash
npx skills@latest remove code-hygiene --global --yes
npx skills@latest remove code-hygiene-compounder --global --yes
npx skills@latest remove code-hygiene-skeleton --global --yes
```

Remove the full trainer plugin from Codex or Claude Code:

```bash
codex plugin remove code-hygiene-compounder@great-code-hygiene
claude plugin uninstall code-hygiene-compounder@great-code-hygiene
```

Remove the clean plugin from Claude Code:

```bash
claude plugin uninstall code-hygiene@great-code-hygiene
```

After removing the plugin, remove the marketplace registration only when you no
longer want any plugins from this repository:

```bash
codex plugin marketplace remove great-code-hygiene
claude plugin marketplace remove great-code-hygiene
```

Both clients report the installed full trainer plugin id as
`code-hygiene-compounder@great-code-hygiene`, Claude Code reports the clean
plugin as `code-hygiene@great-code-hygiene`, and the configured marketplace
name is `great-code-hygiene`. The removal commands use those persisted
identifiers, not the capitalization of the GitHub repository slug.

## Manual Fallbacks

Use these only when `npx` and plugin marketplaces are unavailable.

Claude Code clean install:

```bash
git clone https://github.com/wochaotom/Great-Code-Hygiene.git
mkdir -p ~/.claude/skills
cp -R Great-Code-Hygiene/code-hygiene ~/.claude/skills/code-hygiene
```

Codex clean install:

```bash
git clone https://github.com/wochaotom/Great-Code-Hygiene.git
mkdir -p ~/.codex/skills
cp -R Great-Code-Hygiene/code-hygiene ~/.codex/skills/code-hygiene
```

For the full trainer fallback, copy `code-hygiene-compounder` instead of
`code-hygiene`. For the skeleton fallback, copy `code-hygiene-skeleton`.

Cursor project fallback:

```bash
git clone https://github.com/wochaotom/Great-Code-Hygiene.git
mkdir -p .cursor/skills .cursor/rules
cp -R Great-Code-Hygiene/code-hygiene .cursor/skills/code-hygiene
cp Great-Code-Hygiene/.cursor/rules/code-hygiene.mdc .cursor/rules/code-hygiene.mdc
```

Antigravity project fallback:

```bash
git clone https://github.com/wochaotom/Great-Code-Hygiene.git
mkdir -p .agents/skills
cp -R Great-Code-Hygiene/code-hygiene .agents/skills/code-hygiene
```

## Skill Install vs Plugin Install

| Shape | What it installs | Best for |
| --- | --- | --- |
| Skill install | One selected skill directory: `code-hygiene`, `code-hygiene-compounder`, or `code-hygiene-skeleton`. | Most users and normal coding-agent installs. |
| Plugin install | In Claude Code, `code-hygiene` (clean) or `code-hygiene-compounder` (full trainer). In Codex, `code-hygiene-compounder` only. | Claude Code users who prefer `/plugin`, maintainers, and users who explicitly want PASS-100/training tools. |

The clean Claude Code plugin is the `code-hygiene/` skill directory with no
plugin manifest; its marketplace entry supplies the plugin metadata. The
skeleton edition is a skill only. The full trainer plugin is heavier because it
carries source-grounded audit tools, fixtures, package validation scripts, and
the context index.

## Codex Plugin Config

The Codex plugin marketplace currently installs the full trainer package.

```bash
codex plugin marketplace add wochaotom/Great-Code-Hygiene
codex plugin add code-hygiene-compounder@great-code-hygiene
```

On Windows, if Git reports `Filename too long` while Codex clones the
marketplace, enable long paths for Git and rerun the command:

```bash
git config --global core.longpaths true
codex plugin marketplace add wochaotom/Great-Code-Hygiene
codex plugin add code-hygiene-compounder@great-code-hygiene
```

If you manage Codex by config, the plugin id is:

```toml
[plugins."code-hygiene-compounder@great-code-hygiene"]
enabled = true
```

## Source of Truth

| Surface | Source of truth | Synced/generated copies |
| --- | --- | --- |
| Clean workflow | `code-hygiene/` | `.cursor/skills/code-hygiene/`, `.agents/skills/code-hygiene/` |
| Skeleton template | `code-hygiene-skeleton/` | Installed only when selected with `--skill code-hygiene-skeleton` |
| Full trainer skill | `code-hygiene-compounder/` | Claude AI package, Claude command package, Codex plugin skill copy |
| Claude plugin manifest | `.claude-plugin/marketplace.json` (both plugins), `code-hygiene-compounder/.claude-plugin/plugin.json` (full trainer) | None |
| Codex plugin manifest | `.agents/plugins/marketplace.json`, `plugins/code-hygiene-compounder/.codex-plugin/plugin.json` | `plugins/code-hygiene-compounder/skills/code-hygiene-compounder/` |
| Chat-only use | `chatbot-profiles/` and `portable-prompts/code-hygiene-compounder-chat.md` | Profile-specific custom instructions |

## Package Targets

| Target | Path |
| --- | --- |
| Clean function-only skill | `code-hygiene/` |
| Skeleton template skill | `code-hygiene-skeleton/` |
| Full trainer source of truth | `code-hygiene-compounder/` |
| Claude Code plugin marketplace index | `.claude-plugin/marketplace.json` |
| Claude Code plugin manifest | `code-hygiene-compounder/.claude-plugin/plugin.json` |
| Codex plugin marketplace index | `.agents/plugins/marketplace.json` |
| Codex plugin bundle | `plugins/code-hygiene-compounder/` |
| Codex plugin skill copy | `plugins/code-hygiene-compounder/skills/code-hygiene-compounder/` |
| Cursor project rule and skill | `.cursor/rules/code-hygiene.mdc` and `.cursor/skills/code-hygiene/` |
| Antigravity workspace skill | `.agents/skills/code-hygiene/` |
| Claude web upload package | `code-hygiene-compounder-claude-ai/` |
| Legacy Claude command package | `code-hygiene-compounder-command/` |
| Chat-only prompt | `portable-prompts/code-hygiene-compounder-chat.md` |
| Chatbot profiles | `chatbot-profiles/` |

## Maintainer Checks

Before publishing or committing package-shape changes, run:

```bash
python code-hygiene-compounder/scripts/validate_package.py --repo-root .
python code-hygiene-compounder/scripts/guardrail_check.py --skill-root code-hygiene-compounder
```

For fixture and PASS-100 tooling:

```bash
python code-hygiene-compounder/scripts/pass100_runner.py list --suite code-hygiene-compounder/references/eval-prompts.md
python code-hygiene-compounder/scripts/fixture_runner.py --fixtures code-hygiene-compounder/fixtures validate --suite code-hygiene-compounder/references/eval-prompts.md
python code-hygiene-compounder/scripts/fixture_runner.py --fixtures code-hygiene-compounder/fixtures baseline
```

For context-index drift:

```bash
python code-hygiene-compounder/scripts/source_audit_plan.py --skill-root code-hygiene-compounder --context-index --out code-hygiene-compounder/references/context-index.json --check
```

Optional local Git hooks are available for maintainers:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools/hooks/install-local-hooks.ps1
```

CI is authoritative. Hooks run deterministic local checks only; they do not run
model-execution promotion gates, sync local Codex installs, or contact external
services.

### CLI Documentation Checks

The repository contract tests preserve commands after they have been reviewed;
they do not install third-party CLIs in CI. Before a release that changes setup
documentation, verify the public command surfaces directly:

```bash
npx skills@latest --help
npx skills@latest remove --help
codex plugin add --help
codex plugin remove --help
codex plugin marketplace remove --help
claude plugin install --help
claude plugin uninstall --help
claude plugin marketplace remove --help
```

After a marketplace install, `codex plugin marketplace list --json`,
`codex plugin list --json`, `claude plugin marketplace list --json`, and
`claude plugin list --json` expose the exact identifiers used by removal
commands. Run install and removal smoke tests under an isolated config or test
home so documentation checks do not mutate a developer's active setup.

## Release Process

Claude Code and Codex plugin manifests share one semantic version. Update both
manifests, the Claude marketplace entry, and the validator constant together.
The release contract tests reject drift.

After the package, guardrail, fixture, and baseline checks pass on `main`, push
the annotated Claude plugin tag:

```bash
claude plugin tag --dry-run code-hygiene-compounder
claude plugin tag --push code-hygiene-compounder
```

The tag-triggered release workflow re-runs the gates, verifies that the tag
matches both manifests, builds edition-specific archives, writes SHA-256
checksums, and publishes the GitHub release. Do not upload hand-built archives.

## Full Trainer Internals

Use the full trainer only when you are intentionally maintaining or evaluating
the skill system.

```text
Run PASS-100 smoke for this candidate lesson.
Do not promote unless gates pass.
Treat new evidence as candidate evidence.
```

### Source Routing

The trainer keeps source material outside the active skill body. A registry and
weight file define the admitted corpus. Task domains such as security, API,
frontend, config, release, observability, package, Python, or training activate
only the relevant distilled source packs. A new source remains quarantined
until it adds measurable coverage and has been classified, distilled, and
weighted.

### Evaluation and PASS-100

PASS-100 is a 100-point code-hygiene rubric. It scores the quality of one run,
not the number of prompts and not a universal model ranking.

| Category | Points |
| --- | ---: |
| Correctness and behavior preservation | 15 |
| Test quality and verification | 15 |
| Simplicity and maintainability | 15 |
| Security and data safety | 10 |
| Local integration | 10 |
| Minimal reviewable diff | 10 |
| Error handling and observability | 10 |
| Documentation and comments | 5 |
| Dependency and config hygiene | 5 |
| Agent process hygiene | 5 |

Critical failures cap the score. Promotion compares the candidate with an
accepted baseline and protects correctness, tests, security, and minimal-diff
behavior from regression. The complete rubric and caps are in
[`PASS-100.md`](../code-hygiene-compounder/references/PASS-100.md).

### Fixtures, Matrices, and Real Tasks

The trainer uses three complementary surfaces:

- Executable fixtures reproduce small objective failure modes and protect
  important files from accidental edits.
- Generated matrices vary code shapes and hidden contracts to test target and
  harness quality. Oracle-green matrix output is not model-execution proof.
- Independent real tasks test whether a lesson transfers beyond a synthetic
  example.

Fixtures stay sparse. A new fixture or lesson needs a repeated measurable
failure, independent evidence, or an admitted source-backed rule.

### Model Coverage

A skill's results depend on the model running it, so test each model you
plan to use. The `code-hygiene` frontmatter records the Claude model families
covered by the smoke check below.

On 2026-10-02, a smoke check ran the `hyg-006-currency-rounding` and
`hyg-083-config-precedence` fixtures through Claude Code on Claude Haiku,
Sonnet, and Opus, with both Claude Code plugins installed. Each target was
scored with `fixture_runner.py run`.

| Run | Haiku | Sonnet | Opus |
| --- | --- | --- | --- |
| Fixtures fixed, no skill invoked | 2/2 | 2/2 | 2/2 |
| Fixtures fixed with `/code-hygiene:code-hygiene` | 2/2 | 2/2 | 2/2 |
| Protected test files edited | 0 | 0 | 0 |

- No model loaded either skill on its own for these small fix requests. Invoke
  `/code-hygiene:code-hygiene` when you need the workflow applied.
- Without the skill, Sonnet and Opus each added a new test file for one
  fixture. With the skill, no model added test files.
- With the skill, Haiku copied the progress checklist into its report. Sonnet
  and Opus reported what they changed, what they ran, and what they could not
  check, in prose.

This is a smoke check of two fixtures per model, not a PASS-100 run. It shows
that the skill works on each model family; it does not measure score
differences between models. It ran before the trigger wording below was added
to the `code-hygiene` description.

### Skill Triggering

Claude sees only each skill's name and description until it decides to load
one, so the description decides whether the workflow runs. On 2026-10-02, four
requests that never name the skill ran on fixture repositories with both
Claude Code plugins installed: a pre-ship review, failing tests, a cleanup
refactor, and a "is this safe to expose" hardening question. Each cell counts
runs that loaded `code-hygiene`, over two rounds.

| Setup | Haiku | Sonnet | Opus | Total |
| --- | --- | --- | --- | --- |
| Earlier description | 1/8 | 0/8 | 6/8 | 7/24 |
| Earlier description plus trigger wording in `when_to_use` | 3/8 | 6/8 | 8/8 | 17/24 |
| Earlier description plus a `CLAUDE.md` line | 5/8 | 8/8 | 8/8 | 21/24 |
| Current description, as shipped | 4/8 | 8/8 | 8/8 | 20/24 |

- The current `code-hygiene` description includes the tested trigger wording,
  and the last row was measured on that exact text. The wording sits in the
  description itself rather than Claude Code's `when_to_use` field, which Claude
  Code appends to the description, so Codex, Cursor, and Antigravity see it too.
- The `CLAUDE.md` line was: `For code reviews, bug fixes, refactors, and
  hardening in this repo, use the code-hygiene skill.` It is the most reliable
  option short of invoking the skill by name.
- `code-hygiene-compounder` never loaded for these everyday requests. In one
  Haiku hardening run with the `CLAUDE.md` line, Haiku chose Claude Code's
  built-in `security-review` skill instead.
- Haiku stays the least likely to load a skill on its own. Invoke
  `/code-hygiene` (or `/code-hygiene:code-hygiene` for the plugin) when the
  workflow must run.

A skill's `model` frontmatter field can run it on a different model than the
session, and `context: fork` runs it as a separate subagent. Neither is set
here: `code-hygiene` works inside the current conversation, and the checks above
show it working on each model family.

### Promotion and Overtraining Control

A candidate can be applied only through a v2 evidence bundle passed to
`promote_candidate.py --evidence-bundle`. A score file passed with `--score`
remains readable for diagnosis but cannot authorize `--apply`. The bundle
references SHA-256 checked artifacts: a predeclared plan, matched baseline and
candidate result records, fresh-context external execution records and captured
outputs, target snapshots, verification results, and an independent review that inspected them.
The reviewer report and the fresh reviewer's raw output are distinct hashed
artifacts; the report must match the captured output and name every inspected
artifact hash. A hand-written approval record alone cannot satisfy this gate.
Hashes establish artifact integrity, not that execution really happened;
reviewers must inspect the actual capture. The verifier cannot authenticate an
operator who fabricates every record, including reviewer output. Synthetic
accepted-path tests prove only gate behavior, never an actual promotion.
Script-only and audit-backed scores
cannot be mixed with model-execution scores for promotion.

The accepted verifier, rubric, suite, fixtures, source weights, plugin metadata,
agent metadata, context-index schema, and policy must remain outside
the candidate tree and match the installed baseline's controls. Candidate edits
to those controls require ordinary reviewed repository maintenance. A promotion
must cover every prompt in each predeclared focused category, not a favorable
subset. The verifier reruns each untouched applicable fixture in a temporary
copy and confirms its declared failure signature with protected tests unchanged.
The current-skill model arm may fix that fixture or fail with the known
assertion signature; the candidate arm must pass. Every repository fixture run
must bind a hashed ZIP snapshot of its edited target to its execution,
verification result, and independent review. The archive is checked for unsafe
paths and protected-test changes. A pass claim cannot use a snapshot identical
to the known-failing accepted source, and a report must retain every test
identity observed in the untouched baseline (exactly those identities when
all test files are protected). Each execution also carries the
predeclared plan hash. The plan, both scored results, and every execution
record must agree on the harness command and settings; the recorded execution
arguments must exactly match the planned command. Use `fixture_runner.py snapshot` after running
the tests to create it. This binding makes the edited target inspectable but
does not, by itself, prove the recorded tests ran on that exact archive.
Edited fixture targets are executable code. Run them only in an appropriately
isolated external harness; a test reporter and hashed output cannot establish
authenticity against code that can tamper with the harness or an operator who
fabricates all inputs.
A promotion also requires structural budgets, package parity, no aggregate
mean regression and no critical-category regression on declared critical prompts,
a focused average of at least 85, and a predeclared gain (or identical category
scores for every matched prompt and trial with smaller active instructions). For
equal-score promotions, the conservative size
check counts `SKILL.md` and eligible instruction files under `references/`
in both trees. Generated context-index JSON, its schema, source-weight JSON,
agent metadata, and plugin metadata cannot supply a size reduction; the pinned
control files must match accepted controls. V2 category and total scores use
half-point increments, so floating-point dust cannot constitute a gain.
Candidate roots outside the declared package layout are rejected.
It requires at least 32 fewer bytes and 16 fewer non-whitespace bytes; moving
text into another extension or trimming only whitespace does not qualify.
Candidate trees containing excluded runtime or metadata paths are rejected,
since those files would not be installed. Each target ID binds to a
nonempty snapshot
artifact in the plan and execution record; hard mode needs three distinct
snapshot hashes. The reviewer must inspect the snapshots as well as run records.
Source-backed edits, including source-derived reference changes, need a valid
honing report in the bundle. Its activated IDs must be accepted weighted sources;
every always-activated source and changed source pack must be named.
Unavailable gates
fail; they do not become implicit passes.

Promotion `--apply` requires a writable `--log` path outside both the current
and candidate trees;
the flushed `apply_started` record precedes the directory swap. Its absence
blocks application. The current path must be the full canonical trainer
package, including its controlled scripts, fixtures, agents, and plugin
metadata; an isolated edition export is not a promotion baseline.
Installation stages the candidate, verifies its fingerprint, journals the
transaction, and swaps directories. A pending journal blocks another apply
until `promote_candidate.py --current path/to/skill --recover` rolls back an
incomplete swap or closes a verified commit journal. Durable run and fixture
data excluded from promotion is moved into the new installation; bytecode,
tool caches, and `dist` remain in the retained backup. The previous tree is
retained at the reported `retained_backup` path even after a successful apply;
run recovery only after the apply process has exited. Quiesce writers and
inspect the backup before manual removal. This avoids deleting a
late write into the old tree during automatic cleanup.
If rollback displaces an installed candidate, recovery retains that tree at
the reported `retained_discard` path rather than deleting possible late writes.
If runtime data appears in both trees or remains in the backup after the move,
the journal and backup remain intact for manual reconciliation.
The verifier rejects local bytecode caches in its script tree before importing
internal modules. Package validation also rejects fingerprint-excluded content
inside any distributed trainer root; direct exports omit those paths.

Claude export refuses an output directory that overlaps the skill root or an
existing directory it did not create. Repeated exports replace only an
unchanged, marked prior export; user edits in that output are preserved by
refusing the replacement.

Phase advancement remains a human decision. The trainer can recommend more
coverage but cannot declare that a broader eval phase is warranted on its own.

### Historical Evidence Audit

The v0.3.0 audit inspected reachable Git history, retained local evidence, and
available CI artifacts. It found 55 existing promoted lessons and four named
post-release promotion commits. No target-level model outputs, matched score
records, reviewer records, or promotion decisions were retained for those
lessons. All 55 are therefore **unverifiable**, not contradicted, against the
requirements in force when they were added; none is eligible under the new v2
protocol. Existing lessons and Git history are preserved. A passing package CI
run is not evidence that a model-execution promotion gate passed.

### Migration From Score Files

Existing result files can still be validated and analyzed. For a new promotion,
predeclare targets, trials, critical prompts, model, harness, runtime, and the
accepted control hashes before running either arm. Capture each fresh external
run's output and verification, score matched trials under the same rubric, and
obtain an independent review of those artifacts. Supply their relative paths
and hashes in a v2 bundle; run without `--apply` first to inspect every gate.
Do not use synthetic accepted-path tests as evidence of real model behavior.

### What the Scripts Automate

| Script | Responsibility |
| --- | --- |
| `source_audit_plan.py` | Activate source packs and maintain the context index |
| `pass100_runner.py` | List prompts, select batches, and score supplied result records |
| `validate_results.py` | Reject malformed or inconsistent result artifacts |
| `analyze_runs.py` | Summarize scores, intervals, pass rates, and baseline deltas |
| `fixture_runner.py` | Validate, prepare, run, and baseline executable fixtures |
| `matrix_runner.py` | Generate deterministic target matrices and review-contract cases |
| `matrix_families.py` | Define the deterministic matrix families consumed by the runner |
| `guardrail_check.py` | Enforce instruction, lesson, fixture, script, source, and noise budgets |
| `validate_honing_report.py` | Validate source-grounded audit reports |
| `promote_candidate.py` | Consume promotion artifacts and optionally apply an approved candidate |
| `export_claude_package.py` | Build Claude skill, Claude.ai, legacy command, and portable prompt formats |
| `validate_package.py` | Check manifests, package shape, synced copies, docs, and generated noise |

These scripts are deterministic gatekeepers. They do not call a model, judge
source code, extract lessons, or prove model performance. The surrounding agent
or operator still runs tasks, captures outputs, scores judgment-dependent
categories, and executes the full promotion protocol. Only `model-execution`
evidence evaluates actual model behavior on prompts.

## Chatbot Profiles

The chatbot profile files are setup instructions for reusable chatbot personas:

```text
chatbot-profiles/chatgpt-gpt-instructions.md
chatbot-profiles/claude-project-instructions.md
chatbot-profiles/gemini-gem-instructions.md
portable-prompts/code-hygiene-compounder-chat.md
```

Connectors can help a chatbot read a GitHub repo, Google Drive folder, or
uploaded files. They do not automatically install this workflow.

## FAQ

### Why use npx?

`npx skills@latest add` installs agent skills from public GitHub repositories
into supported agents. It avoids manual copying for normal users.

### What if I want broad readability-only renaming?

Great Code Hygiene may improve names and comments when they affect correctness,
maintainability, reviewability, or user-facing diagnostics. For broad
readability-only renaming or de-jargoning, use a separate `humanize-code` pass.

### Does the repo need separate branches for each edition?

No. All three editions are maintained on `main`. Users select the edition with
the `--skill` flag.
