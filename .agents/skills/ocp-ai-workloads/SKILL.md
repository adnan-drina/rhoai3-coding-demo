---
name: ocp-ai-workloads
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding OpenShift Container Platform AI
  workload platform guidance from official OCP documentation: Red Hat build of
  Kueue, Kueue custom resources, ClusterQueue, ResourceFlavor, LocalQueue,
  Workload, queue labels, quotas, RBAC, cohorts, fair sharing, gang scheduling,
  pending workload visibility, Leader Worker Set Operator, LeaderWorkerSet,
  JobSet Operator, JobSet, and coordinated AI training or inference workload
  scheduling. Do NOT use for RHOAI dashboard, DataScienceCluster, workbenches,
  or OpenShift AI distributed workload component configuration; use the
  relevant rhoai-* skill. Do NOT run live queue, quota, RBAC, or operator
  changes without the env safety guard and explicit approval.
---

# OCP AI Workloads

Use this skill to ground OpenShift AI workload platform guidance in the
official OpenShift Container Platform AI workloads guide for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers OCP platform
operators and Kubernetes APIs for AI workload scheduling and coordination; it
does not replace RHOAI component skills, GPU enablement skills, or live
environment skills.

## Demo AI Workload Posture

For this AWS-hosted RHOAI demo:

- Treat Red Hat build of Kueue as an OpenShift platform scheduling and quota
  layer for batch, distributed, and GPU-constrained workloads.
- Use Kueue queues to make limited GPU capacity explicit before RHOAI or demo
  workloads consume it.
- Keep RHOAI component enablement in `rhoai-kueue-workload-management`,
  `rhoai-distributed-workload-operations`, and related `rhoai-*` skills.
- Use `ocp-node-feature-discovery`, `ocp-nodes`, and
  `rhoai-nvidia-gpu-accelerators` before claiming that GPU queues map to real
  GPU capacity.
- Verify installed Operator versions, channels, CRDs, API groups, and support
  posture before writing README claims or GitOps manifests.

## OCP AI Workload Model

Use the official docs to frame:

- **Red Hat build of Kueue**: Kubernetes-native resource access management for
  jobs, including waiting, admission, and preemption.
- **Kueue custom resource**: cluster-level Kueue configuration, including
  framework integrations, preemption policy, fair sharing, and gang scheduling.
- **ClusterQueue**: cluster-scoped quota pool for covered resources and
  resource flavors.
- **ResourceFlavor**: named resource variation associated with node labels,
  taints, and tolerations.
- **LocalQueue**: namespaced queue that points workloads in a namespace to a
  `ClusterQueue`.
- **Workload**: Kueue representation of a submitted job or integrated workload.
- **LeaderWorkerSet**: coordinated groups of leader and worker pods for
  distributed inference or sharded model serving workloads.
- **JobSet**: coordinated groups of Kubernetes Jobs for large-scale training,
  HPC, and related batch workloads.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - Red Hat build of Kueue installation, upgrade, or disconnected install
   - `Kueue` custom resource configuration
   - namespace opt-in with `kueue.openshift.io/managed=true`
   - `ClusterQueue`, `ResourceFlavor`, `LocalQueue`, or `Workload` resources
   - RBAC with `kueue-batch-admin-role` or `kueue-batch-user-role`
   - quotas, cohorts, fair sharing, gang scheduling, or visibility API use
   - Leader Worker Set Operator or `LeaderWorkerSet`
   - JobSet Operator or `JobSet`
4. For GitOps manifests, verify API versions and CR fields against official
   docs or the active cluster schema before committing.
5. For live operations, use the repo environment guard and pair this skill with
   `env-troubleshoot`, `env-manage-resources`, or `env-deploy-and-evaluate`.
6. Validate the output with `references/validation-checklist.md`.

## Related Skills

- Use `rhoai-kueue-workload-management` for RHOAI-managed Kueue component
  enablement and RHOAI-specific dashboard behavior.
- Use `rhoai-distributed-workload-operations` and
  `rhoai-distributed-workload-workflows` for OpenShift AI distributed workload
  administration and data scientist workflows.
- Use `rhoai-distributed-inference-llmd` for llm-d and RHOAI distributed
  inference.
- Use `ocp-node-feature-discovery`, `ocp-machine-management`, `ocp-nodes`, and
  `rhoai-nvidia-gpu-accelerators` for GPU worker capacity and placement.
- Use `project-gitops-authoring` and `project-manifest-review` for manifests.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/ai-workload-review-patterns.md`
