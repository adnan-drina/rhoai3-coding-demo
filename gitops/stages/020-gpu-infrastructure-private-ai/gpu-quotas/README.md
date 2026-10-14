# GPU quotas and hardware profiles (`020-gpu-quotas`)

This Application turns GPU and CPU capacity into Kueue quota and OpenShift AI hardware profiles. It defines one
ResourceFlavor per GPU type, one ClusterQueue per GPU type plus a CPU queue, the LocalQueues in `demo-sandbox`, and
three global hardware profiles. Users pick a profile in the OpenShift AI dashboard; Kueue admits the workload
against the queue and the flavor places it on the right GPU pool. Stage 040 and 050 model servers and the
`demo-sandbox` workbenches consume it.

| | |
|---|---|
| Argo CD Application | `020-gpu-quotas` ([manifest](../../../argocd/app-of-apps/020-gpu-infrastructure-private-ai/gpu-quotas.yaml)) |
| Deployed by | [`stages/020-gpu-infrastructure-private-ai/deploy.sh`](../../../../stages/020-gpu-infrastructure-private-ai/deploy.sh) (deploy-order 3) |
| Validated by | [`stages/020-gpu-infrastructure-private-ai/validate.sh`](../../../../stages/020-gpu-infrastructure-private-ai/validate.sh) (`Each GPU ResourceFlavor selects exactly its own pool`, ClusterQueue and LocalQueue `Active`, HardwareProfile queue identity) |
| Sync | Automated, prune and self-heal; `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`; Server-Side Diff by compare-options annotation; retry 10, 5s to 3m |
| Depends on | `020-kueue` (Kueue CRDs and controller); Stage 010 (HardwareProfile CRD from OpenShift AI, namespace `demo-sandbox` labelled `kueue.openshift.io/managed: "true"`); `020-gpu-machinesets` (node label `cluster-api/accelerator` and taint `nvidia-gpu-only`) |
| Used by | Stage 040 `local-models` (LocalQueues in `internal-models`, `gpu-rtxpro6000` profile on the Qwen model); Stage 050 `model-qualification` (LocalQueues in `evaluated-models`); dashboard workbenches in `demo-sandbox` |

## Why

OpenShift AI uses Kueue for quota and admission. In a Kueue-managed namespace, workloads must carry the
`kueue.x-k8s.io/queue-name` label, and dashboard-created workloads get it from a hardware profile that names a
local queue [1]. With `autoCreateQueues: false` the administrator creates ResourceFlavors, ClusterQueues and
LocalQueues [1]. A queue-based hardware profile needs that LocalQueue in the target project; a global profile
needs a queue name that exists in every user project [2].

One ClusterQueue per GPU type is a deliberate choice. A hardware profile names one LocalQueue, and inside one
ClusterQueue Kueue picks the first flavor that fits, so a single GPU queue with two flavors would not let a user
choose the GPU type (comment in `queues/cq-gpu-rtxpro6000.yaml`).

Quota and profiles change more often than the operators, so they are their own Application.

## What

Queues (`queues/`):

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ResourceFlavor | `default-flavor` | cluster-scoped | CPU and memory, no node selection (wave 4) |
| ResourceFlavor | `gpu-l40s` | cluster-scoped | `nodeLabels: cluster-api/accelerator=nvidia-gpu` (L40S pool), tolerates `nvidia-gpu-only:NoSchedule` (wave 4) |
| ResourceFlavor | `gpu-rtxpro6000` | cluster-scoped | `nodeLabels: cluster-api/accelerator=nvidia-rtxpro6000`, tolerates `nvidia-gpu-only:NoSchedule` (wave 4) |
| ClusterQueue | `cq-cpu-default` | cluster-scoped | 40 CPU, 128Gi on `default-flavor` (wave 4) |
| ClusterQueue | `cq-gpu-reserved-demo` | cluster-scoped | 12 CPU, 48Gi, 2 `nvidia.com/gpu` on `gpu-l40s` (wave 4) |
| ClusterQueue | `cq-gpu-rtxpro6000` | cluster-scoped | 14 CPU, 112Gi, 2 `nvidia.com/gpu` on `gpu-rtxpro6000` (wave 4) |
| LocalQueue | `lq-cpu-default` | `demo-sandbox` | Points to `cq-cpu-default` (wave 5) |
| LocalQueue | `lq-gpu-reserved-demo` | `demo-sandbox` | Points to `cq-gpu-reserved-demo` (wave 5) |
| LocalQueue | `lq-gpu-rtxpro6000` | `demo-sandbox` | Points to `cq-gpu-rtxpro6000` (wave 5) |

Hardware profiles (`hardware-profiles/`):

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| HardwareProfile | `cpu-default` | `redhat-ods-applications` | "CPU Default": CPU 1-8 (default 2), memory 2-64Gi (default 8Gi), queue `lq-cpu-default` (wave 5) |
| HardwareProfile | `gpu-reserved-demo` | `redhat-ods-applications` | "NVIDIA L40S (48 GB) - Demo Team": CPU 1-8, memory 2-64Gi, 1 `nvidia.com/gpu`, queue `lq-gpu-reserved-demo` (wave 5) |
| HardwareProfile | `gpu-rtxpro6000` | `redhat-ods-applications` | "NVIDIA RTX PRO 6000 Blackwell (96 GB)": CPU 1-7, memory 2-56Gi (default 16Gi), 1 `nvidia.com/gpu`, queue `lq-gpu-rtxpro6000` (wave 5) |

