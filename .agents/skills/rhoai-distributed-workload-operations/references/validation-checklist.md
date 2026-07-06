# Validation Checklist

Use this checklist before accepting distributed workload quota, RDMA, or
troubleshooting content.

## Source And Scope

- The work references the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official chapter URL uses the active `/3.4/` baseline path, not an
  unversioned latest documentation path.
- The task belongs to day-2 distributed workload operations. If it is initial
  component installation, use `rhoai-distributed-workloads`.
- RHOAI/Kueue dashboard integration, namespace enforcement, and embedded Kueue
  migration remain in `rhoai-kueue-workload-management`.
- GPU enablement remains in `rhoai-nvidia-gpu-accelerators`.

## Quota Resource Review

- `ResourceFlavor`, `ClusterQueue`, and `LocalQueue` use
  `apiVersion: kueue.x-k8s.io/v1beta1`.
- NVIDIA queues use `nvidia.com/gpu`.
- AMD resources are absent unless explicitly requested.
- No shared cohorts are configured for the OpenShift AI 3.4 baseline.
- `ClusterQueue.spec.resourceGroups[].coveredResources` includes every
  requestable resource.
- Each covered resource has a matching `resources[].name` and `nominalQuota`,
  even when the quota is `0`.
- `ResourceFlavor.spec.nodeLabels` values are verified against live node
  labels or left as placeholders in examples.
- `LocalQueue.metadata.namespace` is the intended data science project
  namespace.
- Existing dashboard-created default `LocalQueue` objects are reviewed before
  adding custom ones.

## RDMA Review

- RDMA is marked optional and not enabled by default.
- The environment has multiple compatible NVIDIA GPU worker nodes before RDMA
  manifests are introduced.
- NVIDIA GPU support, NVIDIA `ClusterPolicy` RDMA state, NVIDIA Network
  Operator, and optional SR-IOV requirements are documented.
- MachineConfig changes are treated as disruptive because worker nodes restart.
- NCCL verification variables are included only in training workload examples
  that need RDMA validation.

## Troubleshooting Review

- Ray suspended, failed, and stuck-starting diagnostics inspect
  `Workload.status.conditions.message`.
- Ray cluster diagnostics inspect `RayCluster.status.conditions.message` when
  applicable.
- KubeRay pod health and logs are checked for cluster start failures.
- `403` errors on `rayclusters.ray.io` point to notebook
  `TokenAuthentication` credentials and user group membership checks.
- Uncovered problems are escalated with evidence instead of speculative fixes.

## Static Checks

Run the repo whitespace check and the focused stale-marker search from
`project-rhoai-doc-chapter-skill-authoring` against this skill directory.
