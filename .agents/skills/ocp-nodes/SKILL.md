---
name: ocp-nodes
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing node labels, taints, tolerations and pod placement in this
  repo (GPU node label cluster-api/accelerator, taint nvidia-gpu-only:NoSchedule,
  Kueue ResourceFlavor nodeLabels and tolerations, ClusterPolicy tolerations),
  node sizing checks in `require_node_sizing` in `scripts/lib.sh`, or diagnosing
  DiskPressure, KubeNodeEviction and ephemeral-storage evictions on CPU or GPU
  workers. Do NOT use for MachineSet lifecycle and scaling (use
  ocp-machine-management), host OS or kubelet configuration (use
  ocp-machine-configuration), or Kueue quota design (use
  rhoai-kueue-workload-management).
---

# OCP nodes

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift Container Platform 4.22 sections. Detailed records:
`gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-machinesets/README.md` and
`gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-quotas/README.md`.

## When to use

- A workload must land on, or stay off, the GPU workers.
- A change touches a taint, toleration, `nodeSelector` or Kueue flavor
  `nodeLabels`.
- Nodes report `DiskPressure`, pods are `Evicted`, or a deploy stops in
  `require_node_sizing`.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| GPU workers carry `cluster-api/accelerator` (`nvidia-rtxpro6000` or `nvidia-gpu`), `node-role.kubernetes.io/gpu` and `demo.rhoai.io/gpu-pool` labels from the MachineSet template | `020-gpu-machinesets/` | [Controlling pod placement onto nodes (scheduling)][placement] |
| GPU workers are tainted `nvidia-gpu-only:NoSchedule` so non-GPU pods stay off them | `020-gpu-machinesets/` | [Controlling pod placement onto nodes (scheduling)][placement] |
| Tolerations live with the GPU consumers: NVIDIA `ClusterPolicy`, each Kueue GPU `ResourceFlavor` (which also selects its pool by `nodeLabels`), and the Qwen `LLMInferenceService` | `020-nvidia-gpu-operator/cluster-policy.yaml`, `020-gpu-quotas/queues/gpu-rtxpro6000.yaml`, `020-gpu-quotas/queues/gpu-l40s.yaml`, `gitops/stages/040-governed-models-as-a-service/040-local-models/qwen38-27b-llminferenceservice.yaml` | [Controlling pod placement onto nodes (scheduling)][placement] |
| Workloads reach a GPU pool through a Kueue flavor, not a hand-written `nodeSelector` | `020-gpu-quotas/queues/` | [Controlling pod placement onto nodes (scheduling)][placement] |
| Control-plane and CPU workers must be at least 16 vCPU / 60 GiB (GPU nodes exempt); every stage `deploy.sh` checks it first | `require_node_sizing` in `scripts/lib.sh` | [Working with nodes][nodes] |
| Platform and user-workload Prometheus use PVCs instead of `emptyDir`, to keep TSDB growth off node ephemeral storage | `gitops/stages/010-openshift-ai-platform-foundation/010-observability-operators/cluster-monitoring/` | [Working with nodes][nodes] |
| No custom scheduler profile, `PriorityClass`, node tuning or descheduler | (none declared) | [Controlling pod placement onto nodes (scheduling)][placement] |

Paths are relative to `gitops/stages/020-gpu-infrastructure-private-ai/` unless they start with `gitops/` or `scripts/`.

## Procedure

1. Change labels and taints only in the MachineSet template (regenerate with
   `stages/020-gpu-infrastructure-private-ai/deploy.sh --generate-machinesets`, see `ocp-machine-management`); add a
   matching toleration to every GPU consumer in the same change.
2. Validate: `./stages/020-gpu-infrastructure-private-ai/validate.sh` checks
   that each Ready GPU node allocates one `nvidia.com/gpu`, has its pool's GPU
   product label and the `nvidia-gpu-only` taint, and that each GPU flavor
   selects exactly its own pool.
3. Read-only checks after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get nodes -L cluster-api/accelerator,demo.rhoai.io/gpu-pool
   oc get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints
   oc describe node <node> | grep -A6 Conditions:
   oc get --raw /api/v1/nodes/<node>/proxy/stats/summary   # per-pod ephemeral storage
   ```

## Pitfalls

- Node labels and taints set by `oc label`/`oc adm taint` are lost when the
  Machine is replaced; only the MachineSet template is durable.
- llm-d router-scheduler pods run on CPU workers and pin the full modelcar
  image (~30-37 GiB); `LLMInferenceService.spec.router.scheduler` exposes no
  placement fields, so they cannot be moved to GPU nodes
  (`docs/TROUBLESHOOTING.md#worker-nodes-evict-pods-after-a-cluster-resume-kubenodeeviction`).
- Image pruning (`crictl rmi --prune`) never removes an in-use modelcar
  (`docs/TROUBLESHOOTING.md#pipeline-or-workspace-pods-evicted-for-ephemeral-storage`).
- A 100 GB GPU root disk hits DiskPressure while pulling a large modelcar
  (`docs/TROUBLESHOOTING.md#model-image-pull-stalls-on-a-gpu-node`).
- `TaintManagerEviction` events right after a sandbox resume are benign.
- Node drain, reboot, cordon and taint changes on a live cluster are
  live-environment operations (`.agents/rules/ocp.md`).

## Official documentation (OpenShift Container Platform 4.22)

| Topic | Section |
|---|---|
| Overview | [Overview of nodes][overview] |
| Placement | [Controlling pod placement onto nodes (scheduling)][placement] |
| Nodes | [Working with nodes][nodes], [Node metrics dashboard][dashboard] |
| Pods and containers | [Working with pods][pods], [Working with containers][containers] |
| Cluster-wide | [Working with clusters][clusters] |

## Related skills

`ocp-machine-management`, `ocp-machine-configuration`,
`ocp-node-feature-discovery`, `rhoai-kueue-workload-management`,
`rhoai-hardware-profiles`, `rhoai-nvidia-gpu-accelerators`.

[overview]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/nodes/index#overview-of-nodes
[pods]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/nodes/index#working-with-pods
[placement]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/nodes/index#controlling-pod-placement-onto-nodes-scheduling
[nodes]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/nodes/index#working-with-nodes
[containers]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/nodes/index#working-with-containers
[clusters]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/nodes/index#working-with-clusters
[dashboard]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/nodes/index#nodes-dashboard-using
