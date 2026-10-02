# Spec: Code Hygiene Report Brevity

Status: stopped after the loop; not merged. The owner chose to skip the final
comparison (see Results). Owner: maintainers.
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
percent in v2. The progress checklist is pasted into most final messages: Haiku
8 or 9 of 10, Opus 6 of 10.

The goal is shorter reports with the same quality and the same required
content. The value is readability; report tokens are about 1 to 2 percent of
session cost.

v1 showed the risk: report wording changes what the blind judge sees. The judge
partly rewards reports that leave out uncomfortable facts, such as "no failing
test was run first". So this spec does not rely on judge scores alone. It
checks the required content of every final message with frozen patterns.

## Scope of Change

The loop may edit only two regions of `code-hygiene/SKILL.md`, defined in the
JSON (`editable_regions`):

- the `### 6. Report` section, from that heading up to `## Tool And Access
  Limits`;
- the checklist sentence after "Follow this loop on every code task." That
  sentence is now frozen as LB40, and the region runs up to the
  `Hygiene progress:` block.

The rest of the normalized body must stay byte-identical.

Frozen rules:

- All v2 frozen sentences stay verbatim, except LB10 (the report list) and LB23
  (the evidence summary sentence). That includes the review sentences in the
  Report section: LB11, LB28, LB31, and LB39 ("If no issues are found…").
- LB40 is "Follow this loop on every code task."

Anchors (`anchors` in the JSON):

- Matching is a case-insensitive substring search inside the region, after
  removing every frozen sentence, so a protected sentence cannot satisfy an
  anchor.
- The Report section must still ask for:
  - the feedback loop (RA1);
  - commands with results (RA2);
  - checks not run (RA3);
  - residual risk (RA4);
  - assumptions (RA5).
- The lead-in must still mention the checklist (LA1).
- The conditional fields (Change, Correctness, Security/Data, Minimal Diff) may
  be condensed or dropped.
- At most 15 words absent from the current text may be added; the guard lists
  them.

## Metrics

- **Report length:** characters of the session's final message. A session with
  no final message is a failed session, not a short report.
- **Total text:** characters of all assistant text in the session, the final
  message included. This catches content moved into earlier messages.
- **Report content:** four frozen, case-insensitive patterns
  (`report_content`) tested on each final message:

  | Item | Content |
  | --- | --- |
  | C1 | Feedback loop or reproduction |
  | C2 | Command or test count with a result |
  | C3 | Checks not run or skipped |
  | C4 | Risk, limitation, or assumption |

  On the 80 v2 final messages the rates were stable between the two arms of the
  same report format:

  | Model | C1 | C2 | C3 | C4 |
  | --- | --- | --- | --- | --- |
  | Haiku | 10/10 | 10/10 | 0–1/10 | 6–7/10 |
  | Sonnet | 13–14/20 | 19/20 | 8–9/20 | 11–13/20 |
  | Opus | 9–10/10 | 10/10 | 1–4/10 | 5–8/10 |

- **Quality:** PASS-100 total from the blind Opus judge, and the
  documentation-plus-process sum (`documentation` 0 to 5 plus `agent_process` 0
  to 5).
- **Capped:** sessions with a total of 72 or less. This is a diagnostic only:
  for a wording change it moves with how honest the report is, not with quality.
- **Other:** resolved and strict reproduced first as defined in the v2 spec; cost.
- **Pooled figures:** the mean of the per-model means.

## Guard

`measure` is the loop's Verify command:

- It runs Haiku and Sonnet on the six train fixtures, one round (12 sessions),
  with the candidate staged and invoked explicitly.
- The blind judge grades each session. It grades one session first, so the
  rubric is cached before the parallel calls.
- The run is cached by the text's hash, and the command prints the pooled report
  length.

`guard --measured` reads that run and checks the following.

Static checks:

- frontmatter hash unchanged;
- only `code-hygiene/SKILL.md` changed;
- no change outside the editable regions;
- frozen sentences and anchors present;
- at most 15 new words.

Behavioral checks, against the calibration run of the current text:

| Check | Pass condition |
| --- | --- |
| Mean PASS-100 | At least the base minus 4 |
| Mean documentation-plus-process | At least the base minus 1 |
| Each report-content item | Count at least the base minus 3 (of 12) |
| Pooled total-text ratio | At most 1.10 |
| Unresolved sessions | At most 1 |
| Strict reproduced first | At least 4 of 12 |

Calibration base: score 86.2; documentation-plus-process 7.96; content C1 8,
C2 12, C3 4, C4 7; total text 1,707 characters; report 1,196 characters.

An unchanged text fails at least one check about 20 percent of the time per
step, mostly from the score check. The guard stops gross regressions. Smaller
losses are left to the final comparison, which has more power.

## Loop Rules

