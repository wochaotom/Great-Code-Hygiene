# Spec: Code Hygiene Token Diet, Second Attempt (v2)

Status: draft for review R1′; thresholds frozen before any v2 data. Owner:
maintainers.
Machine-readable thresholds:
[`code-hygiene-token-diet-v2.json`](code-hygiene-token-diet-v2.json). The first
attempt and its evidence: [`code-hygiene-token-diet.md`](code-hygiene-token-diet.md)
(v1).

## Contents

- Why a Second Attempt
- Changes From v1
- Metrics
- Load-Bearing Rules
- Guard
- Loop Rules
- Acceptance Criteria and Decision
- Budget and Stop Rules
- Review Log
- Results

## Why a Second Attempt

v1 shrank `code-hygiene/SKILL.md` by 27.9 percent but missed two criteria:

- cost ratio 0.988, where the limit was 0.95;
- Sonnet quality -5.4, where the limit was -4.

The final review (R2) traced most of the miss to measurement rather than to the
cut:

- **Report format confound.** M1 made the Feedback Loop report field mandatory.
  Sonnet then stated it in 9 of 10 candidate reports against 3 of 10 originals,
  and the judge capped sessions that admitted no failing test was run first.
- **Zero-test runs counted.** Reproduced-first counted test commands that ran
  zero tests.
- **Unprotected instructions lost.** The loop dropped instructions that no frozen
  sentence protected.
- **Inherited config.** Sessions inherited the parent Claude Code config.

v1 also showed two things that shape this design:

- Text cuts save tokens but barely move session cost.
- One round of ten Sonnet pairs cannot separate a real change from Sonnet's
  run-to-run spread: 82.7 and 88.1 for the same original text.

## Changes From v1

1. **No report change.** The candidate starts from the original text on `main`
   (`26d292d`). M1 is not used. The report list and its lead-in are frozen, so
   both arms ask for the same report.
2. **Strict reproduced-first.** A test call counts only when its own tool output
   shows that at least one test ran, paired by `tool_use_id`. Accepted
   summaries, each with N of at least 1:
   - unittest `Ran N tests`;
   - pytest `N passed` or `N failed`, or `collected N items`;
   - node `# tests N`.

   `Ran 0 tests`, import errors, and empty collections do not count. Test-run
   counts use the same rule. The v1 (loose) count is still recorded for
   comparison.
3. **Clean configuration.** Every model session (fixtures, guard, judge) runs
   with a fresh, empty `CLAUDE_CONFIG_DIR`. A one-session smoke test must show
   two things before any other spend:
   - the session authenticates;
   - its init event lists only built-ins and the staged hygiene plugin.
4. **More frozen sentences.** The frozen set is v1's 21 rules (with the report
   list) plus seven original sentences R2 found unprotected: LB22 to LB28.
5. **More Sonnet data.** The final comparison runs Sonnet twice per fixture (20
   pairs), and Haiku and Opus once (10 pairs each).
   - Pooled figures are the mean of the per-model means, so every model weighs
     the same.
   - The bootstrap resamples within each model.
6. **Token criterion.** AC2 measures the tokens the skill loads and checks that
   cost does not rise, instead of requiring session cost to fall.

## Metrics

As in v1 (size, frontmatter hash, cost, resolved, PASS-100 from the blind Opus
judge), with these changes:

- **Reproduced first (strict):** a Bash call that runs a test command and whose
  output shows at least one test ran comes before the first call that changes a
  file inside the target. A call that both tests and changes a file does not
  count. File changes are detected as in v1.
- **Test runs (strict):** the number of such test calls in a session.
- **First-turn tokens:** for the first assistant message of a session,
  `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`. Prompts
  are identical per fixture, so the difference between arms is the size of the
  loaded skill text in tokens.
- **Pooled statistic:** the mean of the three per-model values.
- **Pairing:** sessions pair by model, fixture, and round.

## Load-Bearing Rules

LB1 to LB21 as in v1. LB10 now freezes the original report list: the lead-in
"For implementation work, report:" and all eight field sentences. New rules:

| ID | Rule (verbatim sentence) |
| --- | --- |
| LB22 | State the smallest viable change and the verification plan. |
| LB23 | Report evidence, skipped checks, assumptions, and residual risk. |
| LB24 | Patch only after the loop is understood or after a concrete blocker is named. |
| LB25 | Remove dead code and stale docs only when the local evidence supports removal. |
| LB26 | Prefer characterization tests or golden traces when behavior is unclear. |
| LB27 | Prefer framework-supported safe APIs over custom parsing or hand-rolled security controls. |
| LB28 | Each finding should name the behavior risk, affected path, evidence, and a practical fix direction. |

The frozen sentences total 3,998 of 9,070 normalized bytes (44 percent).
`tests/test_code_hygiene_core_rules.py` checks them against the v2 JSON.

## Guard

The static checks are as in v1:

