# Principle Traceability

Use this file to audit the distillation. Each principle maps to source IDs, PASS-100 categories, and review checks. Source IDs are defined in `source-weights.json`; source links live in `source-registry.md`.

| Principle | Source IDs | PASS-100 Categories | Checks |
| --- | --- | --- | --- |
| Preserve or improve code health | google-eng-practices | correctness, maintainability, local_integration, minimal_diff | Does the change improve the system overall, or does it solve one issue by adding lasting complexity? |
| Make behavior correct and user-appropriate | google-eng-practices | correctness, tests | Does it do what was intended, benefit users/developers, cover edge cases, and address concurrency/user-facing risk? |
| Keep changes small and reviewable | google-eng-practices | minimal_diff, maintainability, agent_process | Are style-only, formatting, generated, dependency, and unrelated changes separated from functional work? |
| Prefer simplicity over speculative flexibility | google-eng-practices | maintainability | Did the implementation solve the present problem without over-engineering future possibilities? |
| Match the local system | google-eng-practices, google-style-guides | local_integration, maintainability | Does the code follow local patterns unless those patterns worsen code health? |
| Use deterministic loops as fast feedback | google-testing, google-eng-practices | tests, correctness | For bugs, regressions, or flaky behavior, did the agent reproduce the symptom with the smallest reliable loop before fixing, or clearly state why no loop was possible? Are tests appropriate to risk, behavior-focused, maintainable, and placed at the fastest level that proves the behavior? |
| Treat security as design | nist-ssdf, owasp-secure-coding, owasp-asvs, microsoft-sdl, cisa-secure-by-design | security, correctness, tests | Are security requirements addressed during design/implementation/verification, not deferred to cleanup? |
| Prevent common weakness classes | mitre-cwe-top25, owasp-secure-coding, sei-cert | security, correctness | Did the review check injection, XSS, path traversal, authz, unsafe deserialization, memory/resource/concurrency defects, and secret leakage when relevant? |
| Handle failure deliberately | google-eng-practices, owasp-secure-coding, opentelemetry | observability, security, correctness | Are errors safe, useful, bounded, logged appropriately, and not swallowed? |
| Protect data | owasp-secure-coding, nist-ssdf, cisa-secure-by-design | security, observability | Are secrets/PII protected in logs, APIs, exceptions, telemetry, test fixtures, and artifacts? |
| Keep deploy-varying config out of code | twelve-factor-config, owasp-secure-coding | dependencies, security, local_integration | Are hostnames, credentials, resource handles, per-deploy values, and secrets outside code and version control? |
| Make public interfaces evolvable | microsoft-rest-api-guidelines, semver, google-eng-practices | local_integration, documentation, correctness | Are API/versioning/error/pagination/deprecation/migration compatibility concerns handled? |
| Make developer docs usable | google-developer-docs-style, google-eng-practices | documentation, maintainability, local_integration, minimal_diff | Are README/API/setup/procedure docs task-oriented, accurate, scannable, accessible, and tied to real behavior? |
| Keep LLM provider schema adapters explicit | llm-provider-schema-docs, google-eng-practices | correctness, tests, local_integration, security, documentation | Are tool/structured-output schemas normalized at provider boundaries with local canaries, safe diagnostics, and canonical schemas preserved? |
| Make builds and releases traceable | slsa, openssf-scorecard, microsoft-sdl | dependencies, security, agent_process | Are artifacts, provenance, CI, dependency posture, and release controls considered when build/release changes occur? |
| Make web UI accessible | wcag-22, google-eng-practices | correctness, local_integration, documentation | Are UI changes perceivable, operable, understandable, robust, keyboard usable, labeled, and tested where feasible? |
| Instrument what operators need | opentelemetry, google-eng-practices | observability, security | Do logs/metrics/traces help debug real failures without leaking sensitive data? |
| Apply Python-specific hygiene | python-core-docs, google-eng-practices | correctness, security, maintainability, local_integration | Are exceptions, cleanup, path handling, subprocess use, naming, docstrings, typing, and import-time behavior appropriate for the local Python project? |
| Keep Python tests and packaging coherent | python-testing-packaging, google-testing, google-eng-practices | tests, dependencies, correctness, local_integration | Do pytest layout/imports/fixtures prove behavior cleanly, and do pyproject/dependency/build settings match the repo's packaging model? |
| Evaluate agent traces, not only final answers | agent-eval-methodology | agent_process, tests, correctness | Does the evidence show goal fulfillment, plan quality, plan adherence, valid tool use, logical consistency, execution efficiency, and the localized failure point when a trace is available? |
| State residual risk honestly | google-eng-practices, agent-eval-methodology | agent_process, tests | Are checks run/unrun, assumptions, coverage gaps, and evaluation limits stated clearly? |

## Honing Requirement

Every honing run must record:

- Activated source packs.
- PASS-100 categories touched.
- Principles checked.
- Findings or "no issue found" notes for each activated pack.
- Evidence used to promote or reject a candidate skill update.

Do not promote a lesson unless it maps to a row in this file or adds a new audited row.
