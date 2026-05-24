# Training Lessons

Durable lessons promoted from scored target-dummy runs. Keep entries short, source-backed, and reusable outside the original target.

## 2026-04-28: OWASP Juice Shop Codefix Loop

- Unsupported hidden routes: when a route or feature has no legitimate product requirement, prefer removing the exposed surface entirely over obfuscating it or adding a guard. Source basis: CISA secure-by-design systemic fixes, NIST SSDF vulnerability reduction, OWASP ASVS access-control verification.
- Risky endpoint families: when a whole category of external redirects or public surfaces is unsupported, remove the family rather than fixing one member and leaving near-identical risk behind. Source basis: MITRE root-cause weakness elimination, OWASP secure coding allowlists, CISA secure defaults.
- Middleware security: prefer framework-supported secure defaults and documented configuration over custom header parsing or hand-rolled security keying, especially for proxy-aware rate limiting. Source basis: OWASP secure coding safe auth/session handling, Microsoft SDL threat modeling, SEI CERT safe native constructs.
- Benchmark hygiene: if answer-sheet options are byte-identical or semantically equivalent, do not compound a label-only lesson. Fix the harness or record the artifact so training rewards behavior, not memorization.

## 2026-04-28: Gilded Rose Refactoring Kata

- Refactoring-kata setup: do not trust placeholder, demo, or dependency-bound tests as the whole oracle. First build or run a narrow requirements/characterization harness that proves the behavior to preserve and the new feature to add. Source basis: Google Testing behavior assertions, Google code-health review, OpenAI/Anthropic eval criteria for representative tests and clear success criteria.
- Locked model boundaries: when a kata or legacy system marks data structures/API as off-limits, preserve that boundary and move clarity into helper behavior around it. Source basis: Google Engineering Practices design fit, minimal scope, and local consistency.

## 2026-04-28: Tennis Refactoring Kata

- Identity-bearing inputs: when code accepts names, IDs, emails, tenants, roles, or other identity-bearing values, add at least one regression case that varies those values away from placeholders. Comprehensive-looking tests can still hide hard-coded identity bugs if every fixture uses `player1`, `user`, or similar defaults. Source basis: Google Testing behavior assertions, Anthropic eval edge-case coverage, OpenAI representative eval design.
- Refactor then fix deliberately: when a kata names a deliberate defect, first protect current behavior with the existing suite, then add the smallest failing regression for the defect, then refactor/fix. Source basis: Google Engineering Practices small code-health improvements and Google Testing failure-isolating checks.

## 2026-04-28: Trivia Legacy Refactoring Kata

- Output-heavy legacy code: before refactoring code whose behavior is mostly visible through logs, stdout, or transcripts, build a deterministic golden-master harness with fixed seeds and realistic interaction traces. Source basis: Google Testing behavior coverage, OpenAI eval input/output logging, Anthropic clear success criteria.
- Characterization-first cleanup: for legacy code with no tests, only make behavior-neutral extractions after the golden master is recorded and rechecked. Avoid fixing spelling, wording, or output quirks during the first cleanup pass unless the target behavior explicitly asks for it. Source basis: Google Engineering Practices minimal scope and style/behavior separation.

## 2026-04-28: Yatzy Refactoring Kata

- Missing lightweight test tooling: when a kata or legacy project has dependency-light tests but the nominal runner is unavailable, build the narrowest compatible runner for the exact test features used before deciding to install dependencies or skip tests. Source basis: Google Testing fast failure-isolating checks, OpenAI eval automated grading, Anthropic clear success criteria.
- Rule-table refactors: for dense scoring or rule code, consolidate repeated counting/summing through small helpers while preserving the public API and category names the tests call. Source basis: Google Engineering Practices local consistency, minimal scope, and complexity reduction.

## 2026-04-28: Theatrical Players Refactoring Kata

