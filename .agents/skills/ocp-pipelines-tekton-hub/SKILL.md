---
name: ocp-pipelines-tekton-hub
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when auditing or retiring historical Tekton Hub integrations while
  moving to OpenShift Pipelines 1.24, including old TektonHub resources,
  PAC resolver references and migration to Artifact Hub or reviewed tasks.
  Do NOT use to deploy a new Tekton Hub on 1.24; use
  ocp-pipelines-install-config or ocp-pipelines-cicd for current paths.
---

# Retire Historical Tekton Hub Integrations

Read `references/source-capture.md` and the current-update section of
`references/official-doc-extraction.md` before using historical Hub material.

OpenShift Pipelines 1.24 no longer includes a Hub component in its compatibility
matrix or a custom Hub guide. PAC removed its Tekton Hub-specific integration;
tkn's Tekton Hub integration is deprecated in favor of Artifact Hub.

## Workflow

1. Inventory old TektonHub resources, catalog consumers and retained data.
2. Identify PAC annotations, hub resolver configuration and tkn install paths.
3. Move each consumer to Artifact Hub, a reviewed namespaced Task, cluster
   resolver or immutable OCI bundle, as supported by its actual resolver.
4. Verify resource resolution and a bounded pipeline execution.
5. Retire old Hub resources only after a reviewed data-retention/removal plan.

Do not create a new TektonHub CR from the old extraction or advertise its old
database/OAuth fields as supported 1.24 configuration. Use
`ocp-pipelines-install-config`, `ocp-pipelines-as-code` and `ocp-pipelines-cicd`
for the replacement paths. This stable skill name remains useful for legacy
diagnosis; it does not endorse a new Hub deployment.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
