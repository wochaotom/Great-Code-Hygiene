# Source Pack: Python Core Docs and PEPs

- Source ID: `python-core-docs`
- Activation: python_language
- Official links:
  - https://docs.python.org/3/tutorial/errors.html
  - https://docs.python.org/3/library/pathlib.html
  - https://docs.python.org/3/library/subprocess.html#security-considerations
  - https://peps.python.org/pep-0008/
  - https://peps.python.org/pep-0257/

## Distilled Checks

- Prefer local project style first; use PEP 8 only when local style is missing or inconsistent.
- Check function, class, module, and variable names for clarity and Python convention fit.
- Keep docstrings useful for public modules, functions, classes, and non-obvious behavior; avoid comments that repeat obvious code.
- Handle exceptions specifically; avoid broad catches unless they log or add context and re-raise intentionally.
- Use `else`, `finally`, context managers, and cleanup actions when they make error boundaries clearer.
- Prefer `pathlib` or structured path APIs over ad hoc string-built paths.
- Treat file paths, archive members, dynamic imports, deserialization, and generated code as trust-boundary inputs.
- Prefer subprocess argument lists; treat `shell=True`, string-built commands, inherited environment, and untrusted arguments as security-sensitive.
- Keep module import side effects small and explicit; avoid hidden work at import time unless the project convention requires it.
- Use type hints where they clarify contracts or catch common mistakes; do not add annotation noise that fights the local codebase.

## PASS-100 Focus

`correctness`, `security`, `maintainability`, `local_integration`, `observability`, `minimal_diff`, `documentation`
