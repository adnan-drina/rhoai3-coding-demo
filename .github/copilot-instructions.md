# GitHub Copilot Instructions

This repository is `rhoai3-coding-demo` — a trusted enterprise AI development platform demo on Red Hat OpenShift AI.

For detailed agent guidance, see:

- [AGENTS.md](../AGENTS.md) — tool-neutral agent contract (repo map, workflow, security, validation)
- [.cursor/rules/](../.cursor/rules/) — Cursor-specific behavior rules (GitOps, manifests, docs, security)
- [docs/AI_COLLABORATION.md](../docs/AI_COLLABORATION.md) — rules/skills governance model and hook documentation

## Key rules

- Read the relevant step README and manifests before editing.
- Keep changes small and focused.
- Preserve GitOps idempotency and Argo CD sync waves.
- Do not bypass MaaS unless explicitly documented.
- Do not commit secrets, tokens, or real credentials.
- Do not remove workarounds without checking `BACKLOG.md`.
- Update docs when changing behavior.
- Use `set -euo pipefail` in shell scripts.
- Use existing Kustomize patterns over new conventions.

## Validation

```bash
bash -n scripts/*.sh
bash -n steps/*/*.sh
./steps/step-XX-*/validate.sh
```

## Security-sensitive areas

Treat changes to these as high-risk: MaaS gateway, Authorino, Kuadrant, RBAC, NetworkPolicy, API keys, ExternalModel credentials, Dev Spaces permissions, MCP permissions.
