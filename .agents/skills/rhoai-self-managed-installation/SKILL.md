---
name: rhoai-self-managed-installation
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when installing, documenting, reviewing, or rebuilding Red Hat OpenShift
  AI Self-Managed on an existing OpenShift cluster for this demo. Covers
  AWS-hosted OpenShift assumptions, exact OpenShift version checks,
  subscription and cluster-admin prerequisites, CLI-derived Operator
  installation manifests, DataScienceCluster component management, ArgoCD/GitOps
  application flow, default/custom namespace handling, and post-install
  validation. Do NOT use for disconnected installs, managed cloud-service
  add-on installs, uninstall, or individual component tuning; use the relevant
  RHOAI component skill and env-* skills.
---

# RHOAI Self-Managed Installation

Use this skill to rebuild and review the demo installation flow for Red Hat
OpenShift AI Self-Managed on an existing AWS-hosted OpenShift environment.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official CLI installation flow to this repo's GitOps operating model.

## Demo Installation Policy

For this project:

- Install Red Hat OpenShift AI Self-Managed into an existing OpenShift cluster
  running on AWS infrastructure.
- Assume the underlying OpenShift environment already has the required Red Hat
  subscriptions for the demo, but verify this before installation.
- Assume a cluster-admin user is provided; do not use `kubeadmin` for the
  installation workflow.
- Always verify the exact OpenShift version before installing or upgrading
  RHOAI.
- Install the latest available RHOAI version in the selected, verified update
  channel. Use `rhoai-update-channels` for channel policy.
- Derive manifests from official CLI guidance, then apply them through ArgoCD
  Applications and GitOps. Do not make direct `oc create`/`oc apply` mutations
  for ArgoCD-managed resources except during explicit investigation.

## Required Install Sequence

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Verify OpenShift version, cluster-admin access, default storage class,
   identity provider posture, internet/registry access, and absence of Open
   Data Hub.
3. Verify component prerequisites for the capabilities that the demo will
   enable, including object storage, cert-manager, Kueue, GPU, Llama Stack, and
   model registry dependencies as applicable.
4. Decide whether predefined namespaces are sufficient. Use predefined
   namespaces by default unless the reimplementation explicitly needs custom
   namespace control.
5. Create GitOps manifests for the RHOAI Operator namespace, `OperatorGroup`,
   and `Subscription`.
6. Create GitOps manifests for `DataScienceCluster` component management.
7. Create or update ArgoCD Application manifests so ArgoCD applies the install
   content.
8. Validate Operator readiness, `DataScienceCluster` phase, installed component
   status, application namespace pods, and dashboard component versions.

## GitOps Adaptation

The official chapter uses direct CLI creation commands. In this repo, those
commands define manifest shape only. The active implementation should commit
the equivalent manifests under `gitops/` and sync them through ArgoCD.

Keep install manifests and docs atomic:

- README explains Why/What and official-doc source mapping.
- GitOps manifests implement the official CLI-derived resources.
- scripts validate state but do not own long-lived declarative resources.
- operations docs explain bootstrap and day-2 behavior.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/gitops-install-skeleton.md`
