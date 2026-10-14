---
name: rhoai-distributed-workloads
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use for installing RHOAI distributed-workload components: Red Hat build of Kueue, cert-
  manager, DSC kueue/ray/trainingoperator/aipipelines/dashboard/workbenches states,
  GPU/RDMA and CA prerequisites, and component-pod validation. Do NOT use for Kueue day-2
  enforcement, embedded migration, administrator queues/RDMA, user Ray/PyTorchJob/TrainJob
  workflows, general installation, KFP authoring, SparkApplication activation or live
  troubleshooting; use the corresponding rhoai and environment skills.
---

# RHOAI Distributed Workloads

Use this skill to install and review the RHOAI distributed workloads component
set for the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official component installation guidance to this repo's GitOps operating model.

## Installation Model

Distributed workloads require both external Operators and
`DataScienceCluster` component state:

- Red Hat build of Kueue Operator must be installed separately.
- cert-manager Operator must be installed.
- `spec.components.kueue.managementState` must be `Unmanaged`, so the Red Hat
  build of Kueue Operator manages Kueue.
- `ray.managementState` is `Managed` when Ray/KubeRay workloads are needed.
- `trainingoperator.managementState` is `Managed` when Kubeflow Training
  Operator workloads are needed.
- `dashboard`, `aipipelines`, and `workbenches` states depend on whether
  distributed workloads are launched from pipelines, workbenches, or both.

## GitOps Policy

For this repo:

- Derive component state from the official table, but apply it through ArgoCD
  Applications and GitOps manifests.
- Keep prerequisite Operators in earlier or separate GitOps layers so
  `DataScienceCluster` does not enable distributed workload components before
  dependencies are available.
- Keep Kueue integration, namespace queue enforcement, dashboard Kueue
  enablement, and workload management policy in
  `rhoai-kueue-workload-management`.
- Keep `ResourceFlavor`, `ClusterQueue`, `LocalQueue`, RDMA, and Ray
  administrator troubleshooting in `rhoai-distributed-workload-operations`.
- Keep Ray, PyTorchJob, TrainJob, fine-tuning, checkpointing, monitoring, and
  user troubleshooting in `rhoai-distributed-workload-workflows`.
- Keep Kubeflow Spark Operator activation and `SparkApplication` resources in
  `rhoai-kubeflow-spark-operator`.
- If GPU-backed distributed workloads are part of the demo, pair this skill
  with accelerator/GPU skills and verify GPU support before enabling workloads.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Confirm RHOAI is installed with `rhoai-self-managed-installation`.
3. Verify prerequisites from `references/official-doc-extraction.md`.
4. Choose the launch surface:
   - pipelines only
   - workbenches only
   - pipelines and workbenches
5. Set the required `DataScienceCluster` component states from the official
   matrix.
6. Apply manifests through ArgoCD/GitOps.
7. Validate Kueue, KubeRay, and Kubeflow Training Operator deployments with
   `references/validation-checklist.md`.
8. Continue with `rhoai-kueue-workload-management` for queue enforcement,
   dashboard Kueue enablement, and migration.
9. Continue with `rhoai-distributed-workload-operations` for distributed
   workload quota resources, RDMA, and Ray administrator troubleshooting.
10. Continue with `rhoai-distributed-workload-workflows` for user-facing Ray,
    Training Operator, Kubeflow Trainer v2, checkpointing, and monitoring
    workflows.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/dsc-distributed-workloads-states.md`
