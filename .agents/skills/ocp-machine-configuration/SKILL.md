---
name: ocp-machine-configuration
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding OpenShift Container Platform
  machine configuration guidance from official OCP documentation: Machine
  Config Operator, MachineConfig, MachineConfigPool, MachineConfiguration,
  KubeletConfig, ContainerRuntimeConfig, PinnedImageSet, node disruption
  policies, boot image management, rendered machine config pruning, image mode
  for OpenShift, MachineOSConfig, MachineOSBuild, Machine Config Daemon metrics,
  systemd, CRI-O, kubelet, kernel, NetworkManager, and RHCOS host
  configuration. Do NOT use for MachineSet or cloud machine lifecycle; use
  ocp-machine-management. Do NOT use for pod scheduling and node operations;
  use ocp-nodes. Do NOT run live MCO operations without the env safety guard
  and explicit approval.
---

# OCP Machine Configuration

Use this skill to ground OpenShift Machine Config Operator (MCO), RHCOS host
configuration, and machine config pool rollout guidance in the official
OpenShift Container Platform Machine configuration guide for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers node OS and runtime
configuration after machines exist; it does not replace `ocp-machine-management`
for MachineSet and cloud machine lifecycle, `ocp-nodes` for scheduling and node
operations, or RHOAI skills for accelerator and OpenShift AI component
configuration.

## Demo Posture

For this AWS-hosted RHOAI demo:

- Treat MCO, `MachineConfig`, `MachineConfiguration`, `KubeletConfig`,
  `ContainerRuntimeConfig`, `PinnedImageSet`, `MachineOSConfig`, and MCP changes
  as high-risk platform changes because they can drain or reboot nodes, reload
  CRI-O, affect upgrades, or block cluster operators.
- Prefer the default OpenShift host configuration unless the demo has a clear,
  official-doc-backed need for a node OS or runtime change.
- Do not modify control plane machine config pools unless the user explicitly
  requests a planned control plane operation and `ocp-etcd` review is included.
- Keep GPU node behavior aligned with `rhoai-nvidia-gpu-accelerators`; do not
  use ad hoc `MachineConfig` tuning as a substitute for NVIDIA GPU Operator,
  Node Feature Discovery, or supported RHOAI hardware profile configuration.
- Use GitOps only after verifying API shape and rollout impact. Do not invent
  Ignition, Butane, CRI-O, kubelet, systemd, or kernel settings.

## Machine Configuration Model

Use the official docs to frame:

- **Machine Config Operator**: manages RHCOS host configuration and applies
  changes to nodes through machine config pools.
- **MachineConfig**: defines host-level configuration applied to a target role
  or pool, including files, systemd units, kernel arguments, extensions, and
  related RHCOS settings.
- **MachineConfigPool**: groups nodes and tracks rendered machine config
  rollout, update, degraded, and paused state.
- **MachineConfiguration**: singleton operator configuration in the
  `openshift-machine-config-operator` namespace, including node disruption
  policy configuration.
- **KubeletConfig** and **ContainerRuntimeConfig**: supported custom resources
  for kubelet and CRI-O settings that generate machine configs.
- **PinnedImageSet**: an official OCP resource for documented cases where
  nodes must preload selected images and avoid garbage collection removing
  them. Do not use it as a general repeatability mechanism for this demo.
- **Image mode for OpenShift**: builds or applies custom layered RHCOS images
  with `MachineOSConfig` and `MachineOSBuild` when the documented limitations
  and registry requirements are acceptable.
- **Machine Config Daemon metrics and logs**: indicate node-level update,
  drain, pivot, reboot, kubelet, and degraded-state problems.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - `MachineConfig` files, systemd, kernel arguments, extensions, firmware, or
     host access configuration
   - node disruption policies through `MachineConfiguration`
   - kubelet settings through `KubeletConfig`
   - CRI-O settings through `ContainerRuntimeConfig`
   - `PinnedImageSet` image preloading
   - boot image management or rendered machine config pruning
   - image mode with `MachineOSConfig` or `MachineOSBuild`
   - Machine Config Daemon metrics, logs, drift, pool status, or degraded state
4. For GitOps manifests, verify the target pool, labels, CRD fields, and
   disruption behavior before writing resources.
5. For live operations, use the repo environment guard and pair this skill with
   `env-manage-resources`, `env-troubleshoot`, or `env-deploy-and-evaluate`.
6. Validate the output with `references/validation-checklist.md`.

## Related Skills

- Use `ocp-machine-management` for Machine API, MachineSet, autoscaling, and
  cloud machine lifecycle.
- Use `ocp-nodes` for labels, taints, drain, schedulability, node health, and
  pod placement.
- Use `ocp-etcd` before any control plane or cluster-wide change that could
  affect quorum, upgrades, or cluster operator stability.
- Use `ocp-node-feature-discovery` for specialized hardware labels.
- Use `rhoai-nvidia-gpu-accelerators` for GPU workers, accelerator profiles,
  NVIDIA GPU Operator handoff, and RHOAI GPU scheduling intent.
- Use `project-gitops-authoring` and `project-manifest-review` for manifests.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/machine-config-review-patterns.md`
