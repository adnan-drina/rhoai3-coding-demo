# Documentation Index

This directory contains operational documentation for the Red Hat OpenShift AI coding demo. The root README and stage READMEs are the user-facing educational path; this directory holds the runbook material that would make those READMEs too operational.

| Document | Purpose | Intended use |
|----------|---------|--------------|
| [OPERATIONS.md](OPERATIONS.md) | Deployment order, bootstrap behavior, validation strategy, GitOps operating model, day-2 notes, and cleanup guidance | Use while installing, validating, or maintaining the demo environment |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptom-based recovery procedures with diagnostic and recovery commands | Use when a deployment stage fails validation or a demo component is unavailable |
| [AI_COLLABORATION.md](AI_COLLABORATION.md) | AI-assisted contribution model, rules/skills governance, local vs shared boundaries | Use when adding or reviewing rules, skills, or AI-assisted contributions |
| [../BACKLOG.md](../BACKLOG.md) | Deviation register, workarounds, known limitations, validation notes, and planned cleanup | Use when assessing whether demo behavior matches supported Red Hat product guidance |

The published learning path is the stage-based flow from [`flows/default.yaml`](../flows/default.yaml):

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

Shared Cursor rules (`.cursor/rules/`), skills (`.cursor/skills/`), and agent definitions (`.cursor/agents/`) are tracked in git and define project-wide AI agent behavior. Local/private rules and skills that contain credentials, local paths, or personal preferences must not be committed. See [AI_COLLABORATION.md](AI_COLLABORATION.md) for the governance model.

Claims in user-facing documentation must stay aligned with manifests, scripts, validation checks, and official product documentation.
