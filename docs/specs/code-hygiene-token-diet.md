# Spec: Code Hygiene Token Diet

Status: complete, not merged (AC2 and AC3 not met); thresholds were frozen
before any loop or final data. Owner: maintainers.
Machine-readable thresholds: [`code-hygiene-token-diet.json`](code-hygiene-token-diet.json).

## Contents

- Context and Baseline
- Goals and Non-Goals
- Metrics
- Load-Bearing Rules
- Fixture Split
- Change M1: Report Scaling
- Loop Rules and Guard
- Acceptance Criteria and Decision
- Budget and Stop Rules
- Review Log
- Results

## Context and Baseline

The 2026-10-02 PASS-100 comparison in `docs/power-users.md` showed that
`code-hygiene` raises blind-judged quality on Haiku (82.1 to 90.7) and Opus
(90.3 to 94.3) but not Sonnet (83.1 to 82.7), and raises cost per session by
29 to 61 percent. Every one of the 60 sessions was resolved. Session logs
attribute the extra cost to three sources:

- more turns and test runs, which carry the quality gain;
- the skill text itself (9,070 normalized body bytes, about 4,300 extra
  cache-write tokens per session), which repeats the hygiene loop three times;
- final reports about 1.8 times longer, because the 8-field evidence report is
  required even for two-line fixes.

Expected savings are modest. At list prices, the skill text costs roughly 8 to
16 percent of an invoked session. Cutting 30 percent of it, plus M1, should save
about 5 to 7 percent of session cost. Larger savings would most likely come from
less work. The criteria below therefore pair a cost target with a floor on test
runs.

Mechanical signal used throughout: a session "reproduced first" when a test ran
before the first file change (defined under Metrics). Baseline across all ten
fixtures, measured by `tools/claude_model_check.py metrics` on the stored logs:

- without the skill: 1/10 for every model;
- with it: Haiku 8/10, Sonnet 5/10, Opus 9/10;
- with it, on the six train fixtures: Haiku 5/6, Sonnet 3/6.

Runs that reproduced first averaged 89.3 PASS-100 points; the rest averaged
85.6.

## Goals and Non-Goals

Goals: cut the skill's fixed and reporting overhead while keeping measured
effectiveness. Specifically:

- at least 25 percent fewer normalized body bytes;
- lower cost per session (target 10 percent; acceptance at 5 percent), without
  fewer test runs;
- no meaningful quality loss.

Non-goals:

- No change to the `code-hygiene` frontmatter. The description holds the
  measured trigger wording and stays byte-identical.
- No change to the trainer edition, fixtures, PASS-100 rubric, judge, task
  prompts, Cursor rule, chatbot profiles, or portable prompt.
- Improving Sonnet's reproduce-first rate is a separate effort; this one must
  only not make it worse (AC6).
- Results here are diagnostic model-execution evidence for the clean edition.
  They are not trainer promotion evidence under `compound-loop.md`.

## Metrics

- **Size:** take the text after the line that closes the frontmatter, collapse
  every whitespace run to one space, strip both ends, and count the UTF-8 bytes.
  The result is deterministic and the same on every OS, so reflowing text cannot
  move it. The `code-hygiene/` folder may hold only `SKILL.md`
  (`validate_package.py`), so no text can move to another file.
- **Frontmatter hash:** SHA-256 of the UTF-8 bytes from the start of the file
  through the closing `---` line and its newline.
- **Cost:** for each session, `total_cost_usd`, the token usage (input, cache
  write, cache read, output), and the length of the final report.
  - A cost ratio is the ratio of pooled means: the sum over the candidate's
    sessions divided by the sum over the original's.
- **Test runs:** the number of test commands in a session.
- **Reproduced first:** a tool call that ran a test command came before the
  first tool call that changed a file inside the target.
  - A call that runs a test and changes a file does not count, because the code
    changed before the agent saw the result.
  - A test command is a shell segment whose first word is `pytest`, or that
    starts with `npm test`, `node --test` or `<python> -m pytest|unittest`.
    Leading variable assignments and `cd` are skipped.
  - A segment is split on `&&`, `||`, `;`, `|` and newlines.
  - File changes are Edit, Write and NotebookEdit calls on paths inside the
    target. Shell file changes are:
    - segments starting with `sed -i`, `perl -i`, `cp`, `mv`, `rm`, `patch`,
      `git apply`, `git checkout` or `tee`;
    - any `>` or `>>` redirection to a file path that is not `/dev/null`,
      descriptor duplication such as `2>&1` excluded;
    - inline script writes (`.write(`, `.write_text(`, `writeFileSync(`,
      `shutil.copy` or `shutil.move` anywhere in the command), since agents
      often patch files with `python - <<EOF`.
