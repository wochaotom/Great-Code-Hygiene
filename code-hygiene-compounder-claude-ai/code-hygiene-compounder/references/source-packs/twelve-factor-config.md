# Source Pack: Twelve-Factor Config

- Source ID: `twelve-factor-config`
- Activation: config or deploy
- Official link: https://www.12factor.net/config

## Distilled Checks

- Keep deploy-varying config separate from code.
- Treat credentials, resource handles, canonical hostnames, regions, ports, and per-deploy values as config.
- Prefer environment variables or the repo's established secure configuration mechanism.
- Do not check secrets or local-only config into source control.
- Distinguish deploy-varying config from internal application wiring that belongs in code.
- Avoid brittle environment groupings when granular orthogonal config is possible.

## PASS-100 Focus

`dependencies`, `security`, `local_integration`, `documentation`
