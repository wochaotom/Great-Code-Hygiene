# Source Pack: OWASP Secure Coding Practices

- Source ID: `owasp-secure-coding`
- Activation: always
- Official link: https://owasp.org/www-project-secure-coding-practices-quick-reference-guide/

## Distilled Checks

- Validate input at trust boundaries using allowlists and type/range/format checks.
- Encode output in the correct context before rendering to browsers, shells, SQL, paths, logs, or external systems.
- Use safe authentication, password, session, access-control, and token handling.
- Use established cryptography correctly; avoid custom crypto and weak randomness.
- Protect secrets, credentials, PII, and sensitive business data in storage, transit, logs, errors, telemetry, and test fixtures.
- Use parameterized database access and safe query APIs.
- Constrain file operations to intended roots and safe names.
- Handle errors safely without leaking internals.
- Log security-relevant events with useful context and without sensitive values.
- Review memory/resource handling and unsafe APIs when applicable.

## PASS-100 Focus

`security`, `correctness`, `observability`, `tests`, `dependencies`
