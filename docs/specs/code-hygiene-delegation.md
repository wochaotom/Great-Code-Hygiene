# Spec: Code Hygiene Delegation

Status: revised after review R1; frozen before calibration. Owner: maintainers.
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
itself, scoring M = 1.0. So the current skill may already be near the ceiling;
calibration decides whether there is room to improve (see Stop Rules). A
measured "no room" result is an acceptable outcome of this spec.

## Harness

Each session is one Opus `-p` session with:

- the skill invoked explicitly from a staged copy, as in earlier efforts;
- at most 40 turns;
- `Agent` added to the allowed tools;
- `--forward-subagent-text`;
- two fixed subagent definitions passed with `--agents`:
  - `scout`: Haiku; Read, Glob, Grep, and Bash;
  - `implementer`: Sonnet; Read, Edit, Write, Glob, Grep, and Bash.

The two defined subagents have no Skill tool. The built-in agents
(`general-purpose`, `Explore`, `Plan`) stay available, and `general-purpose`
has Skill, so any subagent that changes a file is scored as an implementer
(below). Built-in agent use and background Agent calls are counted as
diagnostics.

The task prompt gets one neutral line in both arms: "Use the scout and
implementer subagents for investigation and the code change." It does not
mention review or verification (R1-1). Fixture split as before: six train,
four holdout.

Sessions are retried once if they break. A comparison with a missing session
after the retry fails. The init fingerprint now includes the agent list, and
each row records the models the session used.

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
case-insensitive patterns, applied to each parent Agent prompt. The visible
set is in the JSON. A second, hidden set is held outside the repository,
with its SHA-256 in the JSON; the loop driver never sees it, and AC1 must
hold on both sets (R1-2).

| Signal | Meaning |
| --- | --- |
| B1 reproduce | asks to reproduce or run tests before editing (diagnostic only) |
| B2 scope | limits the change: only, do not modify, leave alone, minimal |
| B3 evidence | asks for exact commands or verbatim output back |

Per session:

| Measure | Definition |
| --- | --- |
| Delegated | at least one parent Agent call |
| Implementer call | an Agent call to `implementer`, or any Agent call whose subagent changed a file |
| Brief complete | at least one implementer call, and every implementer prompt matches B2 and B3 |
| Re-verified | after the last subagent file change (or, with none, the last subagent result), the parent itself makes a strict test call: a test command whose own output shows tests ran |
| Reproduced first | the existing strict rule over parent and subagent calls together, in event order |

The loop metric is **M**, higher is better: the mean over delegating sessions
of (brief complete + re-verified) / 2. The delegation rate is a separate
check, so M does not reward delegating more often (R1-3).

The judge's action log labels every call `[parent]`, `[scout]`, or
`[implementer]`, and shows each Agent call's subagent and task. Long logs keep
their start and end (R1-8).

## Calibration and Stop Rules

Calibration runs the current skill once on each of the six train fixtures,
about 2.2 USD. The effort stops before the loop, and records the result, if
either holds:

- base M is 0.85 or higher. AC1 needs a gain of at least 0.15, so there is no
  room left;
- fewer than 4 of 6 sessions delegate;
- calibration has not started by 05:00 UTC.

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

A change is kept only if M rises by at least 0.17, two component flips out of
twelve (R1-11). The starting text for the first iteration:

> Subagents do not see this skill. When you delegate, put the rules in the
> task: reproduce the failure with a test before editing, make the smallest
> change, leave tests and user files alone, and return the exact commands run
> with their output. Treat a subagent's summary as a claim: re-run the
> targeted check yourself before you report.

The loop stops at the first of these:

- 3 iterations;
- 2 consecutive rejections;
- a ledger total of 16 USD;
- 06:00 UTC.

## Acceptance Criteria and Decision

Final comparison:

- two arms: the current text (`c2f699d`) and the best kept candidate, run
  together with the same concurrency;
- all ten fixtures, two rounds each, 40 sessions;
- the candidate is copied byte-for-byte into the `.agents/` and `.cursor/`
  mirrors before the final run;
- graded by the blind Opus PASS-100 judge, with one retry for a reply that
  breaks the cap rule.

