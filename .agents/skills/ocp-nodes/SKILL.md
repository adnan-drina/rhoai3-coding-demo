---
name: ocp-nodes
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding OpenShift Container Platform
  node guidance from official OCP documentation: node and pod overview,
  containers, pod autoscaling, pod scheduling and placement, scheduler
  profiles, pod affinity and anti-affinity, node affinity, node selectors,
  taints and tolerations, topology spread constraints, descheduler, secondary
  scheduler, jobs, daemon sets, viewing nodes and pods on nodes, node labels,
  cordon/drain/unschedulable behavior, node deletion, node modification,
  control-plane schedulability, kernel arguments, swap, image pulls, maximum
  pods per node, Node Tuning Operator, node rebooting, garbage collection, node
  metrics, remote workers, single-node OpenShift worker behavior, and sigstore.
  Do NOT use for MachineSet or cloud instance provisioning; use future
  ocp-machine-management-aws. Do NOT use for RHOAI GPU hardware profiles or
  accelerator component behavior; use rhoai-nvidia-gpu-accelerators. Do NOT run
  live cluster operations without the env safety guard.
---

# OCP Nodes

Use this skill to ground OpenShift node, pod placement, node operations,
resource review, and node-health runbooks in the official OpenShift Container
Platform Nodes guide for the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers OCP node and
scheduling behavior; it does not replace Machine API, MachineSet, Node Feature
Discovery, GPU Operator, or RHOAI accelerator skills.

## Demo Node Posture

For this AWS-hosted RHOAI demo:

- Discover node labels, taints, capacity, allocatable resources, and conditions
  from the target cluster before writing placement rules.
- Keep GPU node lifecycle and AWS instance provisioning in future
  `ocp-machine-management-aws` and existing `rhoai-nvidia-gpu-accelerators`
  handoffs.
- Use node selectors, node affinity, taints, tolerations, and topology spread
  intentionally; avoid over-constraining pods so they cannot schedule.
- Treat node drain, reboot, deletion, control-plane schedulability, kernel
  arguments, swap, maximum-pods-per-node, and Node Tuning Operator changes as
  live platform operations that require explicit approval.
- Keep RHOAI component resource requests and limits in `rhoai-*` skills; use
  this skill for the OpenShift scheduling and node mechanics around them.

## OCP Node Model

Use the official docs to frame:

- **Nodes**: worker or control-plane machines that run pods and expose
  capacity, allocatable resources, labels, taints, conditions, and metrics.
- **Pods**: the unit scheduled onto nodes, with scheduling shaped by resource
  requests, affinity, selectors, tolerations, topology spread, and scheduler
  behavior.
- **Containers**: application runtime units inside pods, with operations such
  as logs, exec, file copy, and port forwarding.
- **Scheduling controls**: cluster scheduler profiles, pod affinity, node
  affinity, taints/tolerations, node selectors, topology spread constraints,
  descheduler, and secondary scheduler.
- **Node operations**: listing, inspecting, cordoning, draining, labeling,
  deleting, rebooting, garbage collection, and resource monitoring.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - node inventory and health
   - pod scheduling or placement
   - labels, taints, tolerations, or selectors
   - autoscaling, jobs, daemon sets, or pod lifecycle
   - node maintenance, drain, reboot, deletion, or tuning
   - node metrics and troubleshooting
4. For GitOps manifests, verify all labels, taints, scheduler names, and
   topology keys against the target cluster before committing placement rules.
5. For live operations, use the repo environment guard and pair this skill with
   `env-troubleshoot`, `env-manage-resources`, or `env-deploy-and-evaluate`.
6. Validate the output with `references/validation-checklist.md`.

## Related Skills

- Use `ocp-storage` for node-related volume attachment and storage behavior.
- Use future `ocp-machine-management-aws` for AWS MachineSets, node creation,
  and instance lifecycle.
- Use `ocp-node-feature-discovery` for NFD-specific labels and
  specialized hardware detection.
- Use `rhoai-nvidia-gpu-accelerators` for NVIDIA GPU enablement and RHOAI
  hardware profile intent.
- Use `rhoai-component-resource-customization` for RHOAI component resource
  requests and limits.
- Use `project-gitops-authoring` and `project-manifest-review` for manifests.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/node-placement-patterns.md`
