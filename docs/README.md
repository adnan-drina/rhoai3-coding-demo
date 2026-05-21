# Documentation Index

This directory holds operational and governance documentation for the Red Hat OpenShift AI coding demo. The root README and stage READMEs explain the learning path; these docs hold the runbooks, validation notes, and contribution rules that would make those READMEs too operational.

| Document | Purpose |
|----------|---------|
| [index.md](index.md) | Published TechDocs landing page for the developer workspace guide |
| [OPERATIONS.md](OPERATIONS.md) | Deployment order, bootstrap behavior, validation strategy, GitOps operations, day-2 notes, and cleanup guidance |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptom-based diagnostics and recovery commands |
| [RHOAI_3_4_UPGRADE.md](RHOAI_3_4_UPGRADE.md) | Red Hat OpenShift AI 3.4 upgrade posture, validation gates, risks, and rollback notes |
| [DEVELOPER_WORKSPACE_GUIDE.md](DEVELOPER_WORKSPACE_GUIDE.md) | TechDocs guide for Developer Hub, Dev Spaces, Continue, MaaS, and Stage 100 vibe coding |
| [DEVELOPER_WORKFLOW_VALIDATION.md](DEVELOPER_WORKFLOW_VALIDATION.md) | Quality gates and evidence expectations for Stage 100 and deferred developer workflow stages |
| [AI_COLLABORATION.md](AI_COLLABORATION.md) | AI-assisted contribution rules, shared rules and skills governance, and local vs shared boundaries |
| [../BACKLOG.md](../BACKLOG.md) | Workarounds, known limitations, validation notes, and planned cleanup |

## Learning Path

The implemented flow is defined in [`../flows/default.yaml`](../flows/default.yaml):

1. [Project README](../README.md)
2. [Stage 010: OpenShift AI Platform Foundation](../stages/010-openshift-ai-platform-foundation/README.md)
3. [Stage 020: GPU Infrastructure for Private AI](../stages/020-gpu-infrastructure-private-ai/README.md)
4. [Stage 030: Private Model Serving](../stages/030-private-model-serving/README.md)
5. [Stage 040: Governed Models-as-a-Service](../stages/040-governed-models-as-a-service/README.md)
6. [Stage 050: Approved External Model Access](../stages/050-approved-external-model-access/README.md)
7. [Stage 060: MCP Context Integrations](../stages/060-mcp-context-integrations/README.md)
8. [Stage 070: Controlled Developer Workspaces](../stages/070-controlled-developer-workspaces/README.md)
9. [Stage 080: AI-Assisted Application Modernization](../stages/080-ai-assisted-application-modernization/README.md)
10. [Stage 090: Developer Portal and Self-Service](../stages/090-developer-portal-self-service/README.md)

The developer workflow extension currently keeps [Stage 100](../stages/100-governed-developer-entry-point/README.md) as a documentation-only vibe-coding stage. The former Stage 110 spec and README-alignment placeholder has been merged into Stage 100. Deferred stages `120-170` are tracked in [BACKLOG.md](../BACKLOG.md) until each one has a concrete implementation plan, artifacts, and validation path.

## AI Collaboration Rules

Shared Cursor rules, skills, and agent definitions live under [`../.cursor/`](../.cursor/). They define project-wide AI agent behavior. Do not commit local rules, skills, credentials, personal paths, private cluster URLs, or personal preferences. See [AI_COLLABORATION.md](AI_COLLABORATION.md) before changing shared agent behavior.

Claims in user-facing documentation must stay aligned with manifests, scripts, validation checks, and official product documentation.
