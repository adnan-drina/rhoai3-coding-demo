---
name: ocp-pipelines-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when answering questions about Red Hat OpenShift Pipelines 1.24 release
  notes: version compatibility matrix, new features and enhancements, breaking
  changes, deprecated features, removed features, Technology Preview features,
  known issues, fixed issues, component versions, and supported OCP versions.
  Do NOT use for installing or configuring OpenShift Pipelines, creating CI/CD
  pipelines or tasks, Pipelines as Code setup and configuration, Tekton CRD
  authoring, security policy, observability, or general OpenShift Pipelines
  operational guidance.
---

# OpenShift Pipelines Release Notes — 1.24

Read `references/source-capture.md` and the current-update section of
`references/official-doc-extraction.md` for release-specific claims.

## Current documented patches

The captured guide covers **1.24.0 and 1.24.1**. This branch currently selects
1.24.0 for deployment; availability and qualification of 1.24.1 remain separate.

1.24.1 removes the cluster-wide system:authenticated approval grant from Manual
Approval Gate and enforces immutable approval parameters and approver entries.
Use explicit namespace RoleBindings for approvers. Manual Approval Gate remains
Technology Preview.

## Compatibility and breaking changes

The 1.24 matrix lists Pipelines 1.15.x, Triggers 0.37.x, CLI 0.46.x, Chains
0.29.x, PAC 0.50.x and Results 0.20.x. Supported OCP versions listed are 4.14,
4.16, 4.18, 4.19, 4.20, 4.21 and 4.22. Check the current lifecycle matrix and
installed CSV rather than equating Operator and upstream component versions.

- PAC removes Tekton Hub integration; use Artifact Hub. The 1.24 matrix no
  longer includes a Hub component.
- GitLab source lookups use the immutable event SHA; new-branch pushes and
  token rotation have specific fixes.
- Infrastructure metrics move to OpenTelemetry prefixes. Audit dashboards
  against the actual endpoints after an upgrade.
- Multicluster/Kueue and manual approval retain their preview boundaries.

Use the current release chapters, not retained 1.22 notes, for claims about
new features, fixes or current support.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
