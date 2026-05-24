# Source Pack: SLSA

- Source ID: `slsa`
- Activation: build, release, or supply chain
- Official link: https://slsa.dev/spec/

## Distilled Checks

- For build/release changes, consider source integrity, build integrity, provenance, and artifact verification.
- Prefer scripted, reproducible, tamper-resistant build paths.
- Avoid unchecked generated artifacts and unclear release provenance.
- Verify dependency/build tooling changes for supply-chain risk.
- Record artifact provenance or verification limits where relevant.

## PASS-100 Focus

`dependencies`, `security`, `agent_process`