- The autoresearch classic loop runs on Opus with a driver budget of 1.50 USD,
  starting from tag `report-brevity-base`, which holds the current text.
- Metric: report length, direction lower. The driver keeps a change only if it
  improves the metric by at least 10 percent. One measure of 12 sessions varies
  by about 8 percent, so smaller gains are noise.
- One change per iteration. The driver is told what makes reports long:
  - the eight-field list;
  - pasting the checklist into the final message;
  - restating fields that do not apply.
- The loop stops at the first of these:
  - pooled report length 40 percent below calibration;
  - 3 iterations;
  - 2 consecutive static rejections;
  - 3 consecutive behavioral rejections;
  - ledger above 12 USD;
  - 22:45 UTC.
- A fresh reviewer reads the kept diff and its new words before the final
  comparison. A blocking finding there stops the effort.
- There is no separate confirmation run; the final comparison is the
  confirmation.
- Opus is not measured in the loop. Its reports are the longest, so AC1's
  per-model limit is the main risk.

## Acceptance Criteria and Decision

Final comparison:

- Two arms: the current text (base, `37c920d`) and the candidate. Both are
  invoked explicitly from staged copies, with at most 40 turns and one retry for
  broken sessions.
- All ten fixtures: Haiku once, Sonnet twice, Opus once. That gives 40 pairs and
  80 sessions.
- The arms run concurrently and are graded by the blind Opus judge, with one
  retry for a reply that breaks the cap rule.

| AC | Criterion | `compare` key |
| --- | --- | --- |
| AC1 | Pooled report-length ratio at most 0.70 and at most 0.85 for every model; pooled total-text ratio at most 0.90. | `report_length` |
| AC2 | Pooled PASS-100 difference at least -1.5; every per-model difference at least -4; lower bound of the stratified 90 percent bootstrap at least -4.5; holdout pooled difference at least -3. | `AC3`, `AC4` |
| AC3 | Pooled documentation-plus-process difference at least -0.5; every report-content item at least the original's count minus 5 (of 40). | `doc_process`, `report_content` |
| AC4 | Resolved at least the original's minus 1; strict reproduced first at least the original's minus 5 pooled and minus 4 for Sonnet (of 20); pooled cost ratio at most 1.05. | `AC5`, `AC6`, `AC2` |
| AC5 | Full unit suite, `validate_package.py`, mirror byte equality, matching init fingerprints, and CI on Ubuntu, Windows, and macOS pass. | — |
| AC6 | Final independent review R2 has no open blocking finding. R2 reads at least 10 report pairs. Blocking findings are fixed and confirmed. | — |

Capped counts are reported as a diagnostic.

Decision: if every criterion is met, squash-merge into `main`. Otherwise do not
merge and record the result here.

Error rates for a change that is neutral on quality, from R1's estimates
(paired SDs Haiku about 9, Sonnet about 12, Opus about 2):

| Criterion | Chance a neutral change fails it |
| --- | --- |
| AC2 | about 21% |
| AC3 | about 8% |
| AC4 | about 8% |
| Any of these | about 35% |

Two more limits:

- AC1 fails about 10 percent of the time at a true ratio of 0.65, and about half
  the time at 0.70.
- The design accepts these and prefers a false no-merge to a false merge.

## Budget, Time, and Stop Rules

- Cap: 30 USD, enforced by a separate ledger
  (`/home/user/hygiene-evals/brevity/ledger.jsonl`).
- Spend:

  | Item | Cost |
  | --- | --- |
  | Calibration | 3.52 USD (actual) |
  | Loop | about 2 USD per step, up to 3 steps, plus a driver of at most 1.50 USD |
  | Final comparison (80 sessions plus judge) | about 16 USD |

  Loop measures stop at a ledger total of 12 USD.
- Times (UTC):
  - loop ends by 22:45;
  - final comparison graded by 23:15;
  - R2, docs, CI, and the decision by 23:45.
- Missing a time or the cap means stop, record results, and do not merge.

## Review Log