- Approval plus error paths: approval/golden-master tests are strong for visible formatted output, but pair them with explicit negative/error-path checks before refactoring statement/report code. Source basis: Google Testing behavior assertions, Anthropic hard-case coverage, OpenAI representative eval design.
- Formatting/report refactors: extract pricing, credit, lookup, and formatting helpers in separate behavior-preserving steps; keep exact text, currency formatting, and exception wording stable until the requested feature requires change. Source basis: Google Engineering Practices style/behavior separation and minimal scope.

## 2026-04-29: Self-Hygiene Guardrails

- Destructive tool paths: before any script deletes or replaces directory contents, resolve paths, reject same-source/destination operations, reject dangerous roots, require marker files, and print the planned deletion set. Source basis: OWASP safe file operations, NIST SSDF repeatable protection practices, Google Engineering Practices functionality/risk review.
- Empty metric sets: scoring tools must fail with a clear domain error when no numeric score values are present instead of leaking a generic statistics exception. Source basis: Google Testing clear failure isolation, OpenAI eval logging and automated grading, Anthropic clear success criteria.

## 2026-04-29: Parrot Refactoring Kata

- Polymorphism threshold: add variant-specific classes or strategy objects when they remove an active type switch and make new variants local, but keep the public constructor/API stable until callers are intentionally migrated. Source basis: Google Engineering Practices design fit, complexity reduction, and local consistency.
- Behavior-delegation and wrapper refactors: when replacing conditionals with delegation, factories, middleware stacks, send paths, or lifecycle/promise wrappers, preserve the caller-visible contract first: call shape, propagated state, error/cancellation ownership, and required cleanup/completion must cross the same awaited or callback boundary. Source basis: Google Testing behavior assertions and Google Engineering Practices minimal scope.

## 2026-04-29: Supermarket Receipt Refactoring Kata

- Business-rule arithmetic: sparse happy-path tests can miss pricing defects; before refactoring discounts, promotions, tax, billing, inventory, or quota code, add behavior tests for each rule type, boundary group, and remainder case. Source basis: Google Testing behavior assertions, Anthropic edge-case coverage, OpenAI representative eval design.
- Group/remainder pricing: isolate bundle and group-count calculations in helpers that make complete groups and leftover units explicit; preserve receipt text, public totals, and caller-facing APIs unless the task intentionally changes them. Source basis: Google Engineering Practices complexity reduction, local consistency, and minimal scope.

## 2026-04-29: Bowling Game Kata

- Public API invariants: for stateful scoring, quota, inventory, billing, rules-engine, decoder, config/default, generated schema/serializer/DTO, value-conversion APIs, caller-owned mutable inputs, or config/manifest/CLI path options, test and enforce domain constraints at every external contract boundary; keep absent values, explicit empty values, internal sentinels, validation versus serialization mode, request versus response/component context, public aliases/data keys, internal attribute/source names, reusable metadata, caller-owned object identity, and config-owner roots versus process cwd distinct before fallback, coercion, propagation, or error handling. Do not mutate or retain aliases to caller-owned mutable objects or collections unless the public contract explicitly transfers ownership. For config, manifest, and CLI path options, anchor relative paths to the owning config/manifest file or documented project root rather than process cwd, with cwd-varied tests plus absolute-path and host-path-mapping controls. Source basis: Microsoft REST API Guidelines, OWASP input/output handling, CISA secure defaults, Google Testing boundary behavior checks.
- CLI command boundaries: when code reconstructs, forwards, completes, or stringifies shell commands from argv, paths, magics, or user command fragments, preserve argument boundaries with structured argv or shell-appropriate quoting; regression-test spaces in executable paths, option values, filenames, and quoted command arguments, plus no-space controls. Source basis: Python subprocess/path handling, Google Testing boundary behavior, OWASP command invocation safe APIs.
- Protocol metadata key lookup: when code reads HTTP-like headers, W3C propagation metadata, CORS/header allow-lists, or framework header arguments from external carriers, honor documented key matching semantics such as case-insensitive field names; regression-test lower/title/upper-case variants plus unrelated-key controls, and keep auth/security-sensitive header handling on framework-supported paths rather than custom parsing. Source basis: Microsoft REST API Guidelines, Google Testing boundary behavior, OWASP secure coding safe APIs.
- Structured protocol header values: when code dispatches or parses HTTP/MIME header values such as `Content-Type`, separate the media-type essence from semicolon parameters with the documented grammar before matching; preserve repeated non-combinable fields such as `Set-Cookie` as separate values through adapters and cookie abstractions; parameter values may contain type-like text, legal optional whitespace, or delimiter characters. Regression-test essence matching, quoted/unquoted parameters, SP/HTAB whitespace, legal boundary characters, repeated `Set-Cookie` controls, and unrelated/invalid controls. Source basis: RFC 9110 HTTP field semantics/RFC 6265 cookies, Microsoft REST API Guidelines, Google Testing boundary behavior, OWASP structured input handling.
- Cross-realm judge assertions: when an eval harness runs candidate code in a VM, subprocess, browser frame, plugin sandbox, or other realm, do not rely only on native object identity such as `instanceof`; assert stable error names, messages, status codes, and observable behavior. Source basis: OpenAI eval logging/automated grading, Anthropic clear success criteria, Google Testing failure isolation.

