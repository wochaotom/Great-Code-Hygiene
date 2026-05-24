# Source Pack: MITRE CWE Top 25

- Source ID: `mitre-cwe-top25`
- Activation: always
- Official link: https://cwe.mitre.org/top25/

## Distilled Checks

- Prioritize common, impactful weakness classes when reviewing security-sensitive code.
- Check for injection, cross-site scripting, out-of-bounds access, improper auth/authz, path traversal, deserialization, command injection, code injection, resource exhaustion, and missing validation.
- Prefer root-cause fixes that eliminate a weakness class rather than patching one symptom.
- For security findings, name the weakness class when it helps explain risk.
- Use CWE weighting to raise priority for issues that are both common and exploitable.

## PASS-100 Focus

`security`, `correctness`, `tests`