| ID | Review | Severity | Finding | Disposition |
| --- | --- | --- | --- | --- |
| B-1 | Calibration | minor | Calibration cost 3.52 USD: parallel judge calls each wrote the rubric to the prompt cache. | `grade_all` grades one session first; budget stops tightened. No quality threshold changed. |
| R1-1 | R1 | blocking | Required content was protected only in the skill text; anchors could be hollowed (RA4 always matched LB39); the judge rewards omissions. | Fixed. Frozen content patterns on the final messages are checked in the guard (base minus 3 of 12) and in AC3 (original minus 5 of 40). Anchors ignore frozen sentences. A fresh reviewer reads the kept diff before the final comparison. |
| R1-2 | R1 | major | Report length can be gamed by moving content into earlier messages. | Fixed: total text is in the guard (ratio at most 1.10) and in AC1 (at most 0.90). A session with no final message is a failure. |
| R1-3 | R1 | major | The guard's false-rejection rate was understated, mostly from the cap check. | Cap check removed (see R1-5); the combined rate, about 20 percent per step, is stated. |
| R1-4 | R1 | major | AC2's neutral failure rate was about 29 to 38 percent with one Sonnet round. | Fixed: Sonnet runs twice (about 21 percent). Funded by dropping the separate confirmation run and capping the loop at 3 iterations. |
| R1-5 | R1 | major | Cap criteria push the wrong way for a wording change. | Caps are diagnostic only. Strict reproduced first is the process criterion. |
| R1-6 | R1 | major | The confirmation run was undefined. | Dropped; the final comparison is the confirmation, and a failure there means no merge. |
| R1-7 | R1 | major | The lead-in region held an unprotected process rule. | Fixed: LB40 is frozen, and the region holds only the checklist sentence, which must still mention the checklist (LA1). |
| R1-8 | R1 | minor | The budget was tight. | Fixed: at most 3 iterations, ledger stop 12 USD, and spend stated. |
| R1-9 | R1 | minor | The Sonnet reproduced-first rule was nearly pointless with one round. | With two Sonnet rounds it is minus 4 of 20; pooled minus 5 of 40. |
| R1-10 | R1 | minor | "Capped" was imprecise. | Defined as a total of 72 or less; diagnostic only. |
| R1-11 | R1 | minor | Anchor matching rules were unstated, and RA2 was too loose. | Matching rules stated; RA2 now requires "command" and "result". |
| R1-12 | R1 | minor | Opus is unmeasured in the loop, and noise lets non-improving steps be kept. | Opus risk stated; a step needs at least a 10 percent gain to be kept. |
| R1-13 | R1 | minor | `compare` criteria names did not match the spec's ACs, and size flags could crash it. | Mapping given in the AC table; `compare` skips the size criterion when the spec has none. |

## Results

Decision: **stopped after the loop, not merged**. `code-hygiene/SKILL.md` is
unchanged; the candidate existed only in the loop worktree. The final comparison
was skipped. In the loop, Sonnet's reports did not get shorter, so AC1's
per-model rule (at most 0.85 for every model) would almost certainly have
failed. The owner chose to save its cost (about 16 USD) rather than confirm a
likely failure.

### Loop

Each measure ran 12 sessions (Haiku and Sonnet on the six train fixtures),
judged blind. Every guard passed, and every session resolved its fixture.

| Run | Report (pooled) | Haiku report, score | Sonnet report, score | Score | Doc+process | Total text | Content C1/C2/C3/C4 | Reproduced first | Status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Calibration (current text) | 1,196 | 1,455, 84.2 | 936, 88.1 | 86.2 | 7.96 | 1,707 | 8/12/4/7 | 6 | base |
| 1: one-sentence report request | 965 (-19%) | 1,012, 93.3 | 917, 85.7 | 89.5 | 8.42 | 1,484 | 9/11/3/5 | 6 | kept |
| 2: keep the checklist out of the final report | 933 (-3% vs kept) | 969, 93.8 | 897, 85.8 | 89.8 | 8.25 | 1,333 | 7/12/3/5 | 8 | discarded (below the 10 percent bar) |
| 3: at most six short lines | 968 (no gain) | 898, 86.9 | 1,038, 83.6 | 85.2 | 7.75 | 1,444 | 12/12/7/9 | 4 | discarded |

The kept change replaced the eight-field list and the summary sentence in the
Report section with: "For implementation work, report in a few short lines: what
changed, the feedback loop used, exact commands/checks run and their results,
checks not run and why, assumptions, and residual risk."

### Findings

- **Sonnet's reports are already short.** They ran 900 to 1,040 characters
  whatever the instructions said, so a per-model target of 15 percent is
  infeasible for Sonnet. Haiku, and probably Opus, write the long reports.
  Haiku fell 30 percent with the kept change.
- **The required-content checks held.** No item fell more than 2 below the base,
  and total assistant text fell with the report, so content was cut rather than
  moved. Judge scores did not drop; Haiku rose. With 6 sessions per model these
  are indications only.
- **No help from extra rules.** Telling agents not to paste the checklist, or
  capping reports at six lines, added nothing beyond the one-sentence request.
- **Next attempt:**
  - target Haiku and Opus;
  - measure Opus in the loop;
  - set per-model goals only where reports are long;
  - keep the content and total-text checks.

### Spend and time

| Item | Cost |
| --- | --- |
| Calibration | 3.52 USD |
| Three loop measures | 5.45 USD |
| Driver | 0.69 USD |
| Total | 9.67 USD of the 30 USD cap |

The run went from 21:26 to 21:51 UTC. The tooling built for this effort stays:
`measure`, `guard --measured`, the region and anchor checks, report-content and
total-text checks, judge cache warm-up, and the new `compare` criteria.