Fallback: the final run uses one round if calibration shows more than 0.40
USD per session, or if spent + 1.2 × (cost per session × 40) + 4 > 38 USD.
The fallback thresholds are listed in the JSON (`final.fallback`): delegation
in at least 8 of 10, reproduced-first and resolved slack 1, and the same M
gains.

| AC | Criterion |
| --- | --- |
| AC1 | M of the candidate at least the original's plus 0.15, on both the visible and the hidden pattern sets |
| AC2 | Strict reproduced first (parent plus subagents) at least the original's minus 2 of 20 |
| AC3 | Pooled PASS-100 difference at least -1.5; lower bound of the 90 percent bootstrap at least -4.0; holdout difference at least -3.0 |
| AC4 | Resolved at least the original's minus 1 |
| AC5 | Cost ratio at most 1.15 |
| AC6 | Body grows by at most 700 bytes; frozen sentences, frontmatter, anchors, and mirrors intact; matching init fingerprints |
| AC7 | Each arm delegates in at least 16 of 20 sessions |
| AC8 | Unit suite, `validate_package.py`, and CI on Ubuntu, Windows, and macOS pass; review R2 has no open blocking finding |

`compare` keys: AC1 is `delegation_m` and `delegation_m_hidden`; AC2 is
`AC6`; AC3 is `AC3` and `AC4`; AC4 is `AC5`; AC5 is `AC2`; AC7 is
`delegated`.

R1's estimates for these thresholds:

| Change | Chance it passes AC1 to AC7 |
| --- | --- |
| Helpful, M from about 0.6 to 0.9 | about 50 to 70 percent |
| Neutral | under 1 percent |

Decision: if every criterion is met, squash-merge into `main`. Otherwise, merge
only the tooling and this record, with the skill text unchanged.

## Budget and Time

- Cap: 40 USD, enforced by `/home/user/hygiene-evals/delegation/ledger.jsonl`.
- Estimated spend:

  | Item | Cost (USD) |
  | --- | --- |
  | Probe | 0.35 |
  | Calibration | 2.2 |
  | Loop | about 11; stops at a ledger total of 16 |
  | Final comparison | about 18 |
  | Reviews | about 2 |
- The fallback rule under Acceptance Criteria keeps the worst case below the
  cap.
- Times (UTC):
  - loop ends by 06:00;
  - final comparison graded by 06:45;
  - decision by 07:15.
- Missing a time or the cap means stop, record, and do not change the skill.

## Review Log

| ID | Review | Severity | Finding | Disposition |
| --- | --- | --- | --- | --- |
| R1-1 | R1 | blocking | Ceiling: the probe scores M = 1.0, and the prompt line pushed both arms toward review. | Neutral prompt line; stop threshold 0.85 to match AC1 +0.15; a "no room" result is accepted as an outcome. No extra probe; calibration is the measurement. |
| R1-2 | R1 | major | B2/B3 patterns were both too loose and too strict; the loop can learn keywords. | Patterns tightened and tested on R1's examples; a hidden pattern set, hashed in the JSON, must also show the AC1 gain. |
| R1-3 | R1 | major | M mixed in the delegation rate; a later read-only review hid a re-check. | M over delegating sessions only; re-verified is measured after the last subagent file change. |
| R1-4 | R1 | major | Built-in agents bypass the brief check. | Any subagent that changes a file counts as an implementer; built-in and background agents are counted. |
| R1-5 | R1 | major | AC1 +0.25 and AC4 at 19 of 20 made a helpful change fail too often. | AC1 is +0.15; the absolute AC4 floor is dropped. |
| R1-6 | R1 | major | The one-round fallback was undefined. | Thresholds listed in `final.fallback`. |
| R1-7 | R1 | major | The worst-case budget equaled the cap. | Loop stops at 16 USD; the fallback rule uses projected cost. |
| R1-8 | R1 | minor | The judge could not tell parent from subagent calls; clipping dropped the end. | Labeled action log; clipping keeps start and end. |
| R1-9 | R1 | minor | Parallel arms and caching could confound. | Arms run together with the same concurrency; models used are recorded per row. |
| R1-10 | R1 | minor | Missing carry-overs: agents in the fingerprint, retries, the mirror step. | All three added. |
| R1-11 | R1 | minor | The 0.1 keep bar was below one twelfth plus noise; no start deadline. | Keep bar 0.17; calibration must start by 05:00 UTC. |

## Results

Pending.
