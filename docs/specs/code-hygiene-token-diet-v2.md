# Spec: Code Hygiene Token Diet, Second Attempt (v2)

Status: revised after review R1′. Thresholds were frozen before any comparison
data; the only v2 data so far is a smoke session and the calibration guard on
the original skill. Owner: maintainers.
Machine-readable thresholds:
[`code-hygiene-token-diet-v2.json`](code-hygiene-token-diet-v2.json). The first
attempt and its evidence: [`code-hygiene-token-diet.md`](code-hygiene-token-diet.md)
(v1).

## Contents

- Why a Second Attempt
- Changes From v1
- Metrics and Pooling
- Load-Bearing Rules
- Guard
- Loop Rules
- Acceptance Criteria and Decision
- Budget, Time, and Stop Rules
- Review Log
- Results

## Why a Second Attempt

v1 shrank `code-hygiene/SKILL.md` by 27.9 percent but missed two criteria:

- cost ratio 0.988, where the limit was 0.95;
- Sonnet quality -5.4, where the limit was -4.

The final review (R2) traced most of the miss to measurement rather than to the
cut:

- **Report format.** M1 made the Feedback Loop report field mandatory. Sonnet
  then stated it in 9 of 10 candidate reports against 3 of 10 originals, and the
  judge capped sessions that admitted no failing test was run first.
- **Zero-test runs.** Reproduced-first counted test commands that ran zero
  tests.
- **Unprotected instructions.** The loop dropped instructions that no frozen
  sentence protected.

v1 also showed two things that shape this design:

- Text cuts save tokens but barely move session cost.
- One round of ten Sonnet pairs cannot separate a real change from Sonnet's
  run-to-run spread: 82.7 and 88.1 for the same original text.

## Changes From v1

1. **No report change.** The candidate starts from the original text on `main`
   (`26d292d`); M1 is not used.
   - LB10 freezes the whole report list as one contiguous block, from "For
     implementation work, report:" through the Residual Risk field, including the
     list markers.
   - Its fields cannot be reordered, split, or moved, so both arms ask for the
     same report.
2. **Strict reproduced-first.** A test call counts only when its own tool output
   shows that at least one test ran, paired by `tool_use_id`. Accepted
   summaries, each with N of at least 1:
   - unittest `Ran N test` or `Ran N tests`;
   - pytest `N passed` or `N failed`;
   - node `# tests N` or `ℹ tests N`.

   Rejected even with such a summary:
   - unittest `_FailedTest`;
   - `Failed to import test module`;
   - pytest `Interrupted:` or `error during collection`.

   Test-run counts use the same rule. The v1 (loose) counts are still recorded.
3. **Environment (A-1).** Both arms run in the same standard Claude Code
   environment, as in v1.
   - A smoke session with a fresh `CLAUDE_CONFIG_DIR` removed only one user-level
     skill.
   - Its cold first turn read nothing from the prompt cache, and its cost was
     double that of v1's session on the same fixture.
   - Every session records an init fingerprint: a hash of the model, Claude Code
     version, tools, skills, plugins, and MCP servers. `compare` reports the
     fingerprints per model and arm, and they must match.
4. **More frozen sentences.** v1's 21 rules plus seventeen:
   - LB22 to LB25, the instructions R2 found lost;
   - LB26 to LB28, which v1 restored after its loop (M-2);
   - LB29 to LB38, added on R1′'s advice.
5. **More Sonnet data.** The final comparison runs Sonnet twice per fixture (20
   pairs) and Haiku and Opus once (10 pairs each).
6. **Token check.** AC2 checks the tokens the skill loads and that cost is not
   meaningfully higher, instead of requiring session cost to fall.

## Metrics and Pooling

As in v1 (size, frontmatter hash, cost, resolved, PASS-100 from the blind Opus
judge), plus:

- **Reproduced first (strict):** a Bash call that runs a test command, with
  output that shows at least one test ran, comes before the first call that
  changes a file inside the target. A call that both tests and changes a file
  does not count. File changes are detected as in v1.
- **Test runs (strict):** the number of such test calls in a session.
- **First-turn tokens:** for the first assistant message,
  `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`. Prompts
  are identical per fixture, so the difference between arms measures the loaded
  skill text. Total tokens per session by type are also reported.
- **Pairing:** sessions pair by model, fixture, and round.
- **Pooling:**
  - A pooled mean is the mean of the three per-model means.
  - A pooled ratio divides the candidate's pooled mean by the original's, so
    Opus carries most of the cost weight.
  - Each bootstrap replicate resamples pairs within each model and takes the
    mean of the per-model means.
  - Counts (resolved, reproduced first) are plain totals over all sessions.
- **Incomplete sessions:** a session that still fails after its retry has no
  graded result. `compare` then refuses to evaluate, every comparison criterion
  counts as not met, and the effort does not merge.

## Load-Bearing Rules

LB1 to LB21 as in v1. LB10 is now the contiguous original report list. New
rules, each a verbatim sentence or sentence pair from the original:

| ID | Rule |
| --- | --- |
| LB22 | State the smallest viable change and the verification plan. |
| LB23 | Report evidence, skipped checks, assumptions, and residual risk. |
| LB24 | Patch only after the loop is understood or after a concrete blocker is named. |
| LB25 | Remove dead code and stale docs only when the local evidence supports removal. |
| LB26 | Prefer characterization tests or golden traces when behavior is unclear. |
| LB27 | Prefer framework-supported safe APIs over custom parsing or hand-rolled security controls. |
| LB28 | Each finding should name the behavior risk, affected path, evidence, and a practical fix direction. |
| LB29 | Respect lockfiles, manifests, generated files, and documented defaults. |
| LB30 | Verify adjacent consumer commands when package or config changes can affect install, build, runtime, or export behavior. |
| LB31 | Do not report theoretical issues as confirmed without a code path or behavior path. |
| LB32 | Keep comments sparse and useful; explain tricky rules, do not narrate obvious code. |
| LB33 | Prefer a focused test or exact failing command over inspection. |
| LB34 | Add an abstraction only when it removes real complexity, reduces meaningful duplication, or matches a local pattern. |
| LB35 | Check repo instructions and conventions before inventing a new style. |
| LB36 | Prefer existing helpers, frameworks, parsers, APIs, and architecture seams. |
| LB37 | If no loop is possible, state what was tried and what is missing. |
| LB38 | Treat failing or unavailable checks as evidence; do not move to Report on a failing check without naming the blocker. |

The JSON holds the exact text. Each frozen sentence appears exactly once in the
original. Together they total 5,070 of 9,070 normalized bytes (56 percent).
R1′ estimated that the hinted cuts still allow about 28 percent; AC1 needs 25.
`tests/test_code_hygiene_core_rules.py` checks the sentences against the v2
JSON.

## Guard

The static checks are as in v1:

- frontmatter hash unchanged;
- no change outside `code-hygiene/SKILL.md`;
- each kept step saves at least 32 normalized bytes;
- every frozen sentence present;
- at most 5 words absent from the original.

The behavioral check runs Haiku and Sonnet on the six train fixtures, one round
(12 sessions, skill invoked explicitly), scored on the strict count:

- 2 or more unresolved sessions in a stage fail the guard;
- 6 or more reproduced first pass;
- 3 or fewer fail;
- at 4 or 5, a second stage of 12 sessions runs, and the guard passes at 10 or
  more of 24.

The thresholds come from 36 earlier original-skill sessions, rescored strictly:
Haiku 12/18, Sonnet 6/18. Pass chances under the binomial model:

| Candidate | Chance of passing |
| --- | --- |
| Unchanged skill | 86% |
| Down 1 of 12 | 60% |
| Down 2 of 12 | 28% |
| Down 3 of 12 | 6% |
| Rates halved | 8% |