- **Quality:** PASS-100 total from the blind Opus judge in
  `tools/claude_model_check.py grade`.
  - Each session is judged on its own, never side by side.
  - Report shape may hint at the arm. The judge never sees arm names and grades
    against the rubric only.
- **Resolved:** fixture fixed and protected files untouched (`fixture_runner`).

## Load-Bearing Rules

These rules must survive every change. Each one is frozen as one or more
verbatim sentences in the JSON `load_bearing` map.
`tests/test_code_hygiene_core_rules.py` checks that every sentence appears
unchanged in the normalized body. It also proves, by a deletion self-test, that
removing a sentence fails exactly its rule. Duplicated copies elsewhere may be
cut; the frozen sentence, with its qualifiers, may not. Wording may change only
if the JSON and the test change in the same reviewed commit, as M1 does for
LB10.

| ID | Rule |
| --- | --- |
| LB1 | Build the smallest deterministic feedback loop before fixing, or state why none is possible. |
| LB2 | If a check fails, return to Constrain, fix the cause, and re-run it. |
| LB3 | The copyable `Hygiene progress:` checklist. |
| LB4 | Never revert unrelated user work. |
| LB5 | No completion, passing, or readiness claim without fresh tool output or a named blocker. |
| LB6 | Make the smallest behavior-correct change; avoid rewrites and churn. |
| LB7 | Check edge cases, validation, authorization, secrets, path handling, and injection when relevant. |
| LB8 | For config or precedence changes, test the winning source and a fallback. |
| LB9 | Add or update tests when behavior changes or a bug can regress. |
| LB10 | The report states the feedback loop used, checks run with results, checks not run, and residual risk; after M1, for every implementation report. |
| LB11 | Reviews lead with findings ordered by severity and distinguish confirmed bugs from plausible risks. |
| LB12 | Before recursive deletion or moves, prove the path stays inside the intended directory. |
| LB13 | Never invent command output, file contents, or test results. |
| LB14 | Edition boundary: no training, scoring, or self-mutation; route those to `code-hygiene-compounder`. |
| LB15 | Error paths stay observable; no silent failures. |
| LB16 | Preserve public contracts, migrations, data formats, and config precedence unless asked. |
| LB17 | Run broader checks for shared modules, public APIs, security-sensitive paths, config, and migrations. |
| LB18 | Add regression checks for the vulnerable path and at least one safe control. |
| LB19 | Do not patch symptoms from inspection alone when a loop is feasible. |
| LB20 | Check error handling, retries, timeouts, migration rollback, and compatibility when relevant. |
| LB21 | Scope status, diff, and discovery commands to an explicitly bounded target. |

The frozen sentences total 3,143 of 9,070 normalized bytes (35 percent).

## Fixture Split

Fixed before any loop data.

- Train (guard only): `hyg-006-currency-rounding`,
  `hyg-019-migration-forward-rollback`, `hyg-031-sql-injection`,
  `hyg-051-preserve-user-edits`, `hyg-062-js-retry-bounds`,
  `hyg-083-config-precedence`.
- Holdout (final evaluation only): `hyg-032-path-traversal`,
  `hyg-034-resource-authorization`, `hyg-064-secret-safe-logs`,
  `hyg-096-source-audit-http-domain`.

## Change M1: Report Scaling

Applied by hand before the loop, test first.

- Every implementation report states four fields: the feedback loop used, checks
  run with results, checks not run, and residual risk.
- Some changes also report Change, Correctness, Security/Data, and Minimal Diff:
  - changes touching security, config, persisted data or migrations;
  - changes to more than one source file.
- The four field sentences stay verbatim.
- M1 is a behavior change. The guard checks it before the loop, and the final
  comparison reports its effect together with the loop result. Savings are not
  attributed to the loop alone.

## Loop Rules and Guard

Loop engineering uses the autoresearch classic loop
(`/autoresearch:autoresearch`) with metric = size, direction = lower.

