# Documentation Index

This directory holds operational and governance documentation for the Red Hat OpenShift AI coding demo. The root README and stage READMEs explain the learning path; these docs hold the runbooks, validation notes, and contribution rules that would make those READMEs too operational.

| Document | Purpose |
|----------|---------|
| [OPERATIONS.md](OPERATIONS.md) | Deployment order, bootstrap behavior, validation strategy, GitOps operations, day-2 notes, run verdicts, and cleanup guidance |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptom-based diagnostics and recovery commands |
| [PLATFORM_BASELINE.md](PLATFORM_BASELINE.md) | Fresh-environment platform baseline |
| [../BACKLOG.md](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/BACKLOG.md) | Workarounds, known limitations, validation notes, and planned cleanup |

_This directory holds operational documentation. Read `PLATFORM_BASELINE.md` for selected product versions and `BACKLOG.md` for the boundaries of live qualification._

## Learning Path

The implemented flow is the ordered stage directories. Links outside this documentation tree open the source repository, so they also work in rendered TechDocs:

1. [Project README](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/README.md)
2. [Stage 010: OpenShift AI Platform Foundation](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/stages/010-openshift-ai-platform-foundation/README.md)
3. [Stage 020: GPU Infrastructure for Private AI](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/stages/020-gpu-infrastructure-private-ai/README.md)
4. [Stage 030: Private Model Serving](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/stages/030-private-model-serving/README.md)
5. [Stage 040: Governed Models-as-a-Service](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/stages/040-governed-models-as-a-service/README.md)
6. [Stage 050: Model Evaluation](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/stages/050-model-evaluation/README.md)
7. [Stage 060: Agent Runtime and AgentOps](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/stages/060-agent-runtime-and-agentops/README.md)
8. [Stage 070: Advanced Application Platform](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/stages/070-advanced-app-platform/README.md)
9. [Stage 110: AI-Assisted Development](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/stages/110-ai-assisted-development/README.md)
10. [Stage 120: AI-Agentic Development](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/stages/120-ai-agentic-development/README.md)
11. [Stage 130: AI-Autonomous Migration](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/stages/130-ai-autonomous-migration/README.md)

[Stage 110](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/stages/110-ai-assisted-development/README.md) starts the developer-facing path. It uses the Stage 070 portal and workspace platform for assisted development; Stage 120 covers agentic development and Stage 130 covers autonomous migration. A stage being implemented does not mean every workflow has passed live qualification; see [BACKLOG.md](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/BACKLOG.md).

## AI Collaboration Rules

Shared rules, skills, and agent definitions live under [`../.agents/`](https://github.com/adnan-drina/rhoai3-coding-demo/tree/main/.agents/). They define project-wide AI agent behavior. Do not commit local rules, skills, credentials, personal paths, private cluster URLs, or personal preferences. See [CONTRIBUTING.md](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/CONTRIBUTING.md) before changing shared agent behavior.

Claims in user-facing documentation must stay aligned with manifests, scripts, validation checks, and official product documentation.

Agent platform design: [Stage 060 runtime and AgentOps](migration/060-agent-runtime-and-agentops-plan.md) and [Stage 070 developer platform and SCM](migration/070-developer-platform-and-scm-plan.md). These documents record design scope; current implementation and validation status is in the [Stage 070 upgrade plan](migration/070-upgrade-and-gitlab-plan-20261013.md#implementation-status) and [BACKLOG.md](https://github.com/adnan-drina/rhoai3-coding-demo/blob/main/BACKLOG.md).
