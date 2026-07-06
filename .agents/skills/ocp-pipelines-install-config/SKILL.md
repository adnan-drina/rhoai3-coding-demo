---
name: ocp-pipelines-install-config
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when installing, uninstalling, or configuring Red Hat OpenShift Pipelines
  Operator: TektonConfig CR customization, installation profiles (Lite, Basic,
  All), operator Subscription, pipeline resolvers, pruner configuration,
  event-driven pruner, RBAC resource creation, service monitor, webhook
  options, Tekton Hub migration to Artifact Hub, performance tuning, HA mode,
  and restricted environment setup for OpenShift Pipelines 1.22. Do NOT use for
  Pipelines concepts (use ocp-pipelines-about), creating CI/CD pipelines (use
  ocp-pipelines-cicd), Pipelines as Code (use ocp-pipelines-as-code), security
  (use ocp-pipelines-security), or performance and resource management (use
  ocp-pipelines-performance).
---

# OCP Pipelines Install Config

Use this skill to ground OpenShift Pipelines installation and configuration
guidance in the official Red Hat OpenShift Pipelines 1.22 installing and
configuring guide for the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers the Operator
installation lifecycle, uninstallation, and TektonConfig CR customization
surface. It does not cover pipeline authoring, Pipelines as Code, Tekton
Chains, Tekton Results, or pipeline security topics.

## Installation

The Operator can be installed through the web console or CLI:

- **Web console**: Navigate to Operators > OperatorHub, search for Red Hat
  OpenShift Pipelines, choose an update channel (`latest` or
  `pipelines-<version>`), select All namespaces and Automatic approval
  strategy, then verify with `oc get tektonconfig config`.
- **CLI**: Create a `Subscription` in the `openshift-operators` namespace with
  `name: openshift-pipelines-operator-rh`, `source: redhat-operators`, and the
  desired channel. Apply with `oc apply -f`.
- **Restricted environment**: The Operator configures proxy settings
  automatically via a proxy webhook. Disable per-namespace with the
  `operator.tekton.dev/disable-proxy: true` label.

### Installation Profiles

The TektonConfig CR supports three profiles:

- **Lite**: Tekton Pipelines only.
- **Basic**: Tekton Pipelines, Triggers, Chains, and Results.
- **All** (default): All Tekton components including Pipelines, Triggers,
  Chains, Results, Pipelines as Code, and Tekton add-ons.

## Uninstallation

Uninstallation requires three ordered steps:

1. Delete optional CRs (`TektonHub`, `TektonResult`) then `TektonConfig`.
2. Uninstall the Operator from OperatorHub.
3. Delete CRDs in the `operator.tekton.dev` group.

Skipping optional CR deletion before uninstalling the Operator prevents later
removal of those components.

## TektonConfig Customization

All customization is performed through the `TektonConfig` CR named `config`.
Read `references/official-doc-extraction.md` for the full configuration
surface, including:

- Performance tuning (HA mode, buckets, replicas, threads-per-controller,
  kube-api-qps, kube-api-burst)
- Control plane configuration (modifiable fields with defaults and optional
  fields)
- Default service account for pipelines and triggers
- Namespace labels and annotations for `openshift-pipelines`
- Resync period for the pipelines controller
- Service monitor toggle
- Pipeline resolvers (bundles, cluster, git, hub) and resolver-specific config
- Resolver tasks and pipeline templates
- Tekton Triggers toggle
- Tekton Hub integration and migration to Artifact Hub
- RBAC resource creation and Trusted CA bundle config map
- Inline specification controls
- Job-based pruner (schedule, keep, keep-since, prune-per-resource)
- Event-driven pruner (TTL, history limits, namespace-level, resource-level,
  selectors, observability metrics)
- Webhook configuration options for pipelines, triggers, Pipelines as Code,
  and Hub controllers

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns installation, uninstallation, or a
   specific TektonConfig customization area.
4. For GitOps manifests, verify all API versions, fields, and CRD names before
   committing.
5. For live operations, use the repo environment guard.
6. Validate the output with `references/validation-checklist.md` when present.

## Related Skills

- Use future `ocp-pipelines-about` for Pipelines conceptual overview.
- Use future `ocp-pipelines-cicd` for creating and running CI/CD pipelines.
- Use future `ocp-pipelines-as-code` for Pipelines as Code configuration.
- Use future `ocp-pipelines-security` for Tekton Chains and supply chain
  security.
- Use future `ocp-pipelines-performance` for performance and resource
  management beyond TektonConfig tuning.
- Use `ocp-cicd-builds` for OpenShift Builds and BuildConfig topics.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