## 2026-04-29: Racing Car Tire Pressure Kata

- Nondeterministic collaborators: when target behavior depends on randomness, clocks, sensors, network clients, files, or external services, add a narrow injectable collaborator before asserting behavior; preserve existing default construction for callers that do not pass a test double. Source basis: Google Testing failure isolation, Google Engineering Practices minimal scope and local integration.
- Threshold behavior: for monitoring, alerting, quota, limits, pricing, or policy code, test both sides of each threshold and exact boundary values before refactoring. Source basis: Google Testing behavior assertions, Anthropic edge-case coverage, OpenAI representative eval design.

## 2026-04-29: Racing Car Turn Ticket Kata

- Hidden shared state: when uniqueness, ordering, counters, queues, IDs, or rate limits depend on shared mutable state, make the owner of that state explicit and injectable for tests; keep a default shared owner only when existing callers rely on it. Source basis: Google Engineering Practices design fit, local integration, and minimal scope.
- Meaningless smoke tests: a test that only calls a method without asserting the returned value or state is not a behavioral oracle; replace it with assertions that prove uniqueness, sequence, boundary, or contract guarantees. Source basis: Google Testing behavior assertions, OpenAI automated grading, Anthropic clear success criteria.

## 2026-04-29: Racing Car Text Converter Kata

- Resource and side-effect lifetime checks: when code opens files, sockets, subprocess streams, database handles, locks, or persistent config/data files, tests should prove both the primary behavior and the cleanup/atomicity contract; dry-run and validation paths should leave prior state unchanged; package-manager or generated-state commands should re-read current manifests and exercise adjacent consumer commands after mutation so stale generated state cannot recreate removed resources or serialize impossible metadata; overwrites should use scoped ownership or same-directory temp-write plus replace when partial writes matter. Source basis: OWASP resource/file handling, Google Engineering Practices functionality review, Google Testing failure isolation.
- Encoding-sensitive text boundaries: text conversion, import/export, logs, JSON/config loaders, and HTTP response parsers should use explicit encodings in tests and implementation so behavior does not vary silently by machine locale; include leading UTF-8 BOM/`utf-8-sig` controls for external text before parsing, while preserving ordinary invalid-content failures. Source basis: Google Testing deterministic tests, OpenAI representative eval design, NIST repeatable practices, OWASP input validation.
- External reference data freshness: when behavior depends on bundled standards or reference datasets such as IANA timezone data, treat the data version as part of the runtime contract; add canaries for recent real-world rule changes, keep the update path explicit, and verify unaffected-zone controls before treating the package as current. Source basis: NIST repeatable practices, SLSA artifact verification, Google Testing boundary behavior.

## 2026-04-29: Racing Car Telemetry Kata

