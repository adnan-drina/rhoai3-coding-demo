# AGENTS.md

## Project identity

This repository is `rhoai3-coding-demo`.

It demonstrates a trusted enterprise AI development platform on Red Hat OpenShift AI. The demo shows how platform teams can provide private and governed AI coding assistance through OpenShift AI, Models-as-a-Service, OpenShift Dev Spaces, Continue, OpenCode, MTA, Developer Hub, and GitOps-managed platform components.

The main architectural idea is:

- Developers use familiar tools.
- Sensitive code can use private models on OpenShift.
- Approved external models can be exposed through a governed access layer.
- MaaS is the control point for identity, API keys, rate limits, quotas, telemetry, and model access.
- GitOps keeps platform state reproducible.

## Human accountability

AI tools may assist with this repository, but they do not own changes.

For every AI-assisted contribution:

- A human must review the full diff.
- A human must verify the commands, manifests, scripts, and documentation.
- A human must ensure no secrets, tokens, credentials, or private data are committed.
- A human must take responsibility for correctness, security, maintainability, and licensing.
- Material AI assistance must be disclosed in the PR.

AI agents must not add `Signed-off-by` trailers on behalf of humans.

## Repository map

Important paths:

- `README.md` — main workshop overview and architecture narrative.
- `BACKLOG.md` — known workarounds, limitations, planned work, and validated status.
- `env.example` — non-secret environment variable template.
- `scripts/` — bootstrap, shared helper scripts, validation utilities.
- `gitops/` — desired state for Argo CD and OpenShift resources.
- `gitops/argocd/app-of-apps/` — Argo CD application structure.
- `gitops/step-01-rhoai-platform/` — OpenShift AI platform foundation.
- `gitops/step-02-gpu-infra/` — GPU infrastructure.
- `gitops/step-03-llm-serving-maas/` — MaaS, model serving, gateways, governance, observability.
- `gitops/step-04-devspaces/` — Dev Spaces and AI coding assistant workspace setup.
- `gitops/step-05-mta/` — MTA and Developer Lightspeed.
- `gitops/step-06-developer-hub/` — Developer Hub.
- `steps/` — human-facing deployment walkthroughs and per-step deploy/validate scripts.
- `docs/` — operations, troubleshooting, architecture, and supporting documentation.

## Demo steps

The workshop is organized into six steps:

1. OpenShift AI platform
2. GPU infrastructure
3. MaaS, local/external models, model gateway, governance, and observability
4. Dev Spaces, Continue, and OpenCode
5. MTA and Developer Lightspeed
6. Developer Hub

When changing one step, check whether related changes are also needed in:

- `README.md`
- the step README
- `docs/OPERATIONS.md`
- `docs/TROUBLESHOOTING.md`
- `BACKLOG.md`
- GitOps manifests
- deploy or validate scripts

## Agent workflow

For non-trivial tasks, follow this workflow:

1. Read the relevant README, step docs, and manifests before editing.
2. State the intended change and affected files.
3. Make the smallest useful change.
4. Avoid broad refactors unless explicitly requested.
5. Update documentation in the same PR as behavior changes.
6. Run the narrowest validation command available.
7. If cluster validation is required but unavailable, state exactly what could not be validated.
8. Produce a PR summary with risks, rollback notes, and validation evidence.

## Coding and manifest style

General rules:

- Prefer clear, boring, maintainable changes.
- Preserve the step-based workshop structure.
- Preserve GitOps idempotency.
- Prefer Kustomize overlays and existing patterns over one-off scripts.
- Do not introduce new tools unless the reason is documented.
- Do not rename resources casually; OpenShift and Argo CD resources may depend on names.
- Keep comments where they explain operational intent or known platform quirks.
- Do not remove workaround documentation unless the replacement behavior has been validated.

Shell scripts:

- Use `set -euo pipefail` where practical.
- Quote variables.
- Keep scripts repeatable.
- Prefer explicit error messages.
- Do not assume a specific cluster name unless documented.
- Avoid destructive commands unless clearly labeled and confirmed by the user.

YAML and Kubernetes manifests:

- Preserve namespaces, labels, annotations, sync waves, and Argo CD ordering unless the task explicitly requires changes.
- Check RBAC, NetworkPolicy, AuthPolicy, RateLimitPolicy, and TokenRateLimitPolicy changes carefully.
- Treat gateway, auth, model access, and credential-related manifests as security-sensitive.
- Do not place real credentials in Git.

Documentation:

- Keep the workshop useful for readers who do not have the original author present.
- Explain why a step exists, not only how to run it.
- Update troubleshooting when changing deployment behavior.
- Update `BACKLOG.md` when adding, resolving, or changing workarounds.

## Security and privacy

Never commit:

- API keys
- OpenShift tokens
- kubeconfigs
- Hugging Face tokens
- OpenAI or external model provider keys
- private cluster URLs if they are not intended for publication
- real user passwords
- customer data
- internal/private source code from another project

Use placeholders in examples.

Sensitive areas include:

- MaaS auth and API key handling
- Authorino and Kuadrant policies
- Gateway routing
- RBAC
- NetworkPolicy
- OpenShift OAuth and identity configuration
- External model credentials
- Dev Spaces workspace configuration
- MCP integrations

For these areas, include explicit validation notes in the PR.

## Validation expectations

Use the most specific validation possible.

Examples:

```bash
bash -n scripts/*.sh
bash -n steps/*/*.sh

./steps/step-01-rhoai-platform/validate.sh
./steps/step-02-gpu-infra/validate.sh
./steps/step-03-llm-serving-maas/validate.sh
./steps/step-04-devspaces/validate.sh
./steps/step-05-mta/validate.sh
./steps/step-06-developer-hub/validate.sh
```

If validation requires a live OpenShift cluster and one is not available, do not pretend validation passed. Say:

> Not validated against a live cluster. Static review only.

## Shared skills

This repository includes shared skills for repeatable project workflows:

| Skill | Purpose |
|-------|---------|
| `review-gitops-change` | Review GitOps and manifest changes for safety and completeness |
| `validate-demo-step` | Validate a step after changes with static and live checks |
| `update-demo-docs` | Check documentation consistency after behavior changes |
| `prepare-pr-summary` | Generate a PR summary following the project template |
| `workaround-review` | Review workaround status before modifying or removing |
| `demo-operations-docs` | Maintain OPERATIONS.md and TROUBLESHOOTING.md |
| `rhoai-troubleshoot` | Diagnose and fix live cluster failures |
| `manage-devspaces` | Manage Dev Spaces workspaces |

Skills are invoked workflows. Rules are always-on behavior constraints. See [docs/AI_COLLABORATION.md](docs/AI_COLLABORATION.md) for the full governance model.

## AI prompt discipline

When using Cursor Agent, Claude, GPT, Continue, or OpenCode:

- Provide the task, acceptance criteria, and relevant files.
- Ask for a plan before large edits.
- Ask the agent to keep changes minimal.
- Ask the agent to explain validation steps.
- Review the full diff manually.
- Reject changes that are plausible but not grounded in this repo.

## Pull request output expected from agents

When asked to prepare a PR summary, use this format:

```markdown
## Summary
## Why
## Changed files
## Validation
## Risk
## Rollback
## AI assistance
Tool/model used:
Human review performed:
```
