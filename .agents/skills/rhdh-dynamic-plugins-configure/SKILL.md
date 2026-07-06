---
name: rhdh-dynamic-plugins-configure
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when configuring dynamic plugins in Red Hat Developer Hub, including
  plugin settings, environment variables, integration options, app-config
  fragments, annotations, ClusterRole permissions, and custom resource
  configuration. Covers Argo CD, JFrog Artifactory, Nexus Repository Manager,
  Tekton, Topology, Bulk Import, ServiceNow, Kubernetes custom actions, GitHub
  Events Module, and core backend service overrides. Do NOT use for looking up
  plugin names, versions, or support tiers (use rhdh-dynamic-plugins-reference),
  Helm Chart deployment values (use rhdh-helm-reference), or live cluster
  changes without the OpenShift safety guard.
---

# RHDH Dynamic Plugins Configuration

Use this skill for configuring individual dynamic plugins in Red Hat Developer
Hub on the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official configuring dynamic plugins guide to this repo's operations and GitOps
review model.

## Scope

This skill covers:

- Argo CD plugin: app-config, entity annotations, `argocd/app-selector`,
  `argocd/instance-name`, community vs Roadie plugin choice, Argo CD Rollouts
  integration with Kubernetes plugin custom resources
- JFrog Artifactory plugin: proxy settings, `jfrog-artifactory/image-name`
  annotation
- Nexus Repository Manager plugin: proxy settings, experimental annotations
- Tekton plugin: ClusterRole for PipelineRuns/TaskRuns, `janus-idp.io/tekton`
  annotation, Kubernetes custom resources configuration
- Topology plugin: OpenShift routes, pod logs, Tekton PipelineRuns, virtual
  machines, Dev Spaces source code editor, labels, annotations, runtime icons,
  application grouping, node connectors
- Bulk Import: enabling plugins, RBAC permissions, GitHub/GitLab repository
  import, audit logs, Scaffolder templates, Orchestrator workflows
- ServiceNow: backend/frontend/scaffolder configuration, entity linking,
  scaffolder actions, authentication methods (basic, OAuth)
- Kubernetes custom actions: enabling the plugin, creating namespaces,
  template creation
- GitHub Events Module: webhook configuration for real-time catalog updates
- core backend service overrides via environment variables

Use other skills for adjacent work:

- `rhdh-dynamic-plugins-reference` for plugin names, versions, support tiers,
  OCI paths, and required environment variables
- `rhdh-helm-reference` for Helm Chart configuration values and deployment
  parameters

## Demo Policy

For this repo:

- Argo CD plugin configuration is relevant to the GitOps-based demo workflow.
- Tekton and Topology plugins are relevant to OpenShift CI/CD visualization.
- Bulk Import GitLab support is Technology Preview; note this in any demo docs.
- Do not invent annotations, ClusterRole rules, or app-config keys not listed
  in the official configuration guide.
- Treat community and Roadie Argo CD plugin variants as distinct; do not mix.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - configuring a specific plugin's app-config fragment
   - setting up entity annotations for a plugin
   - configuring ClusterRole permissions for a plugin
   - reviewing Bulk Import, ServiceNow, or Kubernetes custom action workflows
   - configuring GitHub Events Module webhooks
   - overriding a core backend service
4. Use the official guide's procedures as the configuration authority.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
