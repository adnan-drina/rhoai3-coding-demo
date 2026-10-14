# NVIDIA GPU Operator (`020-nvidia-gpu-operator`)

This Application installs the certified NVIDIA GPU Operator and its `ClusterPolicy`. The operator installs the
driver, container toolkit, device plugin, GPU Feature Discovery and DCGM exporter on every GPU node, so each GPU
shows up as one schedulable `nvidia.com/gpu` unit. The Application also publishes the NVIDIA DCGM dashboard in the
OpenShift console and lets OpenShift AI administrators query GPU metrics. Model serving in Stages 030 to 050
consumes the GPUs; administrators consume the dashboard.

| | |
|---|---|
| Argo CD Application | `020-nvidia-gpu-operator` ([manifest](../../../argocd/app-of-apps/020-gpu-infrastructure-private-ai/nvidia-gpu-operator.yaml)) |
| Deployed by | [`stages/020-gpu-infrastructure-private-ai/deploy.sh`](../../../../stages/020-gpu-infrastructure-private-ai/deploy.sh) (deploy-order 2) |
| Validated by | [`stages/020-gpu-infrastructure-private-ai/validate.sh`](../../../../stages/020-gpu-infrastructure-private-ai/validate.sh) (metrics Role binding, pinned dashboard, CSV, `ClusterPolicy` ready, validator/DCGM DaemonSets, per-node driver; `--functional` adds CUDA vectorAdd and DCGM metrics) |
| Sync | Automated, prune and self-heal; `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`; Server-Side Diff by compare-options annotation; retry 10, 5s to 3m |
| Depends on | `020-node-feature-discovery` (GPU node labels); `certified-operators` catalog; group `rhods-admins` and Role `cluster-monitoring-metrics-api` (platform monitoring) |
| Used by | `020-gpu-quotas` (GPU capacity behind the queues); Stage 030/040/050 model servers; `scripts/platform/resume-gpu-demo.sh` (waits for allocatable GPUs) |

## Why

OpenShift AI enables NVIDIA GPUs by installing the NFD Operator, then the NVIDIA GPU Operator with a
`ClusterPolicy` created from its default values [1]. NVIDIA documents the OpenShift installation and states that
the default `ClusterPolicy` values are enough in most cases (upstream) [2]. The operator owns all GPU node
software, so this repository never builds or patches drivers. The policy uses the OpenShift Driver Toolkit to
build the driver for the running RHCOS kernel.

The console dashboard follows NVIDIA's OpenShift procedure: a ConfigMap with the DCGM exporter dashboard JSON in
`openshift-config-managed` with the label `console.openshift.io/dashboard=true` (upstream) [3]. Querying cluster
GPU metrics needs the `cluster-monitoring-metrics-api` permissions in `openshift-monitoring` [4].

The operator, its policy, the dashboard and the metrics binding share one lifecycle (GPU node software and its
observability), so they form one Application.

## What

Operator installation:

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `nvidia-gpu-operator` | cluster-scoped | Operator namespace (the operator enables monitoring on it) |
| OperatorGroup | `nvidia-gpu-operator` | `nvidia-gpu-operator` | Targets only `nvidia-gpu-operator` |
| Subscription | `gpu-operator-certified` | `nvidia-gpu-operator` | Channel `v26.7`, `certified-operators`, Automatic approval (sync-wave 1) |
| ClusterPolicy | `gpu-cluster-policy` | cluster-scoped | Driver, toolkit, device plugin, GFD, DCGM, validator settings (sync-wave 2) |

GPU metrics access:

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| RoleBinding | `rhoai-gpu-metrics-admins` | `openshift-monitoring` | Binds group `rhods-admins` to the platform Role `cluster-monitoring-metrics-api` |

Console dashboard (`console-dashboard/`):

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ConfigMap | `nvidia-dcgm-exporter-dashboard` | `openshift-config-managed` | Generated from the local `dcgm-exporter-dashboard.json` (NVIDIA/dcgm-exporter commit `fafd1511`, Apache-2.0, `LICENSE` kept beside it); label `console.openshift.io/dashboard: "true"` |

