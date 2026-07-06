---
name: ocp-machine-management
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding OpenShift Container Platform
  machine management guidance from official OCP documentation: Machine API
  overview, compute machine sets, AWS compute MachineSets, provider-specific
  machine set fields, manual scaling, modifying machine sets, machine phases
  and lifecycle, deleting machines, cluster autoscaling, machine autoscaling,
  infrastructure machine sets, user-provisioned infrastructure machine
  management, control plane machine sets, control plane machine replacement,
  and machine health checks. Do NOT use for pod scheduling mechanics after a
  node exists; use ocp-nodes. Do NOT use for RHOAI hardware profiles or NVIDIA
  GPU Operator behavior; use rhoai-nvidia-gpu-accelerators. Do NOT run live
  machine operations without the env safety guard and explicit approval.
---

# OCP Machine Management

Use this skill to ground OpenShift Machine API, compute MachineSet, autoscaling,
control plane machine, and machine-health guidance in the official OpenShift
Container Platform Machine management guide for the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers machines and machine
lifecycle; it does not replace `ocp-nodes` for scheduling mechanics after a
node exists, `ocp-storage` for volume behavior, or RHOAI skills for accelerator
configuration.

## Demo Machine Posture

For this AWS-hosted RHOAI demo:

- Use AWS compute MachineSets as the normal GitOps path for adding GPU worker
  capacity after the active GitOps implementation is recreated.
- For demo.redhat.com AWS GPU workers, use the Red Hat CoP GPU Operator
  catalog's `aws-gpu-machineset` component as a generation pattern only:
  derive from an existing worker MachineSet, then capture reviewed GPU
  MachineSet and MachineAutoscaler resources in Git.
- Verify the existing cluster's Machine API namespace, provider spec, failure
  domains, subnets, security groups, IAM/profile references, AMI/image
  references, labels, taints, and autoscaler annotations before authoring a new
  MachineSet.
- Keep exact GPU instance type, desired node count, accelerator identifier, and
  RHOAI hardware-profile intent aligned with `rhoai-nvidia-gpu-accelerators`.
- Treat scale, delete, control plane replacement, machine health checks, and
  autoscaler changes as live platform operations requiring the repo
  environment guard and explicit approval.
- Do not use MachineSets as a shortcut for pod placement; create machines here,
  then use `ocp-nodes` and RHOAI skills for scheduling and workload placement.

## Machine Management Model

Use the official docs to frame:

- **Machine API**: OpenShift API layer for managing machine objects and
  provider-backed infrastructure after installation when supported.
- **Compute MachineSet**: manages groups of compute machines and supports
  scaling, labels, taints, provider-specific configuration, and special-purpose
  worker pools.
- **Machine lifecycle**: machine phases, ownership, provider state, node
  handoff, deletion, and replacement behavior.
- **Cluster autoscaler and machine autoscaler**: scale machine sets within
  configured limits based on pending workload demand and scale-down criteria.
- **Infrastructure MachineSets**: dedicated machines for infrastructure
  workloads when required by the cluster design.
- **ControlPlaneMachineSet**: automates supported control plane machine
  management and replacement on supported platforms.
- **MachineHealthCheck**: detects unhealthy machines and can trigger
  remediation according to the configured policy.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - compute MachineSet creation or modification
   - AWS provider-specific MachineSet settings
   - manual scaling or deletion
   - autoscaling with ClusterAutoscaler and MachineAutoscaler
   - infrastructure MachineSets
   - user-provisioned infrastructure
   - control plane machine sets or replacement
   - machine health checks
4. For GitOps manifests, verify the target cluster's existing machine set
   shape and provider spec before writing a new resource.
5. For GPU MachineSets, pair this skill with
   `rhoai-nvidia-gpu-accelerators` and keep instance type, labels, taints,
   replicas, and autoscaler bounds aligned with the NVIDIA/RHOAI handoff.
6. For live operations, use the repo environment guard and pair this skill with
   `env-manage-resources`, `env-troubleshoot`, or `env-deploy-and-evaluate`.
7. Validate the output with `references/validation-checklist.md`.

## Related Skills

- Use `ocp-nodes` for labels, taints, node health, and pod scheduling after
  machines become nodes.
- Use `ocp-storage` for volume attachment, storage classes, and PVC behavior.
- Use `ocp-node-feature-discovery` for NFD-specific hardware labels.
- Use `rhoai-nvidia-gpu-accelerators` for GPU worker intent, accelerator
  labels, hardware profiles, and RHOAI/NVIDIA component handoff.
- Use `project-gitops-authoring` and `project-manifest-review` for manifests.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/machineset-review-patterns.md`
