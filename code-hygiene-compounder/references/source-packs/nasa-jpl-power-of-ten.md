# Source Pack: NASA/JPL Power of Ten

- Source ID: `nasa-jpl-power-of-ten`
- Activation: safety-critical only
- Official link: https://ntrs.nasa.gov/archive/nasa/casi.ntrs.nasa.gov/20120001915.pdf

## Distilled Checks

- Activate only for embedded, firmware, hard real-time, high-reliability, or safety-critical code.
- Favor simple control flow and avoid unbounded recursion or dynamic dispatch surprises where prohibited by local rules.
- Bound loops and memory use.
- Keep functions small and analyzable.
- Check return values and assertions for critical assumptions.
- Prefer static analysis and zero-warning builds when the domain requires it.
- Do not impose these constraints on ordinary web/app code unless the repo already follows them.

## PASS-100 Focus

`correctness`, `security`, `maintainability`, `tests`
