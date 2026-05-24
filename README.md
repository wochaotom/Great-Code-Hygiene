# Great Code Hygiene

**Turn Claude Code, OpenAI Codex, Cursor, Antigravity, ChatGPT, Claude, and
Gemini into evidence-first code hygiene agents.**

![Claude Code Skill](https://img.shields.io/badge/Claude_Code-Skill-blue?logo=anthropic&logoColor=white)
![Codex Skill](https://img.shields.io/badge/Codex-Skill-green?logo=openai&logoColor=white)
![Cursor Skill](https://img.shields.io/badge/Cursor-Skill-black)
![Antigravity Skill](https://img.shields.io/badge/Antigravity-Skill-lightgrey)
![npx skills](https://img.shields.io/badge/npx-skills-orange)
![PASS-100](https://img.shields.io/badge/PASS--100-rubric-purple)
![License](https://img.shields.io/badge/license-Apache--2.0-blue)

*"Set the task -> the agent reads, reproduces, patches, verifies, and
reports."*

Great Code Hygiene is a portable workflow for code review, cleanup, debugging,
hardening, packaging, and agent evaluation. It teaches coding agents to read
first, build the smallest useful feedback loop, patch narrowly, verify with
real commands, and report evidence instead of confidence.

[Quick Start](#quick-start) | [Which Edition](#which-edition) |
[Use It](#use-it) | [Chatbots](#chatgpt-claude-and-gemini) |
[Power Users](docs/power-users.md) | [License](#license)

---

## What It Does

Great Code Hygiene gives your agent a repeatable loop:

1. Read repo instructions, code, tests, manifests, and local patterns.
2. For bugs or regressions, reproduce the symptom or state why no loop is
   possible.
3. Make the smallest behavior-correct change.
4. Verify with the narrowest meaningful check first.
5. Report commands, evidence, skipped checks, assumptions, and residual risk.

It is useful for:

- code review and PR risk checks
- bug fixing and regression cleanup
- refactors that should preserve behavior
- package, config, docs, and release hygiene
- maintainer-only training and PASS-100 evaluation

## Which Edition

Install `code-hygiene` first unless you are maintaining this project or building
your own workflow.

| Edition | Skill | Use it when... | Self-training |
| --- | --- | --- | --- |
| Clean | `code-hygiene` | You want review, cleanup, bug-fix, hardening, and verification behavior. | No |
| Full trainer | `code-hygiene-compounder` | You want PASS-100, source audits, exports, fixtures, and gated skill evolution. | Only when explicitly requested and gates pass |
| Skeleton | `code-hygiene-skeleton` | You want a blank starting point with no inherited sources, fixtures, lessons, or rubric. | User-defined |

The clean edition can still modify your project when you ask for a fix or
refactor. "No self-training" means it will not mutate itself, add source packs,
or run promotion loops.

## Quick Start

These commands install from the public GitHub repo with `npx skills`.

### Claude Code

```bash
npx skills@latest add wochaotom/Great-Code-Hygiene --skill code-hygiene --agent claude-code --global --yes
```

Restart Claude Code, then ask:

```text
Review this repo with Code Hygiene and report verification evidence.
```

### OpenAI Codex

```bash
npx skills@latest add wochaotom/Great-Code-Hygiene --skill code-hygiene --agent codex --global --yes
```

Invoke it by name when useful:

```text
$code-hygiene review this repo and report verification evidence.
```

### Cursor

```bash
npx skills@latest add wochaotom/Great-Code-Hygiene --skill code-hygiene --agent cursor --global --yes
```

### Antigravity

```bash
npx skills@latest add wochaotom/Great-Code-Hygiene --skill code-hygiene --agent antigravity --global --yes
```

### Install Another Edition

Use the same command shape and change only `--skill`:

```bash
# Full trainer
npx skills@latest add wochaotom/Great-Code-Hygiene --skill code-hygiene-compounder --agent <agent> --global --yes

# Blank skeleton
npx skills@latest add wochaotom/Great-Code-Hygiene --skill code-hygiene-skeleton --agent <agent> --global --yes
```

Supported `<agent>` values in this repo are `claude-code`, `codex`, `cursor`,
and `antigravity`.

### Plugin Marketplace

The plugin marketplace packages install the full trainer,
`code-hygiene-compounder`.

Claude Code:

```text
/plugin marketplace add wochaotom/Great-Code-Hygiene
/plugin install code-hygiene-compounder@great-code-hygiene
/reload-plugins
```

Codex:

```bash
codex plugin marketplace add wochaotom/Great-Code-Hygiene
```

Use the `npx skills` commands above when you want the clean function-only
edition or the skeleton template.

## Use It

Ask for the workflow directly:

```text
Review this repo with Code Hygiene.
Focus: correctness, regressions, tests, security/data safety, config, packaging
Output: findings first, then verification evidence and residual risk
```

```text
Use Code Hygiene to fix this failing check:
Check: <command>
Guard: <optional broader command>
```

```text
Scrub <folder/file> with Code Hygiene.
Avoid unrelated rewrites. Report exact checks run.
```

For trainer work:

```text
Run PASS-100 smoke for this candidate lesson.
Do not promote unless gates pass.
Treat new evidence as candidate evidence.
```

## ChatGPT, Claude, and Gemini

Web chatbots do not install native coding-agent skills. Use the matching profile
as custom instructions or project/Gem instructions, then attach the portable
prompt as knowledge when the platform supports files:

```text
chatbot-profiles/chatgpt-gpt-instructions.md
chatbot-profiles/claude-project-instructions.md
chatbot-profiles/gemini-gem-instructions.md
portable-prompts/code-hygiene-compounder-chat.md
```

Chatbots still need uploaded files, connectors, or pasted context to inspect a
repo. They cannot prove tests passed unless they have tool access or you provide
the command output.

## For Power Users

See [docs/power-users.md](docs/power-users.md) for:

- update commands and manual fallbacks
- skill install vs plugin install details
- package layout and source-of-truth paths
- maintainer checks and CI commands
- PASS-100, fixture, and export workflow notes

## FAQ

### Does it run automatically?

Installed skill systems may invoke it when the task clearly matches review,
cleanup, debugging, hardening, packaging, testing, or evaluation. You can also
invoke `code-hygiene` or `code-hygiene-compounder` by name.

### Does it replace tests?

No. It makes the agent find or build the smallest meaningful feedback loop and
state what was actually verified.

### Which version should I install first?

Install `code-hygiene`. Install `code-hygiene-compounder` only when you want to
maintain, train, score, export, or evolve the skill itself.

### Can it modify my code?

Yes, when you ask it to fix, refactor, clean up, or harden code. The clean
edition does not mutate or train itself.

### Is PASS-100 a benchmark?

No. PASS-100 is this project's scoring rubric for hygiene behavior. Treat
`script-only`, `audit-backed`, and `model-execution` evidence as different
evidence classes.

## License

Great Code Hygiene is licensed under the Apache License, Version 2.0. See
[LICENSE](LICENSE) and [NOTICE](NOTICE).
