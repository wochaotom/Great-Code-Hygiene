# Compound Loop

Use this protocol to improve the skill without letting it drift.

## Phases

- **Phase R Research Corpus Lock-In:** collect, classify, distill, and weight authoritative sources before broad training. Compound against the locked corpus, not a growing random reading list.
- **Phase R2 Source-Grounded Audit Pack:** create per-source checklists, traceability, and a honing report so every training run records which authoritative sources were applied.
- **Phase C Compounder Discipline:** keep the loop narrow: one mutable target, fixed benchmark budget, comparable metric, keep/discard promotion, and logs.
- **Phase 0 Prototype:** exactly 100 prompts. Validate the rubric, scripts, logs, and auto-promotion gates.
- **Phase 1 Stabilized Core:** 150-250 prompts only if Phase 0 reveals coverage gaps.
- **Phase 2 Statistical Confidence:** grow toward 384+ prompts when a stronger pass/fail confidence signal matters.
- **Phase N Final Candidate:** any phase can be final when score, failure profile, and real-use behavior are satisfactory.

## Full-Auto Cycle

1. Select batch: smoke, focused, regression, or full phase.
2. Generate a source audit plan from the task domains.
3. Read every activated source pack individually.
4. Run tasks using the current skill.
5. For bug, regression, or flaky-behavior tasks, record the deterministic feedback loop used before the fix, or the concrete blocker that made no loop possible.
6. Score each result with PASS-100.
7. Validate result JSON and analyze statistics, including confidence intervals and baseline deltas when available.
8. Run matching executable fixtures when the prompt has an objective fixture.
9. Run overtraining guardrails before adding instructions, sources, or fixtures.
10. Extract candidate lessons from concrete failures only.
11. Draft a candidate skill update.
12. Validate the candidate folder structure.
13. Re-run the same batch and any recent failure regressions.
14. Promote only if gates pass.
15. Log the generation, sources activated, scores, accepted/rejected decision, feedback-loop evidence, and lesson evidence.

## Run Types

- **Audit-backed run:** score a real project session using observed misses, artifacts, and reviewer judgment. This is useful for compounding lessons from real work, but it is not a fully automated benchmark.
- **Model-execution run:** give each eval prompt to an agent in a fresh task context, collect its actual output, then score the artifact. Use this for stronger evidence before major promotions.
- **Script-only run:** generate batches, validate result JSON, calculate scores, and gate promotions. This tests the harness, not the model behavior.

Label every score with one of these run types. Do not compare audit-backed scores and model-execution scores as if they were the same measurement.

Transcript fixtures are regression signals for agent process evidence. They can check that a captured run names the deterministic feedback loop, verification, and artifacts, but they do not prove promotion readiness unless paired with fresh model-execution evidence.

Generated matrix variants are candidate evidence only. Use them to expose failure families and regression risk, then require independent model-execution, audit-backed real-task evidence, or source-grounded evidence before promoting a new lesson.

## Hard-Mode Real-Code Evidence

- Predeclare the failure family before fixing; reject evidence that drifts into another family.
- Build parent-plus-tests targets from permissively licensed real repos, keeping upstream source fixes hidden until the local attempted patch is complete.
- Use hidden or synthesized checks only as verification, not as the primary signal that guided the fix.
- Require at least three independent real-code targets before promotion, and prefer multiple ecosystems when feasible.
- If the recurrence is already explained by an existing lesson, record a no-promotion result instead of adding another rule.

## Promotion Gates

Promote automatically only when all conditions hold:

- Skill validation passes.
- PASS-100 result validation passes.
- Overtraining guardrails pass.
- Average score does not regress.
- Correctness, tests, security, and minimal diff categories do not regress on critical prompts.
- Matching executable fixtures pass when they exist for the failed or changed prompt category.
- Transcript fixtures pass when the change affects evidence-reporting or agent-process transcripts.
- Candidate change is tied to an observed failure, repeated real-use miss, or source-backed rule.
- Candidate source-backed rules must reference `source-registry.md` or an admitted, weighted source.
- Source-grounded promotions require a valid honing report checked by `scripts/validate_honing_report.py` and passed to `scripts/promote_candidate.py --require-honing-report`.
- Instruction length stays concise; longer updates need measurable benefit.
- Candidate does not add broad, vague rules such as "be more careful" without operational behavior.
- Candidate removes, merges, or narrows existing guidance when possible.

## Rejection Reasons

Reject and log candidate updates when they:

- Improve one category by causing a critical category regression.
- Add lengthy policy text with no scoring improvement.
- Encode one-off prompt details instead of durable lessons.
- Conflict with Codex system/developer instructions.
- Make Claude export less portable.

## Phase Advancement

Do not advance phases automatically. Phase advancement is a human-level checkpoint. The automation may recommend expansion by reporting uncovered prompt categories, recurring failure clusters, or high score uncertainty.

Do not advance beyond Phase R until `source-registry.md`, `hygiene-principles.md`, and `source-weights.json` exist and are internally consistent.

## Final Candidate Criteria

A phase may be declared final when:

- Full current-phase suite is stable across at least two runs.
- Recent failure regressions are fixed or accepted as out of scope.
- Claude export validates and contains no local logs or secrets.
- The skill improves everyday coding/review behavior without noticeable instruction bloat.
