# Power User Guide

This page keeps maintainer and package-shape details out of the front page.
Start with the root [README](../README.md) if you only want to install and use
Great Code Hygiene.

## Install Matrix

| Surface | Clean | Full trainer | Skeleton | Notes |
| --- | --- | --- | --- | --- |
| Claude Code skill install | Yes | Yes | Yes | Use `npx skills@latest add ... --agent claude-code`. |
| Codex skill install | Yes | Yes | Yes | Use `npx skills@latest add ... --agent codex`. |
| Cursor skill install | Yes | Yes | Yes | Use `npx skills@latest add ... --agent cursor`. |
| Antigravity skill install | Yes | Yes | Yes | Use `npx skills@latest add ... --agent antigravity`. |
| Claude Code plugin marketplace | No | Yes | No | Plugin bundle installs `code-hygiene-compounder`. |
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
| Plugin install | A manifest-backed full trainer bundle named `code-hygiene-compounder`. | Maintainers, plugin marketplace testing, and users who explicitly want PASS-100/training tools. |

The clean and skeleton editions are skills, not plugin bundles. The plugin
bundle is heavier because it carries the full trainer, source-grounded audit
tools, fixtures, package validation scripts, and context index.

## Codex Plugin Config

The Codex plugin marketplace currently installs the full trainer package.

```bash
codex plugin marketplace add wochaotom/Great-Code-Hygiene
```

On Windows, if Git reports `Filename too long` while Codex clones the
marketplace, enable long paths for Git and rerun the command:

```bash
git config --global core.longpaths true
codex plugin marketplace add wochaotom/Great-Code-Hygiene
```

If you manage Codex by config, the plugin id is:

```toml
[plugins."code-hygiene-compounder@great-code-hygiene"]
enabled = true
```

## Source Of Truth

| Surface | Source of truth | Synced/generated copies |
| --- | --- | --- |
| Clean workflow | `code-hygiene/` | `.cursor/skills/code-hygiene/`, `.agents/skills/code-hygiene/` |
| Skeleton template | `code-hygiene-skeleton/` | Installed only when selected with `--skill code-hygiene-skeleton` |
| Full trainer skill | `code-hygiene-compounder/` | Claude AI package, Claude command package, Codex plugin skill copy |
| Claude plugin manifest | `.claude-plugin/marketplace.json`, `code-hygiene-compounder/.claude-plugin/plugin.json` | None |
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

## Full Trainer Notes

Use the full trainer only when you are intentionally maintaining or evaluating
the skill system.

```text
Run PASS-100 smoke for this candidate lesson.
Do not promote unless gates pass.
Treat new evidence as candidate evidence.
```

PASS-100 is a rubric and harness, not model-performance proof by itself. Only
`model-execution` evidence proves actual model behavior on prompts.

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
