# Contributing to rhoai3-coding-demo

This repository is maintained by a small team of human developers using Cursor IDE with Claude models. AI assistance is welcome, but human contributors remain responsible for all changes.

For the full AI collaboration model including rules/skills governance, local vs shared boundaries, and promotion workflows, see [docs/AI_COLLABORATION.md](docs/AI_COLLABORATION.md).

## Contribution Workflow

1. Create or select an issue with clear acceptance criteria.
2. Ask the AI agent for a short plan and review it.
3. Let the agent make a focused change.
4. Review the full diff manually — check for secrets, licensing, and correctness.
5. Run relevant validation.
6. Open a pull request with AI disclosure.
7. Merge only after risk and validation are clear.

## Pull Requests

Every PR must include: a summary, reason for the change, validation evidence, risk assessment, rollback notes, and AI assistance disclosure.

AI disclosure format:

```text
AI assistance: <tool/model used or "none">
Scope: <planning, code edits, documentation, troubleshooting, or validation>
Human review: full diff reviewed by <name>
Validation: <commands run or "static review only">
```

## Branch And Commit Style

Branches: `docs/update-readme`, `fix/stage-040-validation`, `feat/stage-060-workspace-config`

Commits: conventional format `type(scope): description` — types are `feat`, `fix`, `docs`, `refactor`, `chore`, `ci`. Use the stage number for stage-specific changes, component name for cross-cutting changes. Keep subject lines under 72 characters.

## Validation

Use the most specific validation available.

```bash
bash -n scripts/*.sh
bash -n stages/*/*.sh
./scripts/validate-stage-flow.sh
```

For stage changes with a live cluster:

```bash
./stages/010-openshift-ai-platform-foundation/validate.sh
./stages/020-gpu-infrastructure-private-ai/validate.sh
./stages/030-private-model-serving/validate.sh
./stages/040-governed-models-as-a-service/validate.sh
./stages/050-advanced-app-platform/validate.sh
./stages/060-ai-assisted-development/validate.sh
./stages/070-ai-agentic-development/validate.sh
./stages/080-ai-autonomous-migration/validate.sh
```

If live validation is not possible, say: "Not validated against a live OpenShift cluster. Static review only."

## Security

Never commit tokens, kubeconfigs, real passwords, private keys, cloud credentials, model provider API keys, or private customer data. Use `env.example` for placeholders and `.env` for local values. `.env` must not be committed.

## Demo Integrity

This repository teaches a governed enterprise AI platform pattern. Do not make changes that weaken the central story:

- Model access should go through MaaS
- Private and external model paths must remain clearly distinguished
- GitOps should remain the source of truth
- Documentation should explain both platform value and operational steps
- Workarounds should be tracked in `BACKLOG.md` until they are truly resolved

## Sensitive Areas Requiring Review

For these areas, require review from another person even if the team is small:

- MaaS gateway routing and API key handling
- Authorino and Kuadrant policies
- RBAC and NetworkPolicy
- External model credentials
- Red Hat OpenShift Dev Spaces workspace permissions
- MCP integrations and tool-context boundaries
