# Phase 0 Evaluation Prompts

Use these 100 prompts as the Phase 0 prototype suite. Each prompt tests the agent's process and final result against PASS-100. Categories are balanced across ordinary coding, review, security, tests, frontend, APIs, data, config, migrations, and agent hygiene.

## Correctness and Regressions

1. **HYG-001:** Fix a null-reference crash in a shared helper without changing callers that already pass valid values.
2. **HYG-002:** Repair an off-by-one pagination bug while preserving existing API response shape.
3. **HYG-003:** Fix timezone handling in date filtering and add tests for boundary days.
4. **HYG-004:** Resolve a race condition in a cache refresh path without serializing unrelated work.
5. **HYG-005:** Fix duplicate form submissions while preserving keyboard submit behavior.
6. **HYG-006:** Correct an incorrect currency rounding path and protect against floating-point regressions.
7. **HYG-007:** Fix a retry loop that never stops and ensure transient failures still retry.
8. **HYG-008:** Repair a sorting bug with mixed-case names and retain stable ordering.
9. **HYG-009:** Fix a file upload size check that rejects valid boundary-size files.
10. **HYG-010:** Patch a memory leak in an event listener cleanup path.

## Test Quality

11. **HYG-011:** Add regression tests for a bug fix where no current test fails before the change.
12. **HYG-012:** Replace brittle snapshot assertions with behavior-focused assertions.
13. **HYG-013:** Add parameterized tests for input validation edge cases.
14. **HYG-014:** Fix flaky async tests without hiding real timing bugs.
15. **HYG-015:** Add tests for error-path behavior in a service client.
16. **HYG-016:** Improve coverage for a parser without asserting private implementation details.
17. **HYG-017:** Update tests after a public API change while preserving old compatibility cases.
18. **HYG-018:** Add frontend interaction tests for disabled, loading, and error states.
19. **HYG-019:** Create migration tests for forward and rollback paths.
20. **HYG-020:** Fix a test helper that masks production validation failures.

## Maintainability and Simplicity

21. **HYG-021:** Remove duplicated validation logic by reusing an existing helper.
22. **HYG-022:** Split an oversized function only where it improves readability and testability.
23. **HYG-023:** Simplify nested conditionals without changing behavior.
24. **HYG-024:** Replace magic constants with locally meaningful names.
25. **HYG-025:** Remove dead code after proving it is unused.
26. **HYG-026:** Refactor a data transformation pipeline while keeping public outputs identical.
27. **HYG-027:** Reduce coupling between UI and API shape using existing project patterns.
28. **HYG-028:** Consolidate repeated error formatting without introducing a global abstraction.
29. **HYG-029:** Rename confusing variables in a narrow diff without broad formatting churn.
30. **HYG-030:** Simplify configuration loading while keeping environment precedence intact.

## Security and Data Safety

31. **HYG-031:** Fix SQL injection risk using the project's query parameter API.
32. **HYG-032:** Prevent path traversal in file downloads and test encoded path attempts.
33. **HYG-033:** Remove accidental secret logging while preserving useful diagnostics.
34. **HYG-034:** Harden authorization checks on a resource update endpoint.
35. **HYG-035:** Validate webhook signatures before parsing privileged payloads.
36. **HYG-036:** Fix unsafe HTML rendering in a user-generated content component.
37. **HYG-037:** Protect password reset token handling from timing and reuse mistakes.
38. **HYG-038:** Replace insecure random token generation with a cryptographic source.
39. **HYG-039:** Audit a dependency upgrade for breaking and security-sensitive changes.
40. **HYG-040:** Prevent sensitive fields from being returned in a serialized API response.

## Local Integration

41. **HYG-041:** Add a feature flag using the repo's existing config provider.
42. **HYG-042:** Implement a new endpoint following local routing, auth, and error conventions.
43. **HYG-043:** Extend a TypeScript type without weakening strictness.
44. **HYG-044:** Add a database query using the existing repository pattern.
45. **HYG-045:** Update a React component using the local design system controls.
46. **HYG-046:** Add a CLI option that matches existing parsing and help text style.
47. **HYG-047:** Adjust logging to match local structured log fields.
48. **HYG-048:** Add a background job using existing retry and idempotency patterns.
49. **HYG-049:** Integrate a third-party API using the existing client wrapper.
50. **HYG-050:** Update validation messages to match product tone and localization patterns.

