# Spec: Code Hygiene Delegation

Status: draft, before review R1. Owner: maintainers.
Machine-readable thresholds:
[`code-hygiene-delegation.json`](code-hygiene-delegation.json). Earlier efforts
on the same skill: [`code-hygiene-token-diet-v2.md`](code-hygiene-token-diet-v2.md)
(merged) and [`code-hygiene-report-brevity.md`](code-hygiene-report-brevity.md)
(stopped).

## Contents

- Why
- Harness
- Scope of Change
- Metrics
- Calibration and Stop Rules
- Loop Rules
- Acceptance Criteria and Decision
- Budget and Time
- Review Log
- Results

## Why

The owner runs main sessions on Opus and uses Haiku and Sonnet as subagents. A
subagent does not see skill text loaded in the parent session. It follows the
hygiene rules only if the parent writes them into the task, or re-checks the
subagent's work. The skill says nothing about delegation.

The goal is a short `## Delegation` section that makes Opus:

- give each subagent a scoped, evidence-returning brief;
- re-run the targeted check itself before it reports a subagent's result.

It must not cost quality, resolution, reproduce-first behavior, or more than 15
percent extra cost.

A probe session (hyg-006, current skill, 0.35 USD) found:

- Opus delegated to both subagents;
- the subagents ran on Haiku and Sonnet;
- every subagent tool call appears in stream-json with `parent_tool_use_id`.

Opus already wrote a scoped, evidence-returning brief and re-ran the tests
itself. So the current skill may already be near the ceiling on this metric;
calibration decides whether there is room to improve (see Stop Rules).

## Harness

Each session is one Opus `-p` session with:

- the skill invoked explicitly from a staged copy, as in earlier efforts;
- at most 40 turns;
- `Agent` added to the allowed tools;
- `--forward-subagent-text`;
- two fixed subagent definitions passed with `--agents`:
  - `scout`: Haiku; Read, Glob, Grep, and Bash;
  - `implementer`: Sonnet; Read, Edit, Write, Glob, Grep, and Bash.

The subagents have no Skill tool, so the brief is their only route to the
rules. The task prompt gets one fixed line in both arms: "Delegate
investigation and the code change to the scout and implementer subagents; keep
your own context for planning and review." Fixture split as before: six train,
four holdout.

## Scope of Change

The only editable region is the gap between "Report evidence, skipped checks,
assumptions, and residual risk." and `## Tool And Access Limits`. The new
section goes there. The rest of the normalized body must stay byte-identical.

The section may add at most 700 normalized bytes and 80 new words. The frozen
items carry over from the brevity spec unchanged:

- the frontmatter hash;
- 38 load-bearing sentences;
- the Report anchors.

`tests/test_code_hygiene_core_rules.py` reads this spec's JSON.

## Metrics

Parent calls are tool calls in events without `parent_tool_use_id`. Subagent
calls carry the id of the parent's Agent call. Brief signals are frozen
case-insensitive patterns, applied to each parent Agent prompt:

| Signal | Meaning |
| --- | --- |
| B1 reproduce | asks to reproduce or run tests before editing (diagnostic only) |
| B2 scope | limits the change: only, do not modify, leave alone, minimal |
| B3 evidence | asks for exact commands or verbatim output back |

Per session:

| Measure | Definition |
| --- | --- |
| Delegated | at least one parent Agent call to `scout` or `implementer` |
| Brief complete | at least one implementer call, and every implementer prompt matches B2 and B3 |
| Re-verified | after the last subagent result, the parent itself makes a strict test call (the existing strict rule: a test command whose own output shows tests ran) |
| Reproduced first | the existing strict rule over parent and subagent calls together, in event order |

The loop metric is **M**, higher is better: the mean over sessions of (brief
complete + re-verified) / 2.

## Calibration and Stop Rules

Calibration runs the current skill once on each of the six train fixtures,
about 2.2 USD. The effort stops before the loop, and records the result, if
either holds:

- base M is 0.75 or higher. AC1 needs a gain of at least 0.25, so there is no
  room left;
- fewer than 4 of 6 sessions delegate.

## Loop Rules

The autoresearch loop runs headless on Opus:

- driver budget 1.50 USD;
- starting from tag `delegation-base`, which holds the current text;
- Scope is `code-hygiene/SKILL.md` only;
- one change per iteration.

Verify runs `measure --delegate` on the six train fixtures, which prints M. It
uses mechanical signals only, so there is no judge cost.

Guard:

- static: frontmatter, scope, frozen sentences, editable region, at most 80 new
  words, at most 700 added bytes;
- behavioral, from the same measured sessions:
  - unresolved at most 1 of 6;
  - delegated at least 80 percent;
  - strict reproduced first at least calibration's minus 1.

A change is kept only if M rises by at least 0.1. The starting text for the
first iteration:

> Subagents do not see this skill. When you delegate, put the rules in the
> task: reproduce the failure with a test before editing, make the smallest
> change, leave tests and user files alone, and return the exact commands run
> with their output. Treat a subagent's summary as a claim: re-run the
> targeted check yourself before you report.

The loop stops at the first of these:

- 3 iterations;
- 2 consecutive rejections;
- a ledger total of 20 USD;
- 06:00 UTC.

## Acceptance Criteria and Decision

Final comparison:

- two arms: the current text (`c2f699d`) and the best kept candidate;
- all ten fixtures, two rounds each, 40 sessions;
- graded by the blind Opus PASS-100 judge, with one retry for a reply that
  breaks the cap rule.

If calibration shows more than 0.40 USD per session, the final run uses one
round and each slack is halved, rounded down.

| AC | Criterion |
| --- | --- |
| AC1 | M of the candidate at least the original's plus 0.25 |
| AC2 | Strict reproduced first (parent plus subagents) at least the original's minus 2 of 20 |
| AC3 | Pooled PASS-100 difference at least -1.5; lower bound of the 90 percent bootstrap at least -4.0; holdout difference at least -3.0 |
| AC4 | Resolved at least the original's minus 1, and at least 19 of 20 |
| AC5 | Cost ratio at most 1.15 |
| AC6 | Body grows by at most 700 bytes; frozen sentences, frontmatter, anchors, and mirrors intact; matching init fingerprints |
| AC7 | Each arm delegates in at least 16 of 20 sessions |
| AC8 | Unit suite, `validate_package.py`, and CI on Ubuntu, Windows, and macOS pass; review R2 has no open blocking finding |

Decision: if every criterion is met, squash-merge into `main`. Otherwise, merge
only the tooling and this record, with the skill text unchanged.

## Budget and Time

- Cap: 40 USD, enforced by `/home/user/hygiene-evals/delegation/ledger.jsonl`.
- Estimated spend:

  | Item | Cost (USD) |
  | --- | --- |
  | Probe | 0.35 |
  | Calibration | 2.2 |
  | Loop | about 11 |
  | Final comparison | about 18 |
  | Reviews | about 2 |
- If the ledger passes 26 USD before the final comparison, the final uses the
  one-round fallback.
- Times (UTC):
  - loop ends by 06:00;
  - final comparison graded by 06:45;
  - decision by 07:15.
- Missing a time or the cap means stop, record, and do not change the skill.

## Review Log

| ID | Review | Severity | Finding | Disposition |
| --- | --- | --- | --- | --- |

## Results

Pending.
