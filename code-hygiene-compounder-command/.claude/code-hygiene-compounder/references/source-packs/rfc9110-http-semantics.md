# Source Pack: RFC 9110 HTTP Semantics

- Source ID: `rfc9110-http-semantics`
- Activation: HTTP protocol fields, clients, servers, proxies, adapters, and header/cookie handling
- Official link: https://www.rfc-editor.org/rfc/rfc9110
- Related cookie source: https://www.rfc-editor.org/rfc/rfc6265

## Distilled Checks

- Preserve HTTP field-line semantics when parsing, forwarding, adapting, or exposing headers.
- Combine repeated field lines only when the field definition allows list syntax without changing semantics.
- Treat `Set-Cookie` as a special repeated response field that cannot be comma-combined; keep separate values visible to cookie abstractions.
- Preserve field ordering when repeated field order is semantically relevant.
- Regression-test repeated-field cases with unrelated-header controls and ordinary single-field cases.

## PASS-100 Focus

`correctness`, `tests`, `local_integration`, `security`, `minimal_diff`
