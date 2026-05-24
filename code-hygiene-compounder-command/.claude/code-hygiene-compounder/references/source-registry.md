# Source Registry

Phase R locks the authoritative source corpus before heavy training. The skill compounds against distilled principles from this registry, not against a growing pile of ad hoc advice.

## Core Corpus

`source-weights.json` controls when each source pack is loaded. Only general code-health and test-feedback sources should be loaded for every audit. Security-heavy sources remain core authorities, but source-grounded audits should activate them explicitly for security-sensitive work instead of pulling them into every docs/readability task.

| Source | Authority | Use For | Contribution |
| --- | --- | --- | --- |
| Google Engineering Practices | Google engineering documentation | Code review, change size, readability, tests, documentation, code health | Make every change preserve or improve code health while allowing progress. |
| Google Testing Blog: testing pyramid | Google Testing Blog | Test strategy and feedback-loop design | Prefer fast, reliable, failure-isolating tests; avoid overreliance on slow end-to-end tests. |
| NIST SSDF SP 800-218 | U.S. NIST | Secure development lifecycle | Reduce vulnerabilities, mitigate impact, and prevent recurrence through lifecycle practices. |
| OWASP Secure Coding Practices | OWASP Foundation | General secure coding | Cover input validation, output encoding, auth, access control, crypto, error handling, logging, data protection, database, file, memory, and general coding practices. |
| OWASP ASVS | OWASP Foundation | Web application security verification | Use measurable security requirements and verification rigor for web apps. |
| CISA Secure by Design | CISA and international partners | Secure defaults and product accountability | Shift security burden from users to producers; prioritize secure defaults, transparency, and ownership. |
| Microsoft SDL | Microsoft Security Engineering | Threat modeling, secure verification, release and response | Integrate security/privacy through requirements, design, implementation, verification, release, and response. |
| MITRE CWE Top 25 | MITRE CWE program | Real-world weakness weighting | Prioritize common, impactful weakness classes such as XSS, SQL injection, CSRF, authz, path traversal, memory errors, command injection, and code injection. |
| SEI CERT Secure Coding Standards | Carnegie Mellon SEI CERT | Language-specific safety and secure coding | Use normative rules and recommendations for C, C++, Java, Android, Perl, and related secure coding domains. |

## Conditional Core

| Source | Apply When | Contribution |
| --- | --- | --- |
| Google Style Guides | Local style is unclear or a Google-originated language/project is being touched | Prefer clarity, simplicity, concision, maintainability, and consistency. |
| Google Developer Documentation Style Guide | Developer-facing documentation, README/API docs, procedures, examples, link text, and docs accessibility | Write docs that are task-oriented, scannable, accurate, accessible, and easy for global developer readers. |
| Python Core Docs and PEPs | Python source files, scripts, CLIs, libraries, path/process/error handling, typing, or docstrings are involved | Apply Python-specific hygiene for exceptions, cleanup, path APIs, subprocess security, naming, style fallback, and useful docstrings. |
| Python Testing and Packaging | Python tests, pytest usage, package layout, `pyproject.toml`, dependency groups, extras, or build metadata are involved | Keep tests behavior-focused and import-realistic; keep packaging metadata and tool configuration coherent with modern Python packaging. |
| Twelve-Factor App | App config, deploys, environment variables, credentials, or service handles are involved | Separate deploy-varying config from code; never hard-code secrets or environment-specific values. |
| SLSA | Build, release, artifact provenance, packaging, or supply-chain integrity is involved | Improve artifact integrity with provenance, hosted/hardened builds, and tamper-resistant release practices. |
| OpenSSF Scorecard | Open-source dependency/project health or repository security posture is involved | Use automated checks and risk-weighted scoring for project security health. |
| OpenTelemetry | Observability, logging, metrics, traces, or distributed debugging is involved | Prefer vendor-neutral telemetry; correlate logs, metrics, and traces when useful. |
| W3C WCAG 2.2 | Web UI, frontend interaction, forms, content, or accessibility-sensitive changes are involved | Ensure web content is perceivable, operable, understandable, and robust using testable success criteria. |
| Microsoft REST API Guidelines | REST API surface, versioning, error shape, pagination, or compatibility is involved | Keep APIs consistent, evolvable, documented, and predictable for consumers. |
| RFC 9110 HTTP Semantics | HTTP field parsing, forwarding, adapters, client/server libraries, proxies, or protocol compatibility is involved | Preserve HTTP field semantics, including repeated field-line behavior and exceptions such as `Set-Cookie` that cannot be comma-combined. |
| Semantic Versioning | Public packages, libraries, plugins, SDKs, or released APIs are involved | Communicate compatibility through major, minor, and patch version increments. |
| LLM Provider Tool and Structured Output Documentation | Provider-facing tool calling, structured outputs, AI SDK schema adapters, MCP bridges, or model/API schema compatibility is involved | Treat provider schemas as interface contracts; keep canonical schemas separate, compile to the supported provider subset, and verify adapters with local canaries. |
| NASA/JPL Power of Ten | Safety-critical, embedded, firmware, high-reliability C/C++, or hard real-time code is involved | Favor simple control flow, bounded loops, restricted dynamic allocation, small functions, assertions, narrow scope, checked returns, limited preprocessor/pointers, and zero warnings. |