- Protocol-order tests: for retry loops, network clients, diagnostics, payment flows, queues, and multi-step integrations, assert the observable protocol order, retry count, success path, and failure path with a deterministic fake before refactoring. Source basis: Google Testing behavior assertions, Anthropic hard-case coverage, OpenAI representative eval design.
- Placeholder-test rejection: when an inherited test asserts an obviously impossible placeholder value or only proves scaffolding, replace it with the real initial-state and contract assertions before using it as promotion evidence. Source basis: Google Engineering Practices useful tests, Google Testing failure isolation, OpenAI eval grading quality.

## 2026-04-29: Racing Car Leaderboard Kata

- Stale test APIs: if inherited tests fail because the test framework API changed, repair the harness before judging product behavior; record the harness failure separately from implementation failures. Source basis: Google Testing maintainable tests, OpenAI eval logging, Anthropic failure classification.
- Sparse score tables: when business rules use rank tables, pricing tiers, permission levels, or priority buckets, test both in-table and out-of-table positions and define the fallback explicitly instead of relying on index errors or default crashes. Source basis: Google Testing boundary behavior, Google Engineering Practices functionality review, Anthropic edge-case coverage.

## 2026-04-29: Trip Service Python Kata

- Hard-wired collaborators: for legacy code that calls sessions, databases, HTTP clients, clocks, or global services directly, first write scoped tests that replace those collaborators and prove the business rules without changing the public interface. Source basis: Google Testing failure isolation, Google Engineering Practices local integration, NIST repeatable practices.
- No-test baselines: when a target has no discovered executable tests, record that as a distinct coverage failure and promote only after adding meaningful assertions for each business rule and collaborator boundary. Source basis: OpenAI eval logging, Anthropic clear success criteria, Google Testing useful tests.

## 2026-04-29: Trip Service JavaScript Kata

- Cross-runtime recurrence: when a failure pattern repeats in another language or runtime, do not promote a duplicate lesson from similarity alone; prove it again with executable behavior tests, then record the recurrence as reinforcement or a narrower runtime-specific lesson. Source basis: OpenAI regression tracking, Anthropic failure classification, Google Testing behavior assertions.
- JavaScript training artifacts: when npm install/test runs create coverage folders, lockfile metadata changes, audit warnings, or script-policy friction, separate those environment/tooling artifacts from the reviewed source diff and log dependency risk without broad package churn unless the task owns dependencies. Source basis: NIST repeatable practices, Google Engineering Practices minimal reviewable diffs, OWASP dependency/data-safety review.

## 2026-04-29: Trip Service C# Kata

- Harness-first runtime drift: when a legacy target depends on an unavailable runtime, framework, SDK, or test host, first make the copied harness executable with the smallest explicit compatibility change and record that separately from product behavior. Source basis: Google Testing failure isolation, SLSA reproducible build paths, OpenAI eval logging.
- Placeholder tests can hide missing integration: a test project that only asserts a local placeholder may compile while not referencing the production project at all; before scoring coverage, prove tests import/build the code under review. Source basis: Google Engineering Practices useful tests, Anthropic failure classification, OpenAI automated grading.

## 2026-04-29: Trip Service TypeScript Kata

- Forced dependency resolution is not harness health: if `--legacy-peer-deps`, `--force`, vendored caches, or lockfile overrides make install succeed, still verify that compiler, transformer, linter, and test runner versions are mutually supported before scoring product behavior. Source basis: SLSA reproducible build paths, NIST dependency protection, OpenAI eval logging.
- Toolchain modernization should be coherent and narrow: when updating a stale TypeScript/Jest/lint stack in a copied target, align the transformer syntax, compiler range, lint rules, and lockfile evidence together; record residual audit warnings and avoid broad dependency churn beyond the harness needed for executable tests. Source basis: Google Engineering Practices minimal diffs, SemVer compatibility, OWASP dependency review.

## 2026-04-29: Claude Command Entrypoint