The expected cost is 1.32 single runs. Sonnet contributes only about 2 of the 6
expected hits, so the guard is weak for Sonnet-only losses: a candidate with
Sonnet's rate halved passes 61 percent of the time.

Calibration: the original skill passed at 6 of 12 (15:03 UTC, 0.99 USD). The
thresholds did not move after that run. After the loop, one fresh confirmation
guard runs on the final text. On a failure, step back one kept change once; a
second failure means no merge.

## Loop Rules

- The autoresearch classic loop runs on Opus with a 2 USD driver budget,
  starting from tag `token-diet-v2-base`, which holds the original text.
- One removal or condensation per iteration. No new rules, examples,
  abbreviations, or fixture hints.
- The driver receives v1's kept cuts as hints: When To Use, the Purpose
  repetition, Task Modes, Quick Start, and the Tool Limits and Hard Stops
  overlap. It is told to move frozen sentences rather than delete them.
- The loop stops at the first of these:
  - 28 percent below the original;
  - 5 iterations;
  - 2 consecutive static rejections;
  - 3 consecutive behavioral rejections;
  - guard ledger total above 25.50 USD;
  - 16:00 UTC.

## Acceptance Criteria and Decision

Final comparison:

- Two arms: the original (`26d292d`) and the candidate. Both are invoked
  explicitly from staged copies, with at most 40 turns and one retry for broken
  sessions.
- All ten fixtures: Haiku once, Sonnet twice, Opus once. That gives 40 pairs and
  80 sessions.
- The arms run concurrently and are graded by the blind Opus judge, with one
  retry for a reply that breaks the cap rule.

| AC | Criterion |
| --- | --- |
| AC1 | Normalized body at least 25 percent smaller than the original; frontmatter byte-identical; `code-hygiene/` holds only `SKILL.md`. |
| AC2 | (a) First-turn tokens at least 400 lower per session on average, for each model. (b) Pooled cost ratio at most 1.05. (c) Strict test-run ratio at least 0.80. |
| AC3 | Pooled PASS-100 difference (candidate minus original) at least -1.5; every per-model difference at least -4; lower bound of the two-sided 90 percent bootstrap at least -4.5. The bootstrap uses seed 20261002, 10,000 resamples, and the percentile method. |
| AC4 | Pooled holdout difference at least -3. |
| AC5 | Candidate resolved count at least the original's minus 1 (of 40). |
| AC6 | Strict reproduced-first: pooled count at least the original's minus 5 (of 40); Sonnet at least the original's minus 4 (of 20). |
| AC7 | Full unit suite, `validate_package.py`, mirror byte equality, matching init fingerprints, and CI on Ubuntu, Windows, and macOS pass. |
| AC8 | Final independent review R2′ has no open blocking finding; blocking findings are fixed and confirmed, not closed by a disposition. |

Decision: if every criterion is met, squash-merge pull request #3 into `main`.
Otherwise do not merge and record the result here.

What AC2 can and cannot show:

- (a) is a consistency check that bytes become tokens. In v1 the first-turn
  saving was nearly deterministic: 627 tokens on Haiku and about 895 on Sonnet
  and Opus for a 2,559-byte cut. A cut that meets AC1 should therefore meet (a).
- (b) is a non-inferiority bound of +5 percent. The expected true cost effect
  (about -1 to -2 percent) is below this design's resolution, so v2 can merge
  without a measured cost saving. Its claim is fewer tokens loaded per session
  at no meaningful quality or cost penalty.

Error rates, from R1′'s recomputation (per-pair SD 8; 10, 20, and 10 pairs;
mean of model means):

| Criterion | Chance a neutral change fails it |
| --- | --- |
| AC3 | about 19% |
| AC4 | about 7.5% |
| AC6 | about 10% |
| AC2(b) | about 5% |
| AC2(c) | about 0.5% |
| Resolved rule | about 2% |
| Any criterion | about 33% |

