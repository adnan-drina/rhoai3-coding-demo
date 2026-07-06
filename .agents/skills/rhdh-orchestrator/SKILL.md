---
name: rhdh-orchestrator
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when configuring Orchestrator for serverless workflows, cloud migration,
  onboarding, and customization in Red Hat Developer Hub 1.10. Covers plugin
  enablement, Operator and Helm installation, CloudEvent/Kafka integration,
  custom review pages, RBAC permissions, PostgreSQL configuration, Loki log
  integration, air-gapped deployment, and SonataFlow architecture. Do NOT use
  for Scorecard configuration (use rhdh-scorecards), diagnostic data collection
  (use rhdh-diagnostic-data), or general RHDH installation.
---

# RHDH Orchestrator

Use this skill to configure and manage the Orchestrator plugin in
Red Hat Developer Hub 1.10 grounded in official product documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Platform Requirement

Orchestrator supports **only** Red Hat OpenShift Container Platform. It is not
available on AKS, EKS, or GKE.

## Architecture Overview

- **RHDH** — frontend, backend, form-widgets, and scaffolder-backend plugins
- **OpenShift Serverless Logic Operator** — SonataFlow runtime, Data Index
  Service, Job Service
- **OpenShift Serverless** — Knative eventing and functions
- **PostgreSQL** — persistence for SonataFlow and Developer Hub data
- **AMQ Streams (optional)** — Kafka for reliable CloudEvent delivery

## Compatibility (RHDH 1.10)

| Component | Version |
|-----------|---------|
| Orchestrator plugin | 1.10.0 |
| OpenShift | 4.18–4.21 |
| OpenShift Serverless Logic (OSL) | 1.38.0 |
| OpenShift Serverless | 1.37.1 |

## Plugin Packages

| Component | OCI Package |
|-----------|-------------|
| Frontend | `red-hat-developer-hub-backstage-plugin-orchestrator` |
| Backend | `red-hat-developer-hub-backstage-plugin-orchestrator-backend` |
| Form widgets | `red-hat-developer-hub-backstage-plugin-orchestrator-form-widgets` |
| Scaffolder module | `red-hat-developer-hub-backstage-plugin-scaffolder-backend-module-orchestrator` |
| Loki module | `red-hat-developer-hub-backstage-plugin-orchestrator-backend-module-loki` |

Operator packages use `registry.access.redhat.com/rhdh/` prefix with
`{{inherit}}` for auto-version resolution.

## Key Capabilities

1. **Plugin enablement** — enable four core plugins plus notifications/signals
   in `dynamic-plugin-config.yaml`.
2. **Operator installation** — Backstage CR with `dependencies: - ref: sonataflow`
   for automatic SonataFlowPlatform provisioning.
3. **Helm installation** — `orchestrator.enabled=true` with
   `redhat-developer-hub-orchestrator-infra` chart for infrastructure.
4. **CloudEvent/Kafka integration** — `orchestrator.kafka` config for
   event-driven asynchronous workflow execution.
5. **Custom review pages** — `OrchestratorFormApi.getReviewComponent()` with
   `ReviewComponentProps`, helper utilities from `orchestrator-form-react`.
6. **RBAC permissions** — granular per-workflow read/update permissions via
   `orchestrator.workflow[.workflowId]` and `orchestrator.workflow.use[.workflowId]`.
7. **External PostgreSQL** — SonataFlowPlatform CR with explicit DB service and
   secret references for both Operator and Helm deployments.
8. **Air-gapped deployment** — `oc mirror` with ImageSetConfiguration for
   plugin OCI images and Serverless Logic/Serverless operators.
9. **Loki log integration** — `orchestrator.workflowLogProvider.loki` for
   centralized workflow debugging.
10. **JSON structured logging** — Quarkus JSON logging with processInstanceId
    correlation for SonataFlow workflows.

## RBAC Permissions

| Permission | Policy | Description |
|------------|--------|-------------|
| `orchestrator.workflow` | read | List/read all workflow definitions and instances |
| `orchestrator.workflow.[workflowId]` | read | List/read specific workflow |
| `orchestrator.workflow.use` | update | Run or abort any workflow |
| `orchestrator.workflow.use.[workflowId]` | update | Run or abort specific workflow |
| `orchestrator.workflowAdminView` | read | View definition editor and instance variables |
| `orchestrator.instanceAdminView` | read | View all instances (including other users') |

Generic permissions override specific denials within the same action type.

## SonataFlowPlatform CR

The Operator auto-provisions a `SonataFlowPlatform` CR using:
- PostgreSQL database `backstage_plugin_orchestrator`
- Secret `backstage-psql-secret-{{backstage-name}}`
- Service `backstage-psql-{{backstage-name}}`

For external PostgreSQL, remove `ref: sonataflow` dependency and configure
explicit `serviceRef` and `secretRef` in the SonataFlowPlatform CR.

## Workflow

1. Read `references/official-doc-extraction.md` for exact YAML patterns.
2. Identify the task: enable plugins, install via Operator/Helm, configure
   Kafka, set RBAC, connect external DB, or set up air-gapped deployment.
3. Use `{{inherit}}` for Operator packages or explicit version tags.
4. Validate with the verification steps documented per section.
5. Never invent plugin config fields not documented in the official source.

## Related Skills

- `rhdh-scorecards` — Project Health Scorecards
- `rhdh-diagnostic-data` — must-gather diagnostic data collection

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
