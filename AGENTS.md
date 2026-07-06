# AGENTS.md

## Project identity

This repository is `rhoai3-coding-demo`.

It demonstrates a trusted enterprise AI development platform on Red Hat OpenShift AI. The demo shows how platform teams can provide private and governed AI coding assistance through Red Hat OpenShift AI, Models-as-a-Service, Red Hat OpenShift Dev Spaces, Continue, OpenCode, Migration Toolkit for Applications (MTA), Red Hat Developer Hub, and GitOps-managed platform components.

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
- `flows/default.yaml` — ordered source of truth for the demo flow.
- `gitops/stages/` — desired state for stage-specific OpenShift resources.
- `stages/` — human-facing deployment walkthroughs and per-stage deploy/validate scripts.
- `docs/` — operations, troubleshooting, architecture, and supporting documentation.
- `.agents/` — shared tool-neutral agent guidance (rules, skills, hooks, references).

## Demo stages

The workshop has two parts:

- Stages 010-070 build the trusted AI development platform for platform engineers.
- Stages 080 and later show enterprise developer workflows that consume that platform.

Current implemented stages:

1. 010 OpenShift AI Platform Foundation
2. 020 GPU Infrastructure for Private AI
3. 030 Private Model Serving
4. 040 Governed Models-as-a-Service
5. 050 Controlled Developer Workspaces
6. 060 AI-Assisted Application Modernization
7. 070 Developer Portal and Self-Service
8. 080 Governed Vibe Coding With Continue

The stages renumbered when stage 040 absorbed the former external-model and
MCP stages during the rhoai3-demo foundation import: 070/080/090/100 became
050/060/070/080.

Developer workflow stages after 080 are deferred until each has a concrete
implementation plan and validation path.

When changing one stage, check whether related changes are also needed in:

- `README.md`
- the stage README
- `docs/OPERATIONS.md`
- `docs/TROUBLESHOOTING.md`
- `BACKLOG.md`
- GitOps manifests
- deploy or validate scripts

## Detailed Rules

For project structure, coding discipline, change conventions, and shared agent
guidance, read `.agents/rules/project.md`.

For live demo environment deployment, secrets, certs, and cluster safety, read
`.agents/rules/env.md`.

For GitOps authoring, manifests, labels, and schema validation, read
`.agents/rules/gitops.md`.

For documentation standards, README structure, and operations docs, read
`.agents/rules/docs.md`.

## OpenShift Safety Guard

- Open this repository as its own project; do not open `/Users/adrina/Sandbox`
  as the active project for live cluster work.
- Before running live `oc`/`kubectl` commands, call `load_env` and
  `check_oc_logged_in` from `scripts/lib.sh`.
- Set `RHOAI_EXPECTED_API_SERVER` in the local `.env` to a unique target
  API-server substring before deploy, validate, bootstrap, or
  resource-management scripts run.
- Do not bypass the guard with `RHOAI_ALLOW_UNGUARDED_CLUSTER=true` unless the
  user explicitly confirms the current cluster and the command is low risk.

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
- Red Hat OpenShift Dev Spaces workspace configuration
- MCP integrations

For these areas, include explicit validation notes in the PR.

## Agent workflow

For non-trivial tasks, follow this workflow:

1. Read the relevant README, stage docs, and manifests before editing.
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
- Preserve the stage-based workshop structure.
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

YAML and Kubernetes manifests:

- Preserve namespaces, labels, annotations, sync waves, and Argo CD ordering unless the task explicitly requires changes.
- Check RBAC, NetworkPolicy, AuthPolicy, RateLimitPolicy, and TokenRateLimitPolicy changes carefully.
- Treat gateway, auth, model access, and credential-related manifests as security-sensitive.
- Do not place real credentials in Git.

## Shared Skills

Canonical skills live in `.agents/skills/`, the shared tool-neutral skill
discovery path. Keep skill folders flat and use the prefix plus
`metadata.skill-group` taxonomy for skill review:

| Group | Skills | Purpose |
|-------|--------|---------|
| Project Structure | `maintain-rules-and-skills`, `prepare-pr-summary`, `project-demo-stage-authoring` | Governance, PR output, stage lifecycle |
| GitOps & Manifests | `review-gitops-change` | Review changes, explain risk |
| Documentation | `update-demo-docs`, `demo-operations-docs`, `project-documentation-authoring`, `project-architecture-diagrams` | Keep docs aligned, author READMEs, maintain diagrams |
| Demo Environment | `validate-demo-step`, `rhoai-troubleshoot`, `manage-devspaces`, `manage-resources`, `resume-gpu-demo`, `run-guidellm-load-test`, `workaround-review` | Deploy, validate, diagnose, scale |
| Assets & Miscellaneous | `red-hat-quick-deck` | Red Hat-aligned presentations |

Skills are invoked workflows. Rules are always-on behavior constraints.

## Subagents

No shared subagents are currently tracked. Add tool-specific subagents only for
genuinely tool-specific context isolation needs; shared workflows belong in
`.agents/skills/`.

## Validation expectations

Use the most specific validation possible.

Examples:

```bash
bash -n scripts/*.sh
bash -n stages/*/*.sh
./scripts/validate-stage-flow.sh

./stages/010-openshift-ai-platform-foundation/validate.sh
./stages/020-gpu-infrastructure-private-ai/validate.sh
./stages/030-private-model-serving/validate.sh
./stages/040-governed-models-as-a-service/validate.sh
./stages/050-controlled-developer-workspaces/validate.sh
./stages/060-ai-assisted-application-modernization/validate.sh
./stages/070-developer-portal-self-service/validate.sh
```

Stage 080 currently consumes Stage 050 Dev Spaces and Stage 070 Developer Hub
assets. It does not have a standalone deploy or validate script; validate its
documentation changes with `./scripts/validate-stage-flow.sh` and any specific
commands documented in the Stage 080 README when a live workspace and cluster
are available.

If validation requires a live OpenShift cluster and one is not available, do not pretend validation passed. Say:

> Not validated against a live cluster. Static review only.

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
