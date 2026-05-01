# Documentation Index

This directory contains operational documentation for the RHOAI coding demo. The root README and step READMEs are the user-facing educational path; this directory holds the runbook material that would make those READMEs too operational.

| Document | Purpose | Intended use |
|----------|---------|--------------|
| [OPERATIONS.md](OPERATIONS.md) | Deployment order, bootstrap behavior, validation strategy, GitOps operating model, day-2 notes, and cleanup guidance | Use while installing, validating, or maintaining the demo environment |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Symptom-based recovery procedures with diagnostic and recovery commands | Use when a deployment step fails validation or a demo component is unavailable |

The published learning path is:

1. [Project README](../README.md)
2. [Step 01: OpenShift AI platform](../steps/step-01-rhoai-platform/README.md)
3. [Step 02: GPU infrastructure](../steps/step-02-gpu-infra/README.md)
4. [Step 03: Governed Models-as-a-Service](../steps/step-03-llm-serving-maas/README.md)
5. [Step 04: Dev Spaces and AI code assistants](../steps/step-04-devspaces/README.md)
6. [Step 05: MTA and Developer Lightspeed](../steps/step-05-mta/README.md)
7. [Step 06: Red Hat Developer Hub](../steps/step-06-developer-hub/README.md)

Local-only notes, Cursor rules, agent prompts, and scratch material are not part of the published documentation set. They can guide maintenance, but claims in user-facing documentation must stay aligned with manifests, scripts, validation checks, and official product documentation.
