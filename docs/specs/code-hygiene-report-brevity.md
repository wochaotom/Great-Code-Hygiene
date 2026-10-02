# Spec: Code Hygiene Report Brevity

Status: draft for review R1; thresholds frozen before any data. Owner:
maintainers.
Machine-readable thresholds:
[`code-hygiene-report-brevity.json`](code-hygiene-report-brevity.json). Earlier
efforts on the same skill: [`code-hygiene-token-diet.md`](code-hygiene-token-diet.md)
(v1) and [`code-hygiene-token-diet-v2.md`](code-hygiene-token-diet-v2.md) (v2,
merged).

## Contents

- Why
- Scope of Change
- Metrics
- Guard
- Loop Rules
- Acceptance Criteria and Decision
- Budget, Time, and Stop Rules
- Review Log
- Results

## Why

With `code-hygiene` invoked, final reports average:

| Model | Characters |
| --- | --- |
| Haiku | 1,539 |
| Sonnet | 1,300 |
| Opus | 2,136 |

These are from the v2 final comparison of the current text. Reports grew 11
percent in v2, and Opus copied the progress checklist into 6 of 10 final
messages.

The goal is shorter reports with the same quality. The value is readability;
output tokens for the report are only about 1 to 2 percent of session cost.

v1 showed the risk: report wording changes what the blind judge sees. A more
prominent Feedback Loop field raised the number of sessions capped at 72. So
every loop step is checked by the judge, not only the final candidate.

## Scope of Change

The loop may edit only two regions of `code-hygiene/SKILL.md`, defined in the
JSON (`editable_regions`):

- the `### 6. Report` section, from that heading up to `## Tool And Access
  Limits`;
- the checklist lead-in sentence between `## Hygiene Workflow` and the
  `Hygiene progress:` block.

The rest of the normalized body must stay byte-identical.

Frozen rules and anchors:

- All v2 frozen sentences stay verbatim, except LB10 (the report list) and LB23
  ("Report evidence, skipped checks, assumptions, and residual risk.").
- The review sentences inside the Report section (LB11, LB28, LB31) stay frozen,
  and LB39 now freezes "If no issues are found, say so and name any test gaps or
  residual risk."
- LB10 and LB23 become phrase anchors that must still appear inside the Report
  region, so every implementation report keeps its required content:

  | Anchor | Content | Required phrases |
  | --- | --- | --- |
  | RA1 | Feedback loop | "feedback loop" |
  | RA2 | Commands or checks with results | "command" or "check", and "result" |
  | RA3 | Checks not run | "unrun" or "not run" |
  | RA4 | Residual risk | "residual risk" |
  | RA5 | Assumptions | "assumption" |

- The conditional fields (Change, Correctness, Security/Data, Minimal Diff) may
  be condensed or dropped.
- At most 15 words absent from the current text may be added; the guard lists
  them for the reviewer.

## Metrics

- **Report length:** characters of the session's final message (`result` in the
  stream). Pooled figures are the mean of the per-model means.
- **Quality:** PASS-100 total from the blind Opus judge.
- **Documentation and process:** the sum of the `documentation` (0 to 5) and
  `agent_process` (0 to 5) categories.
- **Capped:** sessions with a total of 72 or less (any cap).
- **Resolved:** the fixture is fixed and its protected files are untouched.
- **Strict reproduced first:** as defined in the v2 spec.
- **Cost:** reported session cost.

## Guard

`measure` is the loop's Verify command:

- It runs Haiku and Sonnet on the six train fixtures, one round (12 sessions),
  with the candidate staged and invoked explicitly.
- The blind judge grades each session.
- The run is cached by the text's hash, and the command prints the pooled
  report length.

`guard --measured` reads that run, so the sessions are not repeated, and checks
the following.

Static checks:

- frontmatter hash unchanged;
- only `code-hygiene/SKILL.md` changed;
- no change outside the editable regions;
- frozen sentences and report anchors present;
- at most 15 new words.

