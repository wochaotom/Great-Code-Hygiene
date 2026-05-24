# Source Pack: Google Developer Documentation Style Guide

- Source ID: `google-developer-docs-style`
- Activation: developer_documentation
- Official links:
  - https://developers.google.com/style/highlights
  - https://developers.google.cn/terms/site-policies?hl=en
- License note: Google Developers pages carrying the standard notice license content under CC BY 4.0 and code samples under Apache 2.0; attribution is required and trademarks/media may be excluded.

## Distilled Checks

- For README, API, setup, troubleshooting, deprecation, and usage docs, make the reader's task, prerequisites, sequence, and expected result easy to scan.
- Use descriptive headings and link text; avoid vague links, stale future claims, and wording that forces readers to infer context.
- Put conditions before instructions, use numbered lists for sequences, and use bullets or description lists for non-sequential information.
- Keep code-related text, flags, commands, paths, and UI labels formatted distinctly and consistently with the local docs style.
- Keep examples minimal, current, runnable where feasible, and consistent with the current public API or setup path.
- Consider accessibility and global readers: prefer text over images of text/code, provide alt text when images matter, and avoid ambiguous dates or idioms.
- Update or remove docs when behavior, setup, API, flags, or examples change; avoid unrelated wording churn in functional changes.

## PASS-100 Focus

`documentation`, `maintainability`, `local_integration`, `minimal_diff`, `correctness`
