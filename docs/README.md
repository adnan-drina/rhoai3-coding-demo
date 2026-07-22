# Documentation Index

This directory holds operational and governance documentation for the Red Hat OpenShift AI coding demo. The root README and stage READMEs explain the learning path; these docs hold the runbooks, validation notes, and contribution rules that would make those READMEs too operational.

| Document | Purpose |
|----------|---------|
| [index.md](index.md) | Published TechDocs landing page for the developer workspace guide |
| [OPERATIONS.md](OPERATIONS.md) | Deployment order, bootstrap behavior, validation strategy, GitOps operations, day-2 notes, and cleanup guidance |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptom-based diagnostics and recovery commands |
| [DEVELOPER_WORKSPACE_GUIDE.md](DEVELOPER_WORKSPACE_GUIDE.md) | TechDocs guide for Developer Hub, Dev Spaces, Kilo Code, MaaS, and Stage 060 coding exercise |
| [../BACKLOG.md](../BACKLOG.md) | Workarounds, known limitations, validation notes, and planned cleanup |

## Learning Path

The implemented flow is defined in [`../flows/default.yaml`](../flows/default.yaml):

1. [Project README](../README.md)
2. [Stage 010: OpenShift AI Platform Foundation](../stages/010-openshift-ai-platform-foundation/README.md)
3. [Stage 020: GPU Infrastructure for Private AI](../stages/020-gpu-infrastructure-private-ai/README.md)
4. [Stage 030: Private Model Serving](../stages/030-private-model-serving/README.md)
5. [Stage 040: Governed Models-as-a-Service](../stages/040-governed-models-as-a-service/README.md)
6. [Stage 050: Advanced Application Platform](../stages/050-advanced-app-platform/README.md)
7. [Stage 060: AI-Assisted Development](../stages/060-ai-assisted-development/README.md)
8. [Stage 070: AI-Agentic Development](../stages/070-ai-agentic-development/README.md)
9. [Stage 080: AI-Autonomous Migration](../stages/080-ai-autonomous-migration/README.md)

[Stage 060](../stages/060-ai-assisted-development/README.md) starts the developer-facing part of the workshop. It uses the Stage 060 workspace and Stage 050 portal assets to teach governed vibe coding, prompt discipline, review gates, and evidence capture. The former Stage 110 spec and README-alignment placeholder has been merged into Stage 060. Deferred developer workflow topics `120-170` are tracked in [BACKLOG.md](../BACKLOG.md) until each one has a concrete implementation plan, artifacts, and validation path.

## AI Collaboration Rules

Shared rules, skills, and agent definitions live under [`../.agents/`](../.agents/). They define project-wide AI agent behavior. Do not commit local rules, skills, credentials, personal paths, private cluster URLs, or personal preferences. See [CONTRIBUTING.md](../CONTRIBUTING.md) before changing shared agent behavior.

Claims in user-facing documentation must stay aligned with manifests, scripts, validation checks, and official product documentation.