Behavioral checks, against the calibration run of the current text:

| Check | Pass condition |
| --- | --- |
| Mean PASS-100 | At least the base minus 4 |
| Capped sessions | At most the base plus 1 |
| Mean documentation-plus-process | At least the base minus 1 |
| Unresolved sessions | At most 1 |
| Strict reproduced first | At least 4 of 12 |

With a per-session score SD of about 8, the score check falsely rejects an
unchanged text about 11 percent of the time.

## Loop Rules

- The autoresearch classic loop runs on Opus with a driver budget of 2 USD,
  starting from tag `report-brevity-base`, which holds the current text.
- Metric: report length, direction lower.
- One change per iteration, inside the editable regions only. The driver is
  told what makes reports long:
  - the eight-field list;
  - copying the checklist into the final message;
  - restating fields that do not apply.
- The loop stops at the first of these:
  - a pooled report length 40 percent below calibration;
  - 5 iterations;
  - 2 consecutive static rejections;
  - 3 consecutive behavioral rejections;
  - ledger above 16 USD;
  - 22:45 UTC.

## Acceptance Criteria and Decision

Final comparison:

- Two arms: the current text (base, `37c920d`) and the candidate. Both are
  invoked explicitly from staged copies, with at most 40 turns and one retry for
  broken sessions.
- All ten fixtures on Haiku, Sonnet, and Opus, one round each: 30 pairs and 60
  sessions.
- The arms run concurrently and are graded by the blind Opus judge, with one
  retry for a reply that breaks the cap rule.

| AC | Criterion |
| --- | --- |
| AC1 | Pooled report-length ratio (candidate over original) at most 0.70, and at most 0.85 for every model. |
| AC2 | Pooled PASS-100 difference at least -1.5; every per-model difference at least -4; lower bound of the stratified 90 percent bootstrap at least -4.5; holdout pooled difference at least -3. |
| AC3 | Pooled documentation-plus-process difference at least -0.5; capped sessions at most the original's plus 2 (of 30). |
| AC4 | Resolved at least the original's minus 1; strict reproduced first at least the original's minus 3, pooled, and the same for Sonnet; pooled cost ratio at most 1.05. |
| AC5 | Full unit suite, `validate_package.py`, mirror byte equality, matching init fingerprints, and CI on Ubuntu, Windows, and macOS pass. |
| AC6 | Final independent review R2 has no open blocking finding. R2 reads sample reports from both arms and confirms the required content is still present. Blocking findings are fixed and confirmed. |

Decision: if every criterion is met, squash-merge into `main`. Otherwise do not
merge and record the result here.

Error rates for a change that is neutral on quality:

| Criterion | Chance a neutral change fails it |
| --- | --- |
| AC2 | about 16% |
| AC3 | about 12% |
| AC4 | about 12% |
| Any of these | about 35% |

The design accepts that and prefers a false no-merge to a false merge.

## Budget, Time, and Stop Rules

- Cap: 30 USD, enforced by a separate ledger
  (`/home/user/hygiene-evals/brevity/ledger.jsonl`).
- Planned spend:

  | Item | Estimate |
  | --- | --- |
  | Calibration | about 2 USD |
  | Loop | about 1.9 USD per step plus a driver of at most 2 USD |
  | Confirmation | about 2 USD |
  | Final comparison (60 sessions plus judge) | about 11 USD |

  Loop guards stop at a ledger total of 16 USD, which reserves the final
  comparison and confirmation.
- Times (UTC):
  - loop ends by 22:45;
  - final comparison graded by 23:15;
  - R2, docs, CI, and the decision by 23:45.
- Missing a time or the cap means stop, record results, and do not merge.

## Review Log

| ID | Review | Severity | Finding | Disposition |
| --- | --- | --- | --- | --- |

## Results

To be completed after the final comparison.