- Exported command entrypoints must carry the operational safety rules, not merely point at bundled references; include repo-instruction precedence, audit/edit boundaries, verification-before-completion, source-grounded honing limits, and final-artifact inspection in the user-facing command text. Source basis: Google Engineering Practices documentation/usefulness, OpenAI eval logging, Anthropic clear success criteria.
- Validate generated packages by inspecting the exported command and archive contents, because passing source scripts alone does not prove the installed Claude-facing artifact enforces the intended workflow. Source basis: NIST repeatable practices, SemVer package compatibility, Google Testing behavior assertions.
- Archive filters should apply to relative package paths, not absolute filesystem paths; otherwise exporting under a parent named like an excluded folder, such as `runs`, can silently produce an empty package. Source basis: Google Testing behavior assertions, SLSA artifact verification, NIST repeatable practices.

## 2026-04-29: Source Audit Domain Validation

- Source activation inputs must fail closed: if a source-grounded planner receives an unknown domain, reject it with a clear allowed-domain list and suggestion instead of silently falling back to always-on sources. Source basis: OpenAI eval logging, Anthropic clear success criteria, Google Testing failure isolation.
- Conditional-source coverage needs executable checks for both typo and valid-domain paths; prove that a misspelled domain leaves no misleading plan artifact, and that the corrected domain activates the expected conditional source pack. Source basis: OpenSSF dependency-risk evidence, NIST repeatable practices, Google Engineering Practices useful tests.

## 2026-04-29: Honing Report Source Exactness

- Honing report validators must require checklist source IDs to match the activated source set exactly; reject extra, fake, or stale source IDs instead of only checking that activated sources are present. Source basis: OpenAI eval logging, Anthropic clear success criteria, Google Testing failure isolation.
- Planner domain validation must preserve documented generic domains such as `tests`, `legacy`, `review`, and `documentation`; fail closed for true unknowns without making normal workflow language unusable. Source basis: Google Engineering Practices local integration, NIST repeatable practices, OpenAI representative eval design.

## 2026-04-29: Honing Report Duplicate Source Rejection

- Source-grounded reports need one checklist result per activated source; reject duplicate checklist entries because repeated evidence can hide missing review coverage, inflate apparent diligence, or make promotion audits ambiguous. Source basis: OpenAI eval logging, Anthropic clear success criteria, Google Testing failure isolation.
- Keep standalone validation and promotion-gate validation behavior identical for malformed honing reports, otherwise dry-run validation can pass while apply-time gates behave differently. Source basis: NIST repeatable practices, Google Engineering Practices local consistency, OpenAI regression tracking.

## 2026-04-29: PASS-100 Score Shape Validation

- PASS-100 result scorers must validate each `scores[]` item shape before reading fields; malformed result items should fail with a clear scoring-domain error, not a Python traceback. Source basis: Google Testing failure isolation, OpenAI eval logging, Anthropic clear success criteria.
- Keep positive scorer fixtures alongside malformed fixtures so hardening invalid input does not break valid PASS-100 averages, warnings, or promotion readiness calculations. Source basis: Google Engineering Practices useful tests, OpenAI automated grading, NIST repeatable practices.

## 2026-04-29: PASS-100 Top-Level Shape Validation

- PASS-100 result files must be JSON objects before the scorer reads `scores`; arrays or strings should fail with a clear domain error instead of leaking an attribute traceback. Source basis: Google Testing failure isolation, OpenAI eval logging, Anthropic clear success criteria.
- Preserve a known-good score fixture for every scorer input-shape hardening change so malformed-artifact handling does not regress ordinary promotion scoring. Source basis: Google Engineering Practices useful tests, NIST repeatable practices, OpenAI automated grading.

## 2026-04-29: PASS-100 Invalid JSON Diagnostics

- PASS-100 scorers must reject malformed JSON with a clear scoring-domain diagnostic that names the file and location; do not leak raw parser tracebacks as promotion evidence. Source basis: OWASP input validation and safe errors, Google Testing failure isolation, OpenAI eval logging.
- Keep malformed-file fixtures separate from malformed-object fixtures so the harness proves both parser-boundary handling and schema-boundary handling. Source basis: Anthropic hard-case coverage, Google Engineering Practices useful tests, NIST repeatable practices.

