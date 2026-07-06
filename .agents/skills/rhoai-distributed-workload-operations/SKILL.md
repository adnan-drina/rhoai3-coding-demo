---
name: rhoai-distributed-workload-operations
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift AI
  distributed workload operations from the Administer documentation: Kueue
  ResourceFlavor, ClusterQueue, and LocalQueue quota resources for distributed
  workloads; NVIDIA GPU quota examples; RDMA setup boundaries; and
  administrator troubleshooting for RayCluster, RayJob, PyTorchJob, KubeRay,
  CodeFlare, and Kueue Workload status. Do NOT use for initial distributed
  workload component installation; use rhoai-distributed-workloads. Do NOT use
  for RHOAI/Kueue dashboard integration, embedded Kueue migration, or namespace
  enforcement setup; use rhoai-kueue-workload-management. Do NOT use for GPU
  enablement; use rhoai-nvidia-gpu-accelerators. Do NOT use for user workflows
  that run Ray, PyTorchJob, or TrainJob workloads; use
  rhoai-distributed-workload-workflows. For live cluster diagnostics, pair with
  env-troubleshoot and the OpenShift safety guard.
---

# RHOAI Distributed Workload Operations

Use this skill to manage distributed workload quotas, RDMA readiness, and
administrator troubleshooting on the active product baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official Administer chapter to this repo's GitOps and NVIDIA-first demo model.

## Demo Policy

For this repo:

- Use NVIDIA GPU resources by default with `nvidia.com/gpu`.
- Do not create AMD GPU queue examples unless the user explicitly asks for AMD
  coverage.
- Do not use shared cohorts for OpenShift AI 3.4 distributed workload queues.
- Treat RDMA as optional advanced infrastructure. Do not enable it unless the
  active environment has supported NVIDIA GPUs, compatible accelerated
  networking, and an explicit implementation need.
- Keep Kueue quota resources GitOps-managed once the active implementation
  introduces them.
- Use `ocp-ai-workloads` for OCP Kueue API behavior, Leader Worker Set
  Operator, JobSet Operator, and platform queue/quota references before
  treating them as RHOAI-specific guidance.
- Keep user-facing Ray, PyTorchJob, TrainJob, fine-tuning, checkpointing,
  monitoring, and troubleshooting workflows in
  `rhoai-distributed-workload-workflows`.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Confirm distributed workload components were installed with
   `rhoai-distributed-workloads`.
3. Confirm RHOAI/Kueue integration and namespace enforcement with
   `rhoai-kueue-workload-management`.
4. Read `references/official-doc-extraction.md`.
5. For quota work, define or review:
   - `ResourceFlavor`
   - `ClusterQueue`
   - project `LocalQueue`
   - requested CPU, memory, and GPU quotas
6. For RDMA work, verify the environment supports the official prerequisites
   before authoring MachineConfig, NVIDIA Network Operator, or PyTorchJob
   changes.
7. For troubleshooting, inspect `Workload.status.conditions.message`,
   `RayCluster.status.conditions.message`, KubeRay pod health, and pod events.
8. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/distributed-workload-operations-patterns.md`