All objects carry `SkipDryRunOnMissingResource=true` because their CRDs come from operators.

Objects not in Git here: LocalQueues with the same names in `internal-models` (Stage 040 `local-models`) and
`evaluated-models` (Stage 050 `model-qualification`); Kueue `Workload` objects (Kueue controller); the
`default-profile` HardwareProfile (created by OpenShift AI).

## How

- **Ordering.** Flavors and ClusterQueues at wave 4, LocalQueues and hardware profiles at wave 5, so a LocalQueue
  is created after its ClusterQueue. On a fresh cluster the Application retries until `020-kueue` has installed the
  CRDs.
- **API version.** `kueue.x-k8s.io/v1beta2`. The Red Hat build of Kueue serves `v1beta2` since 1.3 and deprecates
  `v1beta1` [3]; the installed CRD stores `v1beta2`.
- **Flavors select by MachineSet label.** The GPU flavors match `cluster-api/accelerator`, which each GPU
  MachineSet stamps on its nodes from the moment they join. The earlier selector `nvidia.com/gpu.present` matched
  every NVIDIA node, so an L40S workload could land on another GPU type (comment in `queues/gpu-l40s.yaml`). The
  flavor also carries the toleration for the `nvidia-gpu-only` taint, so the hardware profiles do not need node
  selectors or tolerations.
- **Profiles are type `Queue` without node selectors or tolerations.** OpenShift AI does not allow node selectors
  or tolerations on queue-based profiles [1]; placement comes from the flavor.
- **Quota sizes.** Each GPU ClusterQueue has two GPUs, one per worker in a two-worker pool. CPU and memory quotas
  are below the allocatable capacity of two workers (for `g7e.2xlarge`, about 7.5 CPU and 58 GiB each, per the
  queue comment). The RTX PRO 6000 profile caps CPU at 7 and memory at 56Gi so one pod fits on one worker.
- **Preemption.** No cohorts and no preemption settings, so the defaults apply (live: `withinClusterQueue: Never`,
  `reclaimWithinCohort: Never`). Workbenches cannot be suspended and must use a non-preemptive ClusterQueue [1].
- **namespaceSelector `{}`.** Every namespace may use each ClusterQueue [3]; access is limited by which
  namespaces have a LocalQueue pointing to it.
- **No time-slicing.** Each GPU quota unit is one physical GPU.
- **ignoreDifferences / delegated fields.** None.
- **Secrets.** None.
- **Cluster-specific values.** None.

## Validation

`validate.sh` checks that `gpu-l40s` and `gpu-rtxpro6000` select exactly their own pool label and tolerate the
GPU taint; that the three ClusterQueues and their `demo-sandbox` LocalQueues are `Active` for the current
generation; that each hardware profile names `lq-<suffix>`; and that the two GPU LocalQueues are `Active` in
`internal-models` and `evaluated-models` (owned by Stages 040 and 050).

```bash
oc get clusterqueue,resourceflavor
oc get localqueue -A
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Queue ownership | With `autoCreateQueues: false`, create ResourceFlavor, ClusterQueue and per-project LocalQueue [1] | All declared in Git | Aligned |
| Namespace opt-in | Label managed namespaces `kueue.openshift.io/managed=true` [1][3] | `demo-sandbox` labelled by Stage 010 | Aligned |
| Hardware profile scheduling | Queue profiles name a LocalQueue; no node selectors or tolerations [1][2] | Three `Queue` profiles without them | Aligned |
| Global profile queues | A global profile's LocalQueue must exist in every user project [2] | Queues only in `demo-sandbox`, `internal-models`, `evaluated-models` | Deviation (justified: only these projects are meant to use the profiles; other projects would fail admission) |
| Workbench queues | Workbenches need a non-preemptive ClusterQueue [1] | `cq-cpu-default` has no preemption | Aligned |
| ResourceFlavor | Flavors can match node types by labels, taints and tolerations [3] | `nodeLabels` plus tolerations per GPU type | Aligned |
| ClusterQueue scope | Empty `namespaceSelector` lets all namespaces use the queue [3] | `{}` on all three | Aligned |
| API version | `v1beta2` current, `v1beta1` deprecated [3] | `v1beta2` | Aligned |
| L40S profile limits | Maximum allowed is the largest amount a user can request [2] | `gpu-reserved-demo` allows 8 CPU / 64Gi on an 8 vCPU / 64 GiB instance | Gap (maximum request cannot be scheduled on one L40S worker) |

## References

1. Managing workloads with Kueue, Managing OpenShift AI, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_openshift_ai/managing-workloads-with-kueue
2. Working with hardware profiles, Working with accelerators, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_accelerators/working-with-hardware-profiles_accelerators
3. Red Hat build of Kueue (release notes for 1.3; 2.3.5 Labeling namespaces; 2.9.1-2.9.3 Configuring a cluster queue, resource flavor and local queue), AI workloads, OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/ai_workloads/red-hat-build-of-kueue