## 2026-04-29: Honing Report Evidence Type Validation

- Source-grounded promotion reports must validate nested evidence as non-empty strings, not merely arrays or objects; otherwise numeric or boolean placeholders can masquerade as audited checklist coverage. Source basis: OpenAI eval logging, Anthropic clear success criteria, OWASP input validation.
- When tightening validator schemas, run both a malformed fixture and prior accepted valid reports so evidence hardening does not break legitimate promotion history. Source basis: Google Testing failure isolation, Google Engineering Practices useful tests, NIST repeatable practices.

## 2026-04-29: Promotion Gate Validator Parity

- Critical promotion gates should reuse the canonical validator for evidence schemas; duplicated partial validators drift and can approve reports that dry-run validation rejects. Source basis: NIST repeatable practices, Google Engineering Practices local consistency, OpenAI regression tracking.
- Gate-parity regressions need the same malformed fixture exercised through both the standalone validator and the promotion command before promotion. Source basis: Google Testing failure isolation, Anthropic clear success criteria, OWASP input validation.

## 2026-04-29: Promotion Score Artifact Validation

- Promotion commands must schema-check score artifacts before reading `average` or `promotion_ready`; malformed score files should fail closed with a gate-domain error, not a traceback. Source basis: OWASP input validation, NIST repeatable protection practices, OpenAI eval logging.
- Destructive-capable promotion paths need both malformed-score fixtures and known-good dry-run fixtures, because a valid honing report alone does not prove the score gate is safe. Source basis: Google Testing failure isolation, Google Engineering Practices functionality review, Anthropic clear success criteria.

## 2026-04-29: PASS-100 Nested Category Shape Handling

- PASS-100 scorers must not continue aggregating nested score fields after detecting that `categories` is not an object; record the schema warning and keep the malformed item from becoming promotion-ready. Source basis: Google Testing failure isolation, OWASP input validation, OpenAI automated grading.
- For score hardening, pair warning-producing malformed fixtures with known-good fixtures and earlier malformed-file regressions so one input boundary fix does not reopen another. Source basis: Anthropic hard-case coverage, NIST repeatable practices, Google Engineering Practices useful tests.

## 2026-04-29: Source Corpus Metadata Validation

- Source-grounded planners must validate corpus metadata shape before activating source packs; corrupted `source-weights.json` should fail closed with a corpus-domain diagnostic, not a raw collection/type exception. Source basis: NIST repeatable practices, OWASP input validation, OpenAI eval setup logging.
- Pair corrupted-corpus fixtures with a normal source-plan fixture so hardening the planner does not break everyday source activation. Source basis: Google Testing failure isolation, Anthropic edge-case coverage, Google Engineering Practices useful tests.

## 2026-04-29: Claude Export Path Safety

- Export tools must reject package folders and zip outputs inside the source skill root; generated artifacts under the canonical skill can pollute future training, packaging, or source audits. Source basis: OWASP constrained file operations, NIST artifact protection, Google Engineering Practices local integration.
- Verify both unsafe-path rejection and safe external export success before promoting export path guards. Source basis: Google Testing failure isolation, OpenAI artifact logging, Anthropic clear success criteria.

## 2026-04-29: Claude Package Format Separation

- Claude Code skill, Claude.ai upload skill, and legacy command exports must be explicit package formats with verifiable archive structures; do not label a `.claude/commands/` package as a modern skill. Source basis: Google Engineering Practices documentation impact, SemVer compatibility classification, Anthropic clear success criteria.
- Package exporters should assert archive contents, including the expected `SKILL.md` location and absence of run artifacts, before treating an export as usable. Source basis: Google Testing behavior assertions, NIST artifact protection, OpenAI eval logging.
- Multi-format exporters need format-specific staging directories before writing zips; otherwise concurrent or repeated exports to one output folder can delete or corrupt another format's staging tree. Source basis: NIST artifact protection, OWASP constrained file operations, Google Testing hard-case coverage.

