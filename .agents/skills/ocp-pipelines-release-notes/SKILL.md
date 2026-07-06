---
name: ocp-pipelines-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when answering questions about Red Hat OpenShift Pipelines 1.22 release
  notes: version compatibility matrix, new features and enhancements, breaking
  changes, deprecated features, removed features, Technology Preview features,
  known issues, fixed issues, component versions, and supported OCP versions.
  Do NOT use for installing or configuring OpenShift Pipelines, creating CI/CD
  pipelines or tasks, Pipelines as Code setup and configuration, Tekton CRD
  authoring, security policy, observability, or general OpenShift Pipelines
  operational guidance.
---

# OCP Pipelines Release Notes

Use this skill to ground OpenShift Pipelines release information in the
official Red Hat OpenShift Pipelines 1.22 release notes for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Compatibility Matrix

The release notes include a versioned compatibility and support matrix mapping
Operator version to component versions (Pipelines, Triggers, CLI, Chains, Hub,
Pipelines as Code, Results, Manual Approval Gate, Pruner, Cache) and supported
OCP versions. Read `references/official-doc-extraction.md` for exact versions.

## Release History

OpenShift Pipelines 1.22 has the following sub-releases:

- **1.22.4** — security fix for multicluster proxy permissions
- **1.22.3** — security fixes for Pipelines as Code (webhook validation, GitHub
  App token scoping), UI fix for status column rendering, CEL expression fix
  for Bitbucket Cloud
- **1.22.2** — webhook signature validation for Forgejo/Gitea, console plugin
  upgrade to React 18 and PatternFly 6 for OCP 4.22 compatibility
- **1.22.1** — stability release
- **1.22** — initial GA release with new features, Technology Preview
  features, breaking changes, known issues, fixed issues, deprecated and
  removed features

## Key Topics

- Version compatibility and support matrix
- New features: resolver caching, HTTP resolver hash verification, hostUsers
  pod template support, pipelines-in-pipelines, per-task timeout overrides,
  array values in `when` expressions, step display names, concurrent StepAction
  resolution, ServiceMonitor for Results and webhook, Pipelines as Code
  enhancements (changed-file caching, update comment strategy, skip-ci tags,
  glob pattern token scoping, CEL expressions in templates, GraphQL batched
  .tekton file retrieval), ANSI color in console logs
- Technology Preview: multi-cluster configuration, Tekton Scheduler (Kueue),
  federated PipelineRun UI indicator
- Breaking changes: legacy static console plugin removal
- Known issues: buildah-ns task failure on OCP 4.20+, tkn CLI limitations in
  multicluster, opc results logs output limit
- Fixed issues across Pipelines, Operator, Pipelines as Code, and UI
- Deprecated features: openshift-pipelines-client RPM, pipelinerun_status
  field in Repository CR
- Removed features: disable-affinity-assistant field, public Tekton Hub as
  default catalog

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the question concerns:
   - component version compatibility
   - new features in a specific sub-release
   - Technology Preview capabilities
   - breaking or behavioral changes during upgrade
   - known issues and workarounds
   - fixed issues in a specific sub-release
   - deprecated or removed features
4. Use exact version numbers and component names from the extraction.
5. When advising on upgrades, cross-reference breaking changes, removed
   features, and known issues.

## Related Skills

- Use `ocp-cicd-builds` for OpenShift build strategies and BuildConfig.
- Use `ocp-gitops-operator` for OpenShift GitOps and Argo CD behavior.
- Use future `ocp-pipelines` for general OpenShift Pipelines installation,
  configuration, and usage guidance beyond release notes.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