## Minimal Diff and Reviewability

51. **HYG-051:** Fix a bug in a file with unrelated user edits without reverting them.
52. **HYG-052:** Avoid formatting an entire file while changing two logic lines.
53. **HYG-053:** Keep generated files untouched unless regeneration is required.
54. **HYG-054:** Split a risky change into a small implementation patch plus tests.
55. **HYG-055:** Remove an accidental dependency introduced by an earlier patch.
56. **HYG-056:** Back out an unnecessary abstraction while preserving the requested behavior.
57. **HYG-057:** Limit a global search-and-replace to safe symbol references.
58. **HYG-058:** Update docs only where behavior or usage actually changed.
59. **HYG-059:** Avoid lockfile churn when no dependency version changed.
60. **HYG-060:** Report the diff scope clearly after touching multiple modules.

## Error Handling and Observability

61. **HYG-061:** Add timeout handling to an external service call.
62. **HYG-062:** Improve retry behavior with backoff and bounded attempts.
63. **HYG-063:** Preserve root-cause exceptions while adding user-friendly errors.
64. **HYG-064:** Add structured logs for a failure path without leaking secrets.
65. **HYG-065:** Make batch processing continue safely after per-item failures.
66. **HYG-066:** Add metrics around a slow path using existing instrumentation.
67. **HYG-067:** Fix swallowed exceptions in an async task.
68. **HYG-068:** Add idempotency checks to a job that may be retried.
69. **HYG-069:** Surface validation errors with field-specific detail.
70. **HYG-070:** Add graceful degradation when optional configuration is missing.

## Documentation and Comments

71. **HYG-071:** Update public API docs after a parameter is deprecated.
72. **HYG-072:** Remove misleading comments after simplifying a function.
73. **HYG-073:** Add a short comment explaining a non-obvious compatibility workaround.
74. **HYG-074:** Document a migration step without duplicating implementation details.
75. **HYG-075:** Update README examples after a CLI behavior change.
76. **HYG-076:** Add release-note guidance for a user-visible behavior change.
77. **HYG-077:** Keep comments out of obvious code while clarifying tricky business rules.
78. **HYG-078:** Document environment variables and defaults after config changes.
79. **HYG-079:** Add troubleshooting notes for a known external API failure mode.
80. **HYG-080:** Remove stale docs for a deleted option.

## Dependency and Config Hygiene

81. **HYG-081:** Add a dependency only after checking whether the standard library or existing dependency suffices.
82. **HYG-082:** Upgrade a vulnerable package and update tests for behavior changes.
83. **HYG-083:** Fix environment variable precedence without breaking local defaults.
84. **HYG-084:** Add config validation for required production settings.
85. **HYG-085:** Remove unused package references from manifest and lockfile.
86. **HYG-086:** Update build config without disabling strict checks.
87. **HYG-087:** Fix Docker image bloat from unnecessary build artifacts.
88. **HYG-088:** Add CI check configuration for a new test suite.
89. **HYG-089:** Ensure platform-specific paths work on Windows and Unix.
90. **HYG-090:** Prevent test-only config from leaking into production startup.

## Agent Process Hygiene

91. **HYG-091:** Start from a dirty worktree and preserve unrelated user changes.
92. **HYG-092:** Discover the repo's narrow test or verification command and use it directly instead of assuming one or adding broad search, subagent, review, or custom verifier machinery when the deterministic loop is already clear.
93. **HYG-093:** Explain residual risk when a required integration test cannot run locally.
94. **HYG-094:** Use a repo's existing parser instead of ad hoc string manipulation.
95. **HYG-095:** Ask only for product intent after exhausting discoverable code facts.
96. **HYG-096:** Capture a durable lesson from a repeated eval failure without bloating SKILL.md.
97. **HYG-097:** Reject a candidate skill update that improves style but lowers security score.
98. **HYG-098:** Export a Claude package from the current Codex skill without including logs.
99. **HYG-099:** Recommend phase expansion based on uncovered categories, not automatic runaway growth.
100. **HYG-100:** Declare a phase final only after stable scores, acceptable failure profile, and validated export.
