# Source Pack: Google Testing

- Source ID: `google-testing`
- Activation: always
- Official link: https://testing.googleblog.com/2015/04/just-say-no-to-more-end-to-end-tests.html

## Distilled Checks

- Prefer fast, reliable, failure-isolating tests for most coverage.
- Use end-to-end tests sparingly for paths that truly require whole-system verification.
- Avoid brittle tests that fail far from the root cause or require excessive maintenance.
- Favor behavior assertions over implementation details or broad snapshots.
- Add tests at the narrowest level that proves the risk.
- Keep tests readable, deterministic, and useful to future maintainers.

## PASS-100 Focus

`tests`, `correctness`, `maintainability`