With the per-model SDs seen in v1, the chance of failing any criterion is about
22 percent. Power is limited:

- a true Sonnet drop of 5 points is caught about 74 percent of the time;
- halving Sonnet's reproduced-first rate is caught by AC6 only about 40 percent
  of the time.

The design accepts these limits.

The holdout is not pristine: v1's holdout results shaped this design.

## Budget, Time, and Stop Rules

- The 50 USD ledger cap still applies. At the start of the loop the ledger
  stands at 20.56 USD: v1, the smoke session, and calibration.
- Reserves:

  | Item | Worst case |
  | --- | --- |
  | Final comparison (sessions plus judge) | about 16 USD |
  | Confirmation and step-back (2 guards, up to 2 stages each) | about 4.4 USD |
  | Loop driver | 2 USD |

  Loop guards therefore stop at a ledger total of 25.50 USD. One two-stage
  overshoot leaves the worst case near 50 USD.
- Times (UTC):
  - loop ends by 16:00;
  - final comparison graded by 17:15;
  - R2′, docs, CI, and the decision by 17:45.
- Missing the 17:45 decision time, or reaching the ledger cap, means stop, record
  results, and do not merge.
- Ledger labels carry the run name. Every grading attempt keeps its log.

## Review Log

| ID | Review | Severity | Finding | Disposition |
| --- | --- | --- | --- | --- |
| A-1 | Smoke test | major | A fresh `CLAUDE_CONFIG_DIR` removes only one user skill, while the platform's 28 skills and 3 built-in plugins remain. Its cold first turn missed the prompt cache, at twice v1's cost for the same Haiku fixture. | Amended before any comparison data. Both arms use the standard environment, and init fingerprints must match. |
| R1′-1 | R1′ | blocking | LB10 was frozen sentence by sentence, so the loop could reshape the report. | Fixed: LB10 is one contiguous block. |
| R1′-2 | R1′ | major | Instructions that carry PASS-100 categories were still unprotected; the attribution was wrong. | Fixed: LB29 to LB38 frozen (all 11 sentences R1′ listed), attribution corrected. |
| R1′-3 | R1′ | major | The worst case overran the budget. | Fixed: driver 2 USD, loop guard stop at a 25.50 USD ledger total, reserves listed. |
| R1′-4 | R1′ | minor | The strict-summary text did not match the tool and allowed false positives. | Fixed in the text and the tool (singular and `ℹ` forms; `_FailedTest`, import, and collection errors rejected; `collected N` dropped). Counts on all stored sessions are unchanged. |
| R1′-5 | R1′ | minor | AC2(a) cannot bind and AC2(b) is non-inferiority. | Stated explicitly in Acceptance Criteria. |
| R1′-6 | R1′ | minor | The error-rate table was off. | Corrected from R1′'s recomputation, with the Sonnet power limits. No threshold changed. |
| R1′-7 | R1′ | minor | Pooling was undefined for ratios, bootstrap, and counts. | Fixed in Metrics and Pooling; the JSON states `"metric": "strict"`. |
| R1′-8 | R1′ | minor | Sessions that still fail after a retry were unhandled. | Fixed: the comparison is incomplete and the criteria are not met. `grade` skips such rows instead of crashing. |
| R1′-9 | R1′ | minor | A-1 overstated its case and the causes list kept the inherited config. | Reworded; fingerprints added. |
| R1′-10 | R1′ | minor | Calibration ran before R1′ closed. | Noted under Guard: no threshold moved after calibration, and no R1′ fix depends on its result. |
| R1′-11 | R1′ | minor | No concrete clock. | Fixed: hard times under Budget, Time, and Stop Rules. |
| R1′-12 | R1′ | minor | Ledger labels could not tell arms apart; the holdout is not pristine. | Fixed: labels carry the run name; holdout caveat stated. |

## Results

To be completed after the final comparison.