- Only `code-hygiene/SKILL.md` changes; the mirrors are synced after the loop.
- Each kept step removes or condenses text, saves at least 32 normalized bytes
  (the repository's own size-promotion rule), and adds no rules, examples, or
  fixture hints.
- Guard sessions invoke the skill explicitly from a staged copy of the candidate,
  with at most 40 turns.
- Guard, cheapest checks first:
  1. Static checks, at no model cost:
     - the frontmatter hash is unchanged;
     - no other file changed against the loop base;
     - the step saves at least 32 bytes against `HEAD~1`; this check is skipped
       while the text still equals the base;
     - the core-rule tests pass;
     - the candidate uses at most 5 lowercase words that are absent from both
       the original and the base. Such words are listed in the output so a
       reviewer sees any new vocabulary, abbreviations, or hints.
  2. Behavioral: Haiku and Sonnet on the six train fixtures, one round
     (12 sessions, about 1.10 USD), scored on resolved sessions and the
     reproduced-first count:
     - Reject when 2 or more sessions are unresolved.
     - Pass when the reproduced-first count is 7 or more.
     - Fail when it is 5 or less.
     - At exactly 6, run a second stage of 12 more sessions. Pass when the total
       is at least 14 of 24 and at most 1 more session is unresolved.
     - A session that ends in an infrastructure error is retried once.
- Error rates, from the binomial model with train rates Haiku 5/6 and Sonnet
  3/6:

  | Candidate | Chance of passing |
  | --- | --- |
  | Unchanged skill | 91% |
  | Reproduced-first down 2 of 12 | 42% |
  | Reproduced-first down 3 of 12 | 19% |
  | Rates halved | 6% |

  The expected cost is 1.11 single runs. The baseline resolved 12/12 on train.
  At a 2 percent unresolved rate per session, the unresolved rule rejects an
  unchanged skill about 2 percent of the time.
- Calibration: the original skill and the M1 base must each pass the guard
  before the loop. Results are cached by the text's hash, so the loop's
  iteration-0 guard reuses the M1 result. A pre-loop failure stops the effort
  with no loop and no merge.
- After the loop, one fresh (uncached) confirmation guard runs on the final text.
  On failure, step back one kept change and confirm once more. If that also
  fails, the result is a no-merge.

## Acceptance Criteria and Decision

Final comparison:

- Two arms: the original skill (from `main` before this effort) and the
  candidate. Both are invoked explicitly from staged copies.
- All ten fixtures on Haiku, Sonnet, and Opus, with at most 40 turns and one
  round per arm, giving 30 paired sessions.
- The arms run concurrently and are graded by the blind Opus judge.

Thresholds are fixed now and never changed after data is seen.

| AC | Criterion |
| --- | --- |
| AC1 | Normalized body bytes down at least 25 percent; frontmatter byte-identical; `code-hygiene/` still holds only `SKILL.md`. |
| AC2 | Pooled cost ratio, candidate over original, at most 0.95; pooled test-run ratio at least 0.80. Report cost by component (cache write, cache read, output, turns). |
| AC3 | Pooled mean PASS-100 difference (candidate minus original) at least -1.5; every per-model difference at least -4; lower bound of the two-sided 90 percent paired bootstrap interval at least -4.5. The bootstrap resamples pairs within each model, keeping 10 per model; seed 20261002, 10,000 resamples, percentile method. |
| AC4 | Holdout pooled difference (12 pairs) at least -3. |
| AC5 | Candidate resolved count at least the original's minus 1 (of 30). |
| AC6 | Candidate reproduced-first count at least the original's minus 3 (of 30) pooled, and Sonnet's at least the original's minus 2 (of 10). |
| AC7 | Full unit suite, `validate_package.py --doctor`, mirror byte equality, and CI on Ubuntu, Windows, and macOS pass. |
| AC8 | Final independent review R2 has no open blocking finding. Blocking findings are fixed and confirmed by a fresh reviewer; a disposition alone does not close them. |

Decision: all criteria met, then squash-merge into `main`. Otherwise do not
merge; record the result here.

Limits stated up front:

- With ten pairs per model these criteria detect meaningful regressions; they do
  not prove equivalence.
- Assume a per-pair score SD of about 7 and a true cost ratio of about 0.94. A
  change that is neutral on quality then still fails some criterion about half
  the time:
  - AC3 about 20 percent;
  - AC4 about 7 percent;
  - AC6 about 15 percent;
  - AC2 about 40 percent.
- The budget allows one final round, so this risk is accepted. The design
  prefers a false no-merge to a false merge.
- The per-model limit of -4 is the resolution ten pairs allow. It cannot certify
  that Sonnet stays above its no-skill score.

## Budget and Stop Rules

- Model spend cap: 50 USD of reported session cost.
  - The ledger in `tools/claude_model_check.py` (`--ledger`, `--budget-usd`)
    enforces it. That ledger counts guard, comparison, and judge sessions.
  - The loop driver is capped by `--max-budget-usd`, and its cost is added to the
    ledger.
- Planned spend:

  | Item | Estimate |
  | --- | --- |
  | Calibration (two guards) | about 2.5 USD |
  | Loop guards | about 10 USD |
  | Loop driver | at most 8 USD |
  | Confirmation and step-back | at most 5 USD |
  | Final comparison | about 8 USD sessions plus at most 14 USD judge |

  The final comparison and confirmation together have an upper bound of about
  28 USD.
- Wall-clock cap: about four hours from 09:09 UTC. On reaching either cap, stop,
  record results, and do not merge.
- The loop stops at the first of these:
  - size at least 30 percent below the original;
  - 8 iterations;
  - 2 consecutive static rejections for the same reason;
  - 3 consecutive behavioral rejections;
  - ledger spend above 22 USD, which reserves the 28 USD upper bound;
  - 11:40 UTC, which leaves 90 minutes for the final comparison, R2, docs, and
    three-OS CI.

## Review Log

| ID | Review | Severity | Finding | Disposition |
| --- | --- | --- | --- | --- |
| R1-1 | R1 | blocking | `max(4, min(live, 7) - 3)` is always 4; a halved skill passes 60 to 80 percent of the time. | Fixed. Two-stage guard; thresholds as corrected in M-1. Unchanged passes 91 percent; halved 6 percent. |
| R1-2 | R1 | blocking | PASS-100-relevant rules unprotected. | Fixed: LB16 to LB21 added; edge cases joined LB7; confirmed-versus-plausible joined LB11. |
| R1-3 | R1 | major | LB10 "always" comes from M1 and omits the feedback loop; LB12 dropped "moves". | Fixed: LB10 names the loop field and the post-M1 scope; LB12 sentence includes moves. |
| R1-4 | R1 | major | Anchor phrases can be hollowed; added hints are unchecked. | Fixed: anchors are verbatim sentences with qualifiers; new-word static check; R2 reviews meaning on the full diff. A per-step model review is rejected on cost. |
| R1-5 | R1 | major | AC2 rewards less work; text cuts alone save little. | Fixed: expected savings stated; AC2 now 0.95 with a test-run floor of 0.80 and a component breakdown. |
| R1-6 | R1 | major | Per-model -4 lets Sonnet drop; non-goal unmapped. | Partly fixed: Sonnet reproduced-first floor added to AC6. A -2 Sonnet quality floor is rejected because it alone would fail a neutral change about 18 percent of the time; the limit is stated. |
| R1-7 | R1 | major | False-rejection rate ignores the unresolved limit. | Fixed: baseline 12/12 resolved on train stated; about 2 percent added rejection. |
| R1-8 | R1 | major | Combined neutral-change failure rate unstated. | Fixed: stated (about half) and accepted; one final round is all the budget allows. |
| R1-9 | R1 | major | Missing stops and reserves. | Fixed: target-size stop, behavioral-rejection stop, time reserve, upper-bound budget reserve, failed step-back means no merge. |
| R1-10 | R1 | minor | Ambiguous definitions. | Fixed in Metrics, Loop Rules, and AC3. |
| R1-11 | R1 | minor | Size trim and hash input undefined; bytes are not tokens. | Fixed: both defined, hash recomputed; token usage reported; new-word check limits abbreviations. |
| M-1 | Phase 2 | major | Implementing the metric showed two definition gaps. Script writes (`python - <<EOF`) went undetected, and a test plus a write in one call counted as reproducing. | Fixed before any loop data. The definition counts per call and detects script writes. The tool reproduces the earlier hand counts within 1 per cell, and the train baseline is 8/12. The guard thresholds move up by one under the same rule (pass at 7 or more, fail at 5 or less, second stage needs 14 of 24), keeping the R1-1 error rates. |
| M-2 | Post-loop | major | The implementer read the loop result before the confirmation guard. The Task Modes cut dropped three original sentences that no frozen sentence covers: safe framework APIs for hardening, characterization tests when behavior is unclear, and what a review finding names. | Restored verbatim before the confirmation guard, adding no new words. Size 6,272 to 6,540 bytes, 27.9 percent below the original. The confirmation guard and final comparison ran on this text. |
| R2-1 | R2 | major | The Sonnet diagnosis left out counter-evidence: two of three capped sessions matched the original's process; caps follow self-reported Feedback Loop text. | Fixed in Diagnosis; AC3 unchanged. |
| R2-2 | R2 | major | The zero-test metric limit was understated. | Fixed in Diagnosis with R2's stricter recount; AC6 holds either way. |
| R2-3 | R2 | major | M-2 listed only three dropped sentences; more were lost. | Fixed in Diagnosis ("Text lost beyond M-2"). |
| R2-4 | R2 | minor | AC7 evidence wording. | Fixed; CI is green on all three OSes. |
| R2-5 | R2 | minor | The aborted first grading's log was overwritten; judge ledger labels lack the arm name. | Accepted as a follow-up. Every judge cost is still in the ledger, and the total stays under the cap. |
| R2-6 | R2 | minor | The branch mixes the rejected skill change with reusable tooling and docs. | Left for the owner, since this effort does not merge. Landing only the tooling and results means reverting the three `SKILL.md` copies. |
| R2-7 | R2 | minor | Sessions inherited the parent Claude Code config; a broken line wrap in Purpose. | Both arms were equally affected. The wrap is left as evaluated, and normalized size is unaffected. A next attempt should use a clean `CLAUDE_CONFIG_DIR`. |
| R1-12 | R1 | minor | Text moved to new files; dispositions closing blockers; status; blinding. | Fixed: AC1 checks the folder; AC8 requires fixes; status updated; blinding limit stated in Metrics. |

## Results

Decision: **not merged**. AC2 and AC3 were not met. The thresholds were frozen
before any data, and the spec allows one final round, so the effort stops here.

### What changed on the branch

- M1 report scaling.
- Three autoresearch iterations, all kept:
  1. drop When To Use and a Purpose sentence that repeats Hard Stops;
  2. drop Task Modes;
  3. drop Quick Start.
- Three original sentences restored after the loop (M-2).
- Normalized body: 9,070 bytes to 6,540 (27.9 percent smaller), frontmatter
  byte-identical, every frozen sentence intact, no new words.

Guards, every session resolved:

| Run | Reproduced first |
| --- | --- |
| Calibration on the original | 8/12 |
| M1 base | 10/12 |
| Loop iteration 1 | 8/12 |
| Loop iteration 2 | 10/12 |
| Loop iteration 3 | 7/12 |
| Confirmation on the final text | 10/12 |

### Final comparison

30 paired sessions per arm (10 fixtures on Haiku, Sonnet, and Opus), run
concurrently. Both arms invoked the skill explicitly from staged copies and were
graded by the blind Opus judge.

| Measure | Original | Candidate | Difference |
| --- | --- | --- | --- |
| PASS-100 Haiku | 87.1 | 89.4 | +2.3 |
| PASS-100 Sonnet | 88.1 | 82.7 | -5.4 |
| PASS-100 Opus | 94.7 | 95.0 | +0.4 |
| PASS-100 pooled | 90.0 | 89.0 | -0.9 (90% bootstrap -2.7 to +0.8) |
| Holdout pooled (12 pairs) | | | -1.8 |
| Resolved | 30/30 | 30/30 | 0 |
| Reproduced first | 23/30 | 25/30 | +2 (Sonnet 6 and 6) |
| Session cost | 3.71 USD | 3.67 USD | ratio 0.988 |

Ratios, candidate over original:

| Measure | Ratio |
| --- | --- |
| Test runs | 1.11 |
| Turns | 1.03 |
| Final report characters | 1.13 |
| Cache-write tokens | 0.96 |
| Cache-read tokens | 1.05 |
| Output tokens | 1.13 |

| AC | Verdict | Evidence |
| --- | --- | --- |
| AC1 | met | 27.9 percent smaller; frontmatter identical; folder holds only `SKILL.md`. |
| AC2 | not met | Cost ratio 0.988 against at most 0.95; test-run ratio 1.11 is above its floor. |
| AC3 | not met | Pooled -0.9 and bootstrap lower bound -2.7 pass, but Sonnet -5.4 is below -4. |
| AC4 | met | Holdout -1.8 against at least -3. |
| AC5 | met | 30 against 30. |
| AC6 | met | 25 against 23 pooled; Sonnet 6 against 6. |
| AC7 | met | Unit suite, package validation, and mirror equality pass locally. CI passes on Ubuntu, Windows, and macOS, including `--doctor` with Node 24. Locally `--doctor` fails only because the container has Node 22. |
| AC8 | met | R2 reports no open blocking finding. Its findings and dispositions are in the Review Log. |

### Diagnosis

These observations do not change the decision. They inform the next attempt.

- **Cost.** The text cut saved about 4 percent of cache-write tokens, as
  predicted. Reports grew 13 percent rather than shrinking, and output and
  cache-read tokens grew with them. M1 did not shorten reports on these
  fixtures, most of which touch security, config, or data and so require the
  full field set. Session cost is dominated by the work itself, not by the
  skill text.
- **Sonnet.** The drop comes from three sessions that the judge capped at 72 for
  patching before reproducing: hyg-032, hyg-083, and hyg-096. R2 found that
  only hyg-083 shows a real difference in behavior.
  - In hyg-032 and hyg-096 the original arm also edited before running a test,
    yet escaped the cap. In hyg-096 the two arms made the same seven calls.
  - The caps followed what the final report admitted. M1 makes Feedback Loop
    one of the four always-required fields. Sonnet wrote that field in 9 of 10
    candidate reports, against 3 of 10 original reports, so the candidate's
    reports more often stated that no failing test was run first.
  - Cap application also varies elsewhere. Sonnet hyg-019 skipped reproduction
    in both arms without a cap. Haiku hyg-019 was capped in both.
  - The same original text scored Sonnet 82.7, with 4 capped sessions, in the
    2026-10-02 baseline. In this run's original arm it scored 88.1, with 2
    capped. The candidate scored 82.7, with 5 capped. The difference is within
    the original skill's own run-to-run spread. Ten pairs cannot tell a real
    Sonnet regression from noise.
  - The likeliest causes are M1's more prominent Feedback Loop field and judge
    variance. Losing the repeated reproduce-first instructions is a weaker
    explanation. AC3 still stands as measured.
- **Metric limit.** A test command counts as reproduced first even when no test
  ran. Examples are `Ran 0 tests`, `No module named pytest`, or an
  unimportable start directory.
  - Before the first edit, such runs occurred in 6 final sessions: original
    Sonnet 051 and 064; candidate Sonnet 006, 032, and 051; candidate Opus 019.
    They also occurred in 2 sessions of every guard run.
  - R2 recounted with the stricter rule that a test must actually run:

    | Run | Metric count | Stricter count |
    | --- | --- | --- |
    | Final, original vs candidate | 23 vs 25 | 21 vs 21 |
    | Final, Sonnet | 6 vs 6 | 4 vs 3 |
    | Calibration | 8 | 6 |
    | Loop iteration 3 | 7 | 5 |
    | Confirmation | 10 | 8 |

  - So the candidate's +2 is an artifact of the metric. Iteration 3 reached the
    pass mark only through zero-test runs. AC6 holds under either count.
  - A next attempt should require the test output to show at least one test ran
    and re-derive the guard thresholds from that count.
- **Text lost beyond M-2.** R2 found more original instructions that no longer
  have an equivalent. None is a frozen rule.
  - Removing dead code and stale docs only on local evidence.
  - Stating the smallest viable change and the verification plan.
  - Reporting assumptions.
  - Patching only after the loop is understood or a blocker is named.
  - Partly covered: respecting lockfiles and documented defaults; verifying
    adjacent consumer commands; not reporting theoretical issues as confirmed.
  - Iteration 3 also replaced the Feedback Loop step's own first bullet with the
    LB1 sentence, so the debug path lost three reproduce-related sentences, not
    one repetition.
- **Grading.** One judge reply in the original arm broke the cap rule, which
  aborted that arm's first grading. `grade` now asks again once for such a
  reply. The original arm was regraded in full under that rule, and the
  candidate arm needed no retry.

### Spend and time

- Ledger total: 19.43 USD of the 50 USD cap. That covers guards, the loop
  driver, both arms, and judging.
- Wall-clock: about 45 minutes from the start of implementation to the final
  comparison.
