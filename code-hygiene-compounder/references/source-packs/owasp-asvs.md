# Source Pack: OWASP ASVS

- Source ID: `owasp-asvs`
- Activation: web or API security
- Official link: https://owasp.org/www-project-application-security-verification-standard/

## Distilled Checks

- For web apps and APIs, verify security controls against measurable requirements rather than broad intent.
- Check encoding/sanitization, injection prevention, authentication, session management, access control, validation, and secure configuration.
- Use the current stable ASVS 5.0.0 requirement set and include identifiers in
  the form `v5.0.0-x.y.z` in high-rigor security reports when possible.
- Prefer verification evidence: tests, configuration checks, code inspection, or tool output.
- Use ASVS when confidence in web application security controls matters, especially for auth, data, and trust-boundary changes.

## PASS-100 Focus

`security`, `tests`, `correctness`, `documentation`
