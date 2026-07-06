---
name: rhoai-kueue-workload-management
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift AI workload
  management with Kueue: Red Hat build of Kueue Operator integration,
  DataScienceCluster kueue managementState, migration from embedded Kueue,
  namespace queue enforcement with kueue.openshift.io/managed=true,
  workload queue labels, dashboard enablement with disableKueue=false,
  Kueue-enabled hardware profile restrictions, default ClusterQueue and
  LocalQueue behavior, and documented Kueue troubleshooting signals. Do NOT use
  for initial distributed workload component installation or Ray/Kubeflow
  Training Operator installation; use rhoai-distributed-workloads. Do NOT use
  for distributed workload ResourceFlavor, ClusterQueue, LocalQueue, RDMA, or
  Ray administrator troubleshooting; use
  rhoai-distributed-workload-operations. Do NOT use for user workflows that run
  Ray, PyTorchJob, or TrainJob workloads; use
  rhoai-distributed-workload-workflows. Do NOT use for GPU node scaling or live
  cluster changes without the OpenShift safety guard.
---

# RHOAI Kueue Workload Management

Use this skill to manage RHOAI integration with the Red Hat build of Kueue for
the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official Kueue workload-management chapter to this repo's GitOps review model.

## Scope

This skill covers:

- RHOAI integration with the Red Hat build of Kueue Operator
- `DataScienceCluster.spec.components.kueue.managementState`
- migration from deprecated embedded Kueue to Red Hat build of Kueue Operator
- queue enforcement on namespaces labeled
  `kueue.openshift.io/managed=true`
- workload `kueue.x-k8s.io/queue-name` label requirements
- dashboard enablement through `OdhDashboardConfig`
- Kueue-enabled hardware profile restrictions
- default `ClusterQueue` and namespace `LocalQueue` behavior
- documented Kueue troubleshooting patterns

This skill does not cover distributed workload quota resource authoring,
`ResourceFlavor`, `ClusterQueue`, or `LocalQueue` schema beyond the RHOAI
integration points. Use `rhoai-distributed-workload-operations` for the
official RHOAI distributed workload quota chapter and use Red Hat build of
Kueue documentation only as supplemental object detail. Use `ocp-ai-workloads`
for OCP Red Hat build of Kueue Operator installation, Kueue API behavior,
Leader Worker Set Operator, and JobSet Operator platform guidance.

Use `rhoai-distributed-workload-workflows` for data scientist workflows that
submit Ray, PyTorchJob, TrainJob, fine-tuning, checkpointing, and monitoring
workloads after queue policy is in place.

## Demo Policy

For this repo:

- Use `Unmanaged` Kueue in `DataScienceCluster` so RHOAI integrates with the
  Red Hat build of Kueue Operator.
- Do not use deprecated embedded Kueue `Managed` mode.
- Do not install embedded Kueue and the Red Hat build of Kueue Operator on the
  same cluster.
- Enable Kueue in the dashboard only after the Red Hat build of Kueue Operator,
  cert-manager, and quota resources are ready.
- Label existing demo namespaces explicitly with
  `kueue.openshift.io/managed=true` when they should enforce queue usage.
- Ensure dashboard-created workloads use hardware profiles with a local queue.
- Do not use node selectors or tolerations in Kueue-enabled hardware profiles;
  use resource flavors and queues for placement.
- Keep queue and quota objects GitOps-managed when the active implementation
  introduces them.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Confirm installation prerequisites with `rhoai-distributed-workloads`.
3. Read `references/official-doc-extraction.md`.
4. Decide whether the task is:
   - activating Kueue integration
   - enabling Kueue in the dashboard
   - enabling queue enforcement for projects
   - creating Kueue-enabled hardware profile guidance
   - troubleshooting queue or webhook failures
   - migrating from embedded Kueue
5. Use `examples/kueue-workload-management-patterns.md` for review patterns.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/kueue-workload-management-patterns.md`