## 2026-04-30: Phase 0A Python Fixture Sweep

- Python source-grounded honing should include the Python language domain alongside the functional domain, such as `python + security`, `python + config`, or `python + observability`; otherwise a plan can miss Python-specific checks for exceptions, subprocess/path handling, import-time behavior, typing, pytest layout, and packaging. Source basis: Python Core Docs and PEPs, Python Testing and Packaging, Google Engineering Practices local integration.

## 2026-04-30: Python Runner Harness Consolidation

- Python training harnesses must support the test-layout features actually used by the target before scoring product behavior: sibling test helpers, fixtures, `pytest.mark.parametrize`, approval/golden-file tests, pytest exception contexts, and mixed pytest/unittest collection. Use real pytest when available, or implement and regression-test the narrow subset locally. Source basis: Python Testing and Packaging, Google Testing behavior coverage, OpenAI eval logging.
- Python test discovery must fail visibly instead of scoring empty coverage: honor `pytest.ini` `testpaths` and `python_files`, include both `test_*.py` and `*_test.py` fallback patterns, fall back from zero-test root discovery to immediate child suites, log selected discovery roots/files, and collect `unittest.TestCase` methods inside discovered modules. Source basis: Python Testing and Packaging, Google Testing failure isolation, OpenAI eval logging.
- Python runner diagnostics should emit structured failure summaries alongside raw errors: exception type/text, file, line, function, assertion source or source call, approved-file path, expected/actual lengths, compact previews, and per-case mismatch summaries. Parse the real exception line before assertion diff tails so stale harness failures, empty golden files, and product assertion failures can be bucketed separately. Source basis: OpenAI eval logging, Anthropic failure classification, Google Testing failure isolation.
- Legacy unittest compatibility shims should be opt-in and logged; restore removed assertion aliases only when requested, record aliases in the run artifact, and keep remaining product/test failures visible instead of treating stale test APIs as product behavior. Source basis: Python Core Docs, Python Testing and Packaging, OpenAI eval logging.

## 2026-04-30: Python Target Batch Runner

- Training loops should provide repeatable batch runners that preserve expected-red targets while aggregating metrics; record per-target expected status, exit code, artifact path, total/passed/failed counts, and satisfaction so automation can keep running without hiding real failures. Source basis: OpenAI eval logging, Anthropic clear success criteria, NIST repeatable practices.

## 2026-04-30: Python Static Hygiene for Testless Legacy Targets

- Testless legacy Python targets should receive an AST-backed static hygiene pass with file, line, function, rule, severity, and evidence before being treated as evaluated; preserve clean-target regressions so structural scans do not become noisy substitute tests. Source basis: Python Core Docs, Google Testing failure isolation, OWASP secure coding review.

## 2026-04-30: Python Static Syntax Compatibility Findings

- Static Python hygiene scans should optionally convert `SyntaxError` parse failures into structured compatibility findings for known legacy-script targets; keep the default fail-closed path, but when opted in record file, line, rule, severity, and parser message so Python-version drift is not hidden as scanner failure. Source basis: Python Core Docs, Python Testing and Packaging, OpenAI eval logging.

## 2026-04-30: Python Static Resource Management Findings

- Python static hygiene scans should flag `open()` calls outside context managers while excluding `with open(...)` usage; record exact file and line evidence so utility-script resource leaks are visible without broad lint dependencies. Source basis: Python Core Docs, OWASP secure coding review, Google Testing failure isolation.

## 2026-04-30: Python Static Top-Level Work Findings

- Python static hygiene scans should flag top-level executable work outside imports, definitions, constants, and `if __name__ == "__main__"` guards; record exact line evidence so import-time side effects in utility scripts are visible during review. Source basis: Python Core Docs, Google Engineering Practices maintainability review, OpenAI eval logging.

## 2026-04-30: Phase 1 Python Dependency Manifest Hygiene