Objects not in Git (operator-owned): the CSV; the operand DaemonSets in `nvidia-gpu-operator`
(`nvidia-driver-daemonset-<rhcos-version>`, container toolkit, device plugin, GFD, DCGM, DCGM exporter, node status
exporter, MIG manager, operator validator); the `gpu-operator`, `nvidia-dcgm-exporter` and
`nvidia-node-status-exporter` ServiceMonitors; the `nvidia.com/gpu.*` node labels. The Role
`cluster-monitoring-metrics-api` is owned by the Cluster Monitoring Operator. While the GPU pools are parked at
zero replicas, the operand DaemonSets schedule no pods and the `ClusterPolicy` still reports `ready`.

### `rhoai-monitoring/`: GPU metrics for OpenShift AI

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceMonitor | `accelerator-gpu-utilization` | `redhat-ods-monitoring` | Scrapes the DCGM exporter in `nvidia-gpu-operator` into the OpenShift AI datasource and renames DCGM series to the `accelerator_*` names the product LLM Utilization dashboard queries. Label `monitoring.opendatahub.io/scrape=true` |


## How

- **Installation.** Channel `v26.7`, Automatic approval, no `startingCSV`.
  `scripts/platform/check-operator-policy.py` requires the offered version to stay on 26.7 and at least `26.7.1`.
  Installed on this cluster: `gpu-operator-certified.v26.7.2`. NVIDIA's CLI example uses Manual approval [2];
  this repository uses Automatic approval within a reviewed channel (see `docs/migration/035-operator-automatic-policy.md`).
- **Ordering.** Subscription at wave 1, `ClusterPolicy` at wave 2 with `SkipDryRunOnMissingResource`, because its
  CRD comes from the CSV.
- **`ClusterPolicy` fields.** The spec is the operator's default example with these intentional choices:
  - `operator.use_ocp_driver_toolkit: true` and `driver.enabled: true`: the driver is built with the OpenShift
    Driver Toolkit, so its DaemonSet is named per RHCOS version [2]. `validate.sh` relies on that name.
  - `daemonsets.tolerations` adds `nvidia-gpu-only:NoSchedule` next to `nvidia.com/gpu`. The GPU MachineSets taint
    their nodes with `nvidia-gpu-only` (see `020-gpu-machinesets`); without this toleration no operand would run there.
  - `dcgmExporter.serviceMonitor.enabled: true`: DCGM metrics reach platform monitoring and the console dashboard.
  - No time-slicing or MIG partitioning is configured (`mig.strategy: single`, no device-plugin config): one
    physical GPU is one `nvidia.com/gpu` unit.
  - `driver.upgradePolicy.autoUpgrade: true` with drain disabled and `maxParallelUpgrades: 1`.
  - `sandboxWorkloads.enabled: false`, so the vGPU, VFIO, Kata and confidential-computing managers that are
    listed as enabled in the default example do not deploy.
- **Dashboard pinning.** `generatorOptions.disableNameSuffixHash: true` keeps the ConfigMap name stable. The JSON
  is stored in Git so a deploy never downloads the mutable upstream `main` file that NVIDIA's procedure uses [3].
  `validate.sh` checks its SHA-256.
- **Metrics access.** The RoleBinding gives `rhods-admins` the namespaced `cluster-monitoring-metrics-api` Role
  (Prometheus and Thanos Querier API access on port 9091) [4], not `cluster-monitoring-view` across the cluster.
- **ignoreDifferences / delegated fields.** None.
- **Secrets.** None. vGPU licensing (`licensingConfig.secretName`) is empty because vGPU is not used.
- **Cluster-specific values.** None.