- frontmatter hash unchanged;
- no change outside `code-hygiene/SKILL.md`;
- each kept step saves at least 32 normalized bytes;
- every frozen sentence present;
- at most 5 words absent from the original.

The behavioral check runs Haiku and Sonnet on the six train fixtures, one round
(12 sessions, clean configuration, skill invoked explicitly), scored on the
strict count:

- 2 or more unresolved sessions in a stage fail the guard;
- 6 or more reproduced first pass;
- 3 or fewer fail;
- at 4 or 5, a second stage of 12 sessions runs, and the guard passes at 10 or
  more of 24.

The thresholds come from 36 earlier original-skill sessions on the train
fixtures, rescored strictly: Haiku 12/18, Sonnet 6/18. The binomial model gives
these chances of passing:

| Candidate | Chance of passing |
| --- | --- |
| Unchanged skill | 86% |
| Down 1 of 12 | 60% |
| Down 2 of 12 | 28% |
| Down 3 of 12 | 6% |
| Rates halved | 8% |

The expected cost is 1.3 single guard runs.

Calibration: the original skill must pass the guard under the clean
configuration before the loop starts; otherwise stop. After the loop, one fresh
confirmation guard runs on the final text. On a failure, step back one kept
change once; a second failure means no merge.

## Loop Rules

- The autoresearch classic loop runs on Opus with a driver budget of 3 USD,
  starting from tag `token-diet-v2-base`, which holds the original skill text.
- One removal or condensation per iteration. No new rules, examples,
  abbreviations, or fixture hints.
- The driver receives v1's kept cuts as hints:
  - When To Use;
  - the Purpose sentence that repeats Hard Stops;
  - Task Modes;
  - Quick Start;
  - overlaps between Tool And Access Limits and Hard Stops.

  It is also told to move frozen sentences rather than delete them.
- The loop stops at the first of these:
  - 28 percent below the original;
  - 5 iterations;
  - 2 consecutive static rejections;
  - 3 consecutive behavioral rejections;
  - ledger above 31.50 USD;
  - 16:20 UTC.

## Acceptance Criteria and Decision

Final comparison:

- Two arms: the original (`26d292d`) and the candidate. Both are invoked
  explicitly from staged copies, under a clean configuration, with at most 40
  turns and one retry for broken sessions.
- All ten fixtures: Haiku once, Sonnet twice, Opus once. That gives 40 pairs and
  80 sessions.
- The arms run concurrently and are graded by the blind Opus judge under a clean
  configuration, with one retry for a reply that breaks the cap rule.

| AC | Criterion |
| --- | --- |
| AC1 | Normalized body at least 25 percent smaller than the original; frontmatter byte-identical; `code-hygiene/` holds only `SKILL.md`. |
| AC2 | (a) First-turn tokens at least 400 lower per session on average, for each model. (b) Pooled cost ratio at most 1.05. (c) Strict test-run ratio at least 0.80. |
| AC3 | Pooled PASS-100 difference (candidate minus original) at least -1.5; every per-model difference at least -4; lower bound of the two-sided 90 percent bootstrap at least -4.5. The bootstrap resamples pairs within each model, using seed 20261002, 10,000 resamples, and the percentile method. |
| AC4 | Pooled holdout difference at least -3. |
| AC5 | Candidate resolved count at least the original's minus 1 (of 40). |
| AC6 | Strict reproduced-first: pooled count at least the original's minus 5 (of 40); Sonnet at least the original's minus 4 (of 20). |
| AC7 | Full unit suite, `validate_package.py`, mirror byte equality, and CI on Ubuntu, Windows, and macOS pass. |
| AC8 | Final independent review R2′ has no open blocking finding; blocking findings are fixed and confirmed, not closed by a disposition. |

Decision: if every criterion is met, squash-merge pull request #3 into `main`.
Otherwise do not merge and record the result here.

Error rates, assuming a per-pair score SD of 8 (v1 Sonnet: 9.6). A change that
is neutral on quality still fails some criterion about 40 percent of the time:

| Criterion | Chance a neutral change fails it |
| --- | --- |
| AC2b | about 10% |
| AC2c | about 3% |
| AC3 | about 14% |
| AC4 | about 4% |
| AC6 | about 12% |

The design accepts that and prefers a false no-merge to a false merge.

## Budget and Stop Rules

- The 50 USD ledger cap from v1 still applies; v1 spent 19.43 USD, leaving 30.57
  USD.
- Planned spend:

  | Item | Estimate |
  | --- | --- |
  | Smoke and calibration | about 1.5 USD |
  | Loop guards and driver | at most 9.5 USD |
  | Confirmation and step-back | at most 3 USD |
  | Final comparison | about 9.8 USD sessions plus at most 5.6 USD judge |

- Wall-clock: about two hours from plan approval at 14:57 UTC.
- On reaching either cap, stop, record the results, and do not merge.

## Review Log

| ID | Review | Severity | Finding | Disposition |
| --- | --- | --- | --- | --- |

## Results

To be completed after the final comparison.
