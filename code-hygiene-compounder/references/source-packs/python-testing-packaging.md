# Source Pack: Python Testing and Packaging

- Source ID: `python-testing-packaging`
- Activation: python_tests_or_package
- Official links:
  - https://docs.pytest.org/en/latest/explanation/goodpractices.html
  - https://packaging.python.org/en/latest/guides/writing-pyproject-toml/
  - https://packaging.python.org/en/latest/guides/tool-recommendations/

## Distilled Checks

- Prefer tests that import the installed/importable package the same way users and tools will.
- Keep test layout, import mode, fixtures, and temporary files aligned with pytest good practices and local convention.
- Make tests behavior-focused and failure-isolating; avoid tests that only bless current output or implementation details.
- Use fixtures for reusable setup while keeping data dependencies visible and understandable.
- Keep test state isolated; avoid relying on test order, global mutation, current working directory, network, or real credentials unless explicitly marked.
- Put packaging metadata, build-system requirements, entry points, optional dependencies, and tool config in `pyproject.toml` when the project uses modern packaging.
- Check that runtime dependencies, dev dependencies, extras, lockfiles, and tool versions match the repository's packaging model.
- Avoid adding new packaging tools, runners, or config files unless they solve a concrete gap and fit the repo.
- Verify Python package changes with the narrowest meaningful command first, then broader test/build checks when packaging or public imports move.

## PASS-100 Focus

`tests`, `dependencies`, `correctness`, `local_integration`, `documentation`, `minimal_diff`, `agent_process`