## Evaluation Sources

| Source | Use For | Contribution |
| --- | --- | --- |
| Agent Evaluation Methodology: OpenAI eval best practices, Anthropic empirical evals, and Agent GPA | Agent training, eval-loop design, and trace-aware agent scoring | Use representative tasks, clear success criteria, logged grading, automated and human-calibrated judges, and goal-plan-action trace checks for plan, tool, action, and failure-localization issues. |

## Source Admission Rules

- Add new sources only if they are official, standards-based, primary, or widely recognized engineering guidance from a credible institution.
- Classify every source before it can affect training: always-on, explicit-security, conditional, language-specific, safety-critical, supply-chain, frontend, observability, documentation, or eval-methodology.
- Do not let a conditional source override the always-on core outside its scope.
- Quarantine newly found sources until their contribution is distilled into `hygiene-principles.md` and weighted in `source-weights.json`.
- Reject sources that mostly repeat existing guidance unless they add measurable coverage or a better verification hook.

## Verified Source Links

- Google Engineering Practices: https://google.github.io/eng-practices/
- Google code review standard: https://google.github.io/eng-practices/review/reviewer/standard.html
- Google code review checklist: https://google.github.io/eng-practices/review/reviewer/looking-for.html
- Google Testing Blog, testing pyramid: https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html
- Google Style Guides: https://google.github.io/styleguide/
- Google Developer Documentation Style Guide: https://developers.google.com/style/highlights
- Google Developers Site Policies: https://developers.google.cn/terms/site-policies?hl=en
- NIST SSDF SP 800-218 final: https://csrc.nist.gov/pubs/sp/800/218/final
- NIST SSDF SP 800-218 Rev. 1 initial public draft: https://csrc.nist.gov/pubs/sp/800/218/r1/ipd
- OWASP Secure Coding Practices: https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/
- OWASP ASVS: https://owasp.org/www-project-application-security-verification-standard/
- OWASP Cheat Sheet Series: https://owasp.org/www-project-cheat-sheets/
- CISA Secure by Design: https://www.cisa.gov/resources-tools/resources/secure-by-design
- Microsoft SDL: https://www.microsoft.com/en-us/securityengineering/sdl
- Microsoft SDL assurance overview: https://learn.microsoft.com/en-us/compliance/assurance/assurance-microsoft-security-development-lifecycle
- MITRE CWE Top 25: https://cwe.mitre.org/top25/
- SEI CERT Secure Coding Standards: https://wiki.sei.cmu.edu/confluence/spaces/seccode/overview
- Python tutorial, errors and exceptions: https://docs.python.org/3/tutorial/errors.html
- Python pathlib: https://docs.python.org/3/library/pathlib.html
- Python subprocess security considerations: https://docs.python.org/3/library/subprocess.html#security-considerations
- PEP 8 style guide: https://peps.python.org/pep-0008/
- PEP 257 docstring conventions: https://peps.python.org/pep-0257/
- pytest good integration practices: https://docs.pytest.org/en/latest/explanation/goodpractices.html
- Python Packaging User Guide, writing pyproject.toml: https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
- Python Packaging User Guide, tool recommendations: https://packaging.python.org/en/latest/guides/tool-recommendations/
- SLSA: https://slsa.dev/
- SLSA specification: https://slsa.dev/spec/
- OpenSSF Scorecard: https://openssf.org/projects/scorecard/
- Twelve-Factor App config: https://www.12factor.net/config
- OpenTelemetry documentation: https://opentelemetry.io/docs/
- W3C WCAG overview: https://www.w3.org/WAI/standards-guidelines/wcag/
- Microsoft REST API Guidelines: https://github.com/microsoft/api-guidelines
- RFC 9110 HTTP Semantics: https://www.rfc-editor.org/rfc/rfc9110
- RFC 6265 HTTP State Management Mechanism: https://www.rfc-editor.org/rfc/rfc6265
- Semantic Versioning: https://semver.org/
- OpenAI function calling and structured outputs: https://developers.openai.com/api/docs/guides/function-calling
- Anthropic tool use overview: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/overview
- Anthropic tool definition docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools
- Anthropic strict tool use docs: https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use
- Gemini function calling: https://ai.google.dev/gemini-api/docs/function-calling
- Gemini structured output: https://ai.google.dev/gemini-api/docs/structured-output
- NASA/JPL Power of Ten reference: https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20120001915.pdf
- OpenAI eval best practices: https://developers.openai.com/api/docs/guides/evaluation-best-practices
- Anthropic empirical evals: https://docs.anthropic.com/en/docs/test-and-evaluate/develop-tests
- Agent GPA paper: https://arxiv.org/abs/2510.08847
- Snowflake Agent GPA engineering write-up: https://www.snowflake.com/en/blog/engineering/ai-agent-evaluation-gpa-framework/
