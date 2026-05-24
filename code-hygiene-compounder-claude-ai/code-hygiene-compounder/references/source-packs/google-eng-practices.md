# Source Pack: Google Engineering Practices

- Source ID: `google-eng-practices`
- Activation: always
- Official links:
  - https://google.github.io/eng-practices/review/reviewer/standard.html
  - https://google.github.io/eng-practices/review/reviewer/looking-for.html

## Distilled Checks

- Review for overall code health improvement, not perfection.
- Check design fit: does the change belong here, integrate with the system, and avoid unnecessary architecture?
- Check functionality for intended behavior, user/developer impact, edge cases, concurrency, race/deadlock risks, and UI impact.
- Penalize excess complexity at line, function, class, and system levels.
- Reject speculative generality and features not presently needed.
- Require appropriate unit, integration, or end-to-end tests in the same change unless it is an emergency.
- Check that tests are sensible, useful, maintainable, and would fail when behavior breaks.
- Check names for clarity without excessive length.
- Prefer comments that explain why; simplify code instead of commenting obvious what.
- Keep style changes separate from functional changes.
- Prefer local consistency unless the style guide or code health says otherwise.
- Update docs when users build, test, interact with, release, or reason differently.
- Review every human-written line in assigned scope or state the reviewed scope.

## PASS-100 Focus

`correctness`, `tests`, `maintainability`, `local_integration`, `minimal_diff`, `documentation`, `agent_process`