- Python Phase 1 training should scan dependency manifests as first-class hygiene targets without installing packages or mutating lockfiles; classify unpinned `requirements.txt`, `pyproject.toml` project dependencies, and build-system requirements separately so dependency drift and build reproducibility risk are visible. Source basis: Python Testing and Packaging, NIST SSDF dependency protection, SLSA build reproducibility.

## 2026-04-30: Phase 1 Python Hardcoded Sensitive Constants

- Python static hygiene scans should detect hardcoded sensitive constants even in syntax-incompatible legacy files, while redacting literal values from evidence; record assignment target, file, line, rule, and severity so secrets/config issues are visible without leaking the secret into training logs. Source basis: OWASP secure coding review, NIST SSDF secret protection, Twelve-Factor config.

## 2026-04-30: Phase 1 Python Application File I/O Hygiene

- Phase 1 Python training should include application-code file I/O static targets, not only utility scripts; resource findings inside functions must preserve enclosing function context so unmanaged `open()` calls and path-handling boundaries are actionable. Source basis: Python Core Docs, OWASP secure file handling, Google Testing failure isolation.

## 2026-04-30: Phase 1 Python Caller-Controlled File Paths

- Phase 1 Python static scans should flag `open()` calls that use constructor-controlled path attributes, while classifying this as path-boundary evidence rather than proof of exploitable traversal; preserve assignment target, function, file, and line context. Source basis: OWASP secure file handling, NIST SSDF input-boundary review, Python Core Docs.

## 2026-04-30: Phase 1 Python Loop String Accumulation

- Phase 1 Python static scans should flag repeated string concatenation inside loops only when the accumulator is initialized as a string in the same function; report one finding per loop and accumulator to avoid noisy duplicate line findings. Source basis: Google Engineering Practices maintainability review, Python Core Docs, Google Testing failure isolation.

## 2026-04-30: Phase 1 Python Static Target Expansion

- Phase 1 target expansion should add independent target coverage for existing rules when the new target exercises a different code shape; promote only when the full batch remains satisfied and the new target artifact is logged. Source basis: Google Testing failure isolation, OpenAI eval logging, Anthropic clear success criteria.

## 2026-04-30: Phase 1 Python Hardwired Runtime Randomness

- Phase 1 Python static scans should flag direct runtime randomness in product methods as a testability and controllability boundary; de-duplicate multiple random calls on the same line and avoid claiming insecure randomness without security context. Source basis: Google Testing determinism, Google Engineering Practices maintainability review, Python Core Docs.

## 2026-04-30: Phase 1 Python Class State Mutation

- Phase 1 Python static scans should flag mutation of class-level or other non-self attributes inside functions as hidden shared state; preserve the exact mutated target and avoid escalating beyond maintainability/testability without contextual evidence. Source basis: Google Engineering Practices maintainability review, Google Testing determinism, Python Core Docs.

## 2026-05-04: HYG-032 Path Traversal Fixture

- Download, archive, static-file, and export helpers should decode caller-controlled path text, resolve/canonicalize against the intended root, and then enforce containment; string checks alone can miss encoded parent traversal or absolute-path escapes. Source basis: OWASP secure file operations, MITRE CWE path traversal, Python Core Docs structured path handling.

## 2026-05-21: Bounded Scratch Target Scope

- Bounded scratch targets: when an eval, fixture, package export, or user request explicitly limits scope to a subdirectory, scope status, diff, and discovery commands to that target instead of letting parent repository state expose or steer unrelated work. Source basis: Agent Evaluation Methodology trace/tool-call validity, Google Engineering Practices assigned-scope review.

## 2026-05-22: HYG-083 Config Precedence Controls

- Config/default/precedence fixes should test the intended winning source plus at least one absence or fallback control when the contract distinguishes defaults, files, environment variables, or overrides; otherwise the regression can prove only the reported key while missing the source-boundary contract. Source basis: Twelve-Factor config, Google Testing behavior coverage, Google Engineering Practices functionality review.
