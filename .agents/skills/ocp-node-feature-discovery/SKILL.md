---
name: ocp-node-feature-discovery
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding OpenShift Container Platform
  Node Feature Discovery guidance from official OCP documentation: specialized
  hardware discovery, NFD Operator installation, NodeFeatureDiscovery custom
  resources, operand.image handling, NFD worker configuration, feature labels,
  NodeFeatureRule labels and taints, NFD Topology Updater, NodeResourceTopology,
  PCI, USB, kernel, and custom feature sources, and accelerator node label
  validation, and the Red Hat CoP NFD GitOps catalog pattern. Do NOT use for
  provisioning GPU workers; use ocp-machine-management. Do NOT use for NVIDIA
  GPU Operator, ClusterPolicy, or RHOAI hardware profiles; use
  rhoai-nvidia-gpu-accelerators. Do NOT run live NFD changes without the env
  safety guard and explicit approval.
---

# OCP Node Feature Discovery

Use this skill to ground OpenShift Node Feature Discovery (NFD) installation,
configuration, feature-label review, and topology updater guidance in the
official OpenShift Container Platform Specialized hardware and driver
enablement guide for the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers NFD and NFD-created
hardware metadata; it does not replace Machine API, MachineSet, NVIDIA GPU
Operator, Kernel Module Management, Driver Toolkit, or RHOAI accelerator
skills.

## Demo NFD Posture

For this AWS-hosted RHOAI demo:

- Use NFD as the OpenShift hardware-discovery layer that publishes feature
  labels used by accelerator and workload-placement workflows.
- Treat NFD as a prerequisite gate for NVIDIA GPU enablement, not as the source
  of `nvidia.com/gpu` capacity. GPU capacity is exposed by the NVIDIA GPU
  Operator and device plugin and is handled in `rhoai-nvidia-gpu-accelerators`.
- Use the Red Hat CoP `nfd` catalog as a local curation pattern only. Reuse its
  operator/channel layout, aggregate overlay shape, and NVIDIA-focused instance
  overlay idea; do not commit remote Kustomize references.
- For the NVIDIA-only demo path, prefer an `only-nvidia` NFD instance overlay
  that limits PCI label publication to the accelerator-relevant class/vendor
  signal after the active CRD schema and official docs are verified.
- Verify feature labels from the live cluster or official CRD/schema before
  writing placement rules, hardware-profile assumptions, or README claims.
- Use `NodeFeatureRule` only for intentional vendor-specific or
  application-specific labels and taints. Do not create broad scheduling taints
  unless the scheduling impact is documented.
- Enable NFD Topology Updater only when the implementation requires
  topology-aware placement or NUMA/resource-zone information.

## NFD Model

Use the official docs to frame:

- **NFD Operator**: installs and manages Node Feature Discovery in OpenShift.
- **NodeFeatureDiscovery**: the custom resource that configures NFD operands,
  worker behavior, enabled feature sources, label filtering, and optional
  topology updater workers.
- **Feature labels**: node labels generated from hardware and OS discovery
  sources such as PCI, USB, kernel, CPU, and custom hooks.
- **NodeFeatureRule**: rule-based custom labeling and optional tainting based
  on discovered node features.
- **NFD Topology Updater**: per-node daemon that reports per-zone resource
  availability and causes `NodeResourceTopology` custom resources to be
  created.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Read `references/gitops-catalog-nfd-pattern.md` when rebuilding NFD
   operator, instance, aggregate overlays, or NVIDIA-only discovery posture.
4. Identify whether the task concerns:
   - NFD Operator installation or subscription review
   - `NodeFeatureDiscovery` custom resource configuration
   - feature sources, label filtering, or no-publish behavior
   - PCI, USB, kernel, CPU, or custom feature labels
   - `NodeFeatureRule` labels or taints
   - NFD Topology Updater and `NodeResourceTopology`
   - GPU accelerator discovery handoff to RHOAI/NVIDIA skills
5. For GitOps manifests, verify CR fields against the active cluster schema or
   official docs before committing.
6. For live operations, use the repo environment guard and pair this skill with
   `env-troubleshoot`, `env-manage-resources`, or `env-deploy-and-evaluate`.
7. Validate the output with `references/validation-checklist.md`.

## Related Skills

- Use `ocp-machine-management` for GPU worker MachineSets and node creation.
- Use `ocp-nodes` for node scheduling, labels, taints, tolerations, and
  placement mechanics after hardware labels exist.
- Use `ocp-machine-configuration` for Machine Config Operator, KubeletConfig,
  ContainerRuntimeConfig, and node operating-system configuration.
- Use `rhoai-nvidia-gpu-accelerators` for NVIDIA GPU Operator, ClusterPolicy,
  RHOAI accelerator profiles, and GPU serving intent.
- Create separate future `ocp-driver-toolkit` or `ocp-kernel-module-management`
  skills for Driver Toolkit and Kernel Module Management guidance from the same
  OCP documentation family.
- Use `project-gitops-authoring` and `project-manifest-review` for manifests.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/gitops-catalog-nfd-pattern.md`
- `references/validation-checklist.md`
- `examples/nfd-review-patterns.md`