- **GPU utilization ServiceMonitor.** The product LLM Utilization dashboard queries `accelerator_gpu_utilization` on the OpenShift AI datasource, and the generated collector job does not deliver it (`BACKLOG.md`, `docs/TROUBLESHOOTING.md`). This ServiceMonitor applies the same renames as the NVIDIA operator's own `nvidia-dcgm-exporter` PrometheusRule: `DCGM_FI_DEV_GPU_UTIL` to `accelerator_gpu_utilization`, `DCGM_FI_DEV_MEM_COPY_UTIL` to `accelerator_memory_used_bytes`, `DCGM_FI_DEV_FB_TOTAL` to `accelerator_memory_total_bytes`. It also derives `model_name` from the consuming pod name. The OpenShift AI guide documents the `monitoring.opendatahub.io/scrape=true` label on a workload's pod template and warns against adding it to operator-managed workloads [2]. The demo puts it on its own ServiceMonitor instead, so no operator-managed pod is changed. The repository records this as a workaround for an OpenShift AI 3.5.1 product gap (`BACKLOG.md`).

## Validation

`validate.sh --readiness` checks: the RoleBinding subject and the Role rules; the dashboard ConfigMap label,
tracking, title and SHA-256; the CSV `Succeeded`; `ClusterPolicy` state `ready`; `nvidia-operator-validator` and
`nvidia-dcgm-exporter` DaemonSets owned by the policy and ready on every GPU node; one current Driver Toolkit
driver DaemonSet per GPU node RHCOS version. `--functional` adds the CUDA vectorAdd validator result and a
port-forwarded DCGM `/metrics` scrape per node. GPU node checks fail while the pools are parked at zero.

```bash
oc get clusterpolicy gpu-cluster-policy -o jsonpath='{.status.state}{"\n"}'
oc get ds -n nvidia-gpu-operator
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Prerequisite order | NFD Operator and instance before the NVIDIA GPU Operator [1] | NFD is deploy-order 1, this Application deploy-order 2 | Aligned |
| Install source | `gpu-operator-certified` from `certified-operators`, namespace `nvidia-gpu-operator`, OperatorGroup targeting it (upstream) [2] | Same | Aligned |
| Approval | NVIDIA CLI example uses Manual approval (upstream) [2] | Automatic within channel `v26.7`, release family checked by `check-operator-policy.py` | Deviation (justified: repository operator policy; channel pins the major release) |
| `ClusterPolicy` content | Create from defaults; an empty spec fails (upstream) [2] | Default example plus GPU taint toleration | Aligned |
| Driver build | Driver Toolkit DaemonSet `nvidia-driver-daemonset-<RHCOS-version>` (upstream) [2] | `use_ocp_driver_toolkit: true` | Aligned |
| OpenShift AI dashboard refresh | After installing, delete `migration-gpu-status` ConfigMap and restart `rhods-dashboard` [1] | Not done by GitOps; the ConfigMap does not exist on this cluster | Gap (the one-time step is not documented in the stage runbook) |
| GPU verification | Node reports `nvidia.com/gpu` capacity; run a CUDA vectorAdd test [1][2] | `validate.sh` checks allocatable `nvidia.com/gpu=1` and the operator's CUDA validator | Aligned |
| Console dashboard | ConfigMap in `openshift-config-managed` labelled `console.openshift.io/dashboard=true` (upstream) [3] | Same, with pinned local JSON | Aligned |
| Metrics API access | Bind `cluster-monitoring-metrics-api` in `openshift-monitoring` for Prometheus/Thanos API access [4] | RoleBinding for `rhods-admins` | Aligned |

## References

1. Enable NVIDIA GPUs, Working with accelerators, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_accelerators/enabling-nvidia-gpus_accelerators
2. Installing the NVIDIA GPU Operator on OpenShift, NVIDIA GPU Operator on Red Hat OpenShift (latest) (upstream). https://docs.nvidia.com/datacenter/cloud-native/openshift/latest/install-gpu-ocp.html
3. Enabling the GPU Monitoring Dashboard, NVIDIA GPU Operator on Red Hat OpenShift (latest) (upstream). https://docs.nvidia.com/datacenter/cloud-native/openshift/latest/enable-gpu-monitoring-dashboard.html
4. Accessing monitoring APIs by using the CLI, Accessing metrics, Monitoring stack for Red Hat OpenShift 4.22. https://docs.redhat.com/en/documentation/monitoring_stack_for_red_hat_openshift/4.22/html/accessing_metrics/accessing-monitoring-apis-by-using-the-cli
