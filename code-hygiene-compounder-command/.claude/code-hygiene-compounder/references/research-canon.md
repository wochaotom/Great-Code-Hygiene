# Research Canon

Use this as the durable basis for code hygiene decisions. Prefer source-backed rules over taste, but adapt them to the repo in front of you.

## Core Sources

Read `source-registry.md` for the full Phase R corpus and `source-weights.json` for activation rules. This summary keeps only the stable operating canon:

- Google Engineering Practices: review for design, functionality, complexity, tests, naming, comments, style, documentation, and every line of code; hold a high standard while balancing progress.
- Google Testing Blog: optimize for fast, reliable, failure-isolating feedback loops; keep end-to-end tests valuable but limited.
- NIST SSDF, CISA Secure by Design, Microsoft SDL: integrate security throughout requirements, design, implementation, verification, release, response, and user outcomes.
- OWASP Secure Coding, OWASP ASVS, OWASP Cheat Sheets: validate and verify concrete application security controls.
- MITRE CWE Top 25 and SEI CERT: prioritize common exploitable weakness classes and language-specific secure coding rules.
- SLSA, OpenSSF Scorecard, Twelve-Factor, OpenTelemetry, WCAG, REST API guidelines, SemVer, and NASA/JPL Power of Ten apply conditionally by task domain.
- OpenAI, Anthropic, and Agent GPA eval guidance: make evals task-specific, logged, automated where possible, human-calibrated where needed, trace-aware when agents plan or call tools, and continuously improved.

## Hygiene Principles

1. Correctness comes before elegance.
2. Small, reviewable changes beat broad cleanup.
3. Tests should prove behavior, not implementation trivia.
4. Security, privacy, and data handling defects are high-priority even when the visible diff is small.
5. Match local conventions unless the convention is the bug.
6. Prefer deletion and simplification over new abstraction.
7. Public interfaces require compatibility thinking: callers, migrations, versions, docs, and rollback.
8. Error paths deserve first-class review.
9. Automation should make drift harder, not easier.
10. Every durable lesson must be tied to evidence: a failing eval, repeated real miss, or source-backed rule.

## Agent-Specific Rules

- Inspect before editing. Guessing is a hygiene failure.
- Preserve user changes. Never revert unrelated work.
- Report verification honestly, including checks not run.
- Avoid changing generated, vendored, or lock files unless the task requires it.
- Keep final explanations concise and focused on behavior, verification, and residual risk.
- Do not promote a skill update merely because it sounds better; it must score better or preserve score with clearer instructions.
