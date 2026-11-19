# NVIDIA GPU Operator (`020-nvidia-gpu-operator`)

This Application installs the certified NVIDIA GPU Operator and its `ClusterPolicy`. The operator installs the
driver, container toolkit, device plugin, GPU Feature Discovery and DCGM exporter on every GPU node, so each GPU
shows up as one schedulable `nvidia.com/gpu` unit. The Application also publishes the NVIDIA DCGM dashboard and the
NVIDIA GPU console plugin in the OpenShift console and lets OpenShift AI administrators query GPU metrics. Model serving in Stages 030 to 050
consumes the GPUs; administrators consume the dashboard.

| | |
|---|---|
| Argo CD Application | `020-nvidia-gpu-operator` ([manifest](../../../applications/020-nvidia-gpu-operator.yaml)) |
| Deployed by | [`stages/020-gpu-infrastructure-private-ai/deploy.sh`](../../../../stages/020-gpu-infrastructure-private-ai/deploy.sh) (deploy-order 2) |
| Validated by | [`stages/020-gpu-infrastructure-private-ai/validate.sh`](../../../../stages/020-gpu-infrastructure-private-ai/validate.sh) (metrics Role binding, pinned dashboard, CSV, `ClusterPolicy` ready, validator/DCGM DaemonSets, DCGM metric list and console plugin, per-node driver; `--functional` adds CUDA vectorAdd and DCGM metrics) |
| Sync | Automated, prune and self-heal; `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`; Server-Side Diff by compare-options annotation; retry 10, 5s to 3m |
| Depends on | `020-node-feature-discovery` (GPU node labels); `certified-operators` catalog; group `rhods-admins` and Role `cluster-monitoring-metrics-api` (platform monitoring); `010-console-observability` (enables `console-plugin-nvidia-gpu` in the console plugin list) |
| Used by | `020-gpu-quotas` (GPU capacity behind the queues); Stage 030/040/050 model servers; `stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus N` (waits for allocatable GPUs) |

## Why

OpenShift AI enables NVIDIA GPUs by installing the NFD Operator, then the NVIDIA GPU Operator with a
`ClusterPolicy` created from its default values [1]. NVIDIA documents the OpenShift installation and states that
the default `ClusterPolicy` values are enough in most cases (upstream) [2]. The operator owns all GPU node
software, so this repository never builds or patches drivers. The policy uses the OpenShift Driver Toolkit to
build the driver for the running RHCOS kernel.

The console dashboard follows NVIDIA's OpenShift procedure: a ConfigMap with the DCGM exporter dashboard JSON in
`openshift-config-managed` with the label `console.openshift.io/dashboard=true` (upstream) [3]. Querying cluster
GPU metrics needs the `cluster-monitoring-metrics-api` permissions in `openshift-monitoring` [4].

The console Cluster utilization card shows CPU, memory, filesystem, network and pods only. The NVIDIA GPU
administration dashboard is a dynamic console plugin that adds GPU rows to **Home > Overview** and a
**Compute > GPUs** page from DCGM exporter metrics; its install has the DCGM exporter collect a custom metric list (upstream) [5].
It uses the documented `console.cluster-overview/utilization-item` and related extension types [6].

The operator, its policy, the DCGM metric list, the dashboard, the console plugin and the metrics binding share one
lifecycle (GPU node software and its observability), so they form one Application.

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

DCGM metric list (`dcgm-metrics/`):

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ConfigMap | `nvidia-dcgm-metrics` | `nvidia-gpu-operator` | Key `dcgm-metrics.csv`, generated from the local `dcgm-metrics.csv`; read by `ClusterPolicy` `dcgmExporter.config.name` |
| PrometheusRule | `nvidia-dcgm-legacy-names` | `nvidia-gpu-operator` | Records `DCGM_FI_PROF_GR_ENGINE_ACTIVE`, `DCGM_FI_PROF_PIPE_TENSOR_ACTIVE`, `DCGM_FI_DEV_POWER_USAGE` and `DCGM_FI_DEV_GPU_TEMP` from their 4.9 names (platform monitoring evaluates it) |

Console plugin (`console-plugin/`, rendered from chart `console-plugin-nvidia-gpu` 0.3.0, Apache-2.0):

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Deployment | `console-plugin-nvidia-gpu` | `nvidia-gpu-operator` | Serves the plugin bundle over TLS on 9443; image `quay.io/edge-infrastructure/console-plugin-nvidia-gpu:release-0.3.0` pinned by digest |
| Service | `console-plugin-nvidia-gpu` | `nvidia-gpu-operator` | Port 9443; service CA writes the `plugin-serving-cert` Secret |
| ConsolePlugin | `console-plugin-nvidia-gpu` | cluster-scoped | Registers the bundle; display name `NVIDIA GPU` |

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
  `check_operator_policy` in `scripts/lib.sh` requires the offered version to stay on 26.7 and at least `26.7.1`.
  Installed on this cluster: `gpu-operator-certified.v26.7.2`. NVIDIA's CLI example uses Manual approval [2];
  this repository uses Automatic approval within a reviewed channel (see Fresh operator deployment in `docs/OPERATIONS.md`).
- **Ordering.** Subscription at wave 1, `ClusterPolicy` at wave 2 with `SkipDryRunOnMissingResource`, because its
  CRD comes from the CSV.
- **`ClusterPolicy` fields.** The spec is the operator's default example with these intentional choices:
  - `operator.use_ocp_driver_toolkit: true` and `driver.enabled: true`: the driver is built with the OpenShift
    Driver Toolkit, so its DaemonSet is named per RHCOS version [2]. `validate.sh` relies on that name.
  - `daemonsets.tolerations` adds `nvidia-gpu-only:NoSchedule` next to `nvidia.com/gpu`. The GPU MachineSets taint
    their nodes with `nvidia-gpu-only` (see `020-gpu-machinesets`); without this toleration no operand would run there.
  - `dcgmExporter.serviceMonitor.enabled: true`: DCGM metrics reach platform monitoring and the console dashboard.
  - `dcgmExporter.config.name: nvidia-dcgm-metrics`: the exporter collects the Git metric list (see DCGM metric list).
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
- **DCGM metric list.** GPU Operator v26.7 ships dcgm-exporter 4.9.0, which renamed its default metrics to DCGM 4.7
  names and changed some units (for example `DCGM_FI_DEV_GPU_UTIL` in percent became `DCGM_FI_DEV_GPU_UTIL_RATIO`) [7].
  The plugin 0.3.0, the pinned dashboard, the `rhoai-monitoring/` ServiceMonitor and `validate.sh --functional`
  still query the old names. A custom list replaces the exporter defaults, so `dcgm-metrics.csv` repeats the 4.9.0
  defaults and then adds the old names that are still their own DCGM field with the old unit (`GPU_UTIL`,
  `MEM_COPY_UTIL`, `FB_USED`, the clocks). The exporter exports one name per DCGM field and the first CSV row wins
  without a warning (seen live), so four old names share a field with a default and cannot come from the CSV:
  `nvidia-dcgm-legacy-names` records them from the new names, which have the same unit. The file was checked with
  `dcgm-exporter config explain -- --collectors <file>` on the running image (exit 0) and against live output. The
  upstream procedure installs the chart's 11-metric list as the whole list [5]; that would drop the 4.9 defaults.
- **Console plugin.** The upstream procedure installs the plugin with Helm and enables it with `oc patch` [5]. Here the chart was
  rendered once into plain manifests, as for GitLab in Stage 070: no Helm release, the image pinned by digest, the
  chart's test Pod and its unused `nginx-conf` volume (a ConfigMap the chart never creates) dropped, restricted pod
  security settings and small resource requests added. `010-console-observability` owns the console plugin list,
  so the plugin is enabled there, not by patch. Red Hat does not support custom plugin code [6]; the plugin is
  maintained by the Red Hat ecosystem edge team on GitHub.
- **ignoreDifferences / delegated fields.** None.
- **Secrets.** None. vGPU licensing (`licensingConfig.secretName`) is empty because vGPU is not used.
- **Cluster-specific values.** None.

- **GPU utilization ServiceMonitor.** The product LLM Utilization dashboard queries `accelerator_gpu_utilization` on the OpenShift AI datasource, and the generated collector job does not deliver it (`BACKLOG.md`, `docs/TROUBLESHOOTING.md`). This ServiceMonitor keeps only `DCGM_FI_DEV_GPU_UTIL` and renames it to `accelerator_gpu_utilization`, as the NVIDIA operator's `nvidia-dcgm-exporter` PrometheusRule does for cluster monitoring. It does not copy that rule's memory names: it maps `DCGM_FI_DEV_MEM_COPY_UTIL`, a percentage, to `accelerator_memory_used_bytes` and the MiB framebuffer total to `accelerator_memory_total_bytes`, so the units would be wrong; the collector already forwards the DCGM memory series [NVIDIA dcgm-exporter counters](https://github.com/NVIDIA/dcgm-exporter/blob/main/etc/default-counters.csv).

## Validation

`validate.sh --readiness` checks: the RoleBinding subject and the Role rules; the dashboard ConfigMap label,
tracking, title and SHA-256; the CSV `Succeeded`; `ClusterPolicy` state `ready`; `nvidia-operator-validator` and
`nvidia-dcgm-exporter` DaemonSets owned by the policy and ready on every GPU node; the `ClusterPolicy` reading
`nvidia-dcgm-metrics` with old and new names and the legacy-name rule, the plugin Deployment available, its `ConsolePlugin` backend and the
plugin enabled on the console; one current Driver Toolkit driver DaemonSet per GPU node RHCOS version. `--functional` adds the CUDA vectorAdd validator result and a
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
| Approval | NVIDIA CLI example uses Manual approval (upstream) [2] | Automatic within channel `v26.7`, release family checked by `check_operator_policy` | Deviation (justified: repository operator policy; channel pins the major release) |
| `ClusterPolicy` content | Create from defaults; an empty spec fails (upstream) [2] | Default example plus GPU taint toleration | Aligned |
| Driver build | Driver Toolkit DaemonSet `nvidia-driver-daemonset-<RHCOS-version>` (upstream) [2] | `use_ocp_driver_toolkit: true` | Aligned |
| OpenShift AI dashboard refresh | After installing, delete `migration-gpu-status` ConfigMap and restart `rhods-dashboard` [1] | Not done by GitOps; the ConfigMap does not exist on this cluster | Gap (the one-time step is not documented in the stage runbook) |
| GPU verification | Node reports `nvidia.com/gpu` capacity; run a CUDA vectorAdd test [1][2] | `validate.sh` checks allocatable `nvidia.com/gpu=1` and the operator's CUDA validator | Aligned |
| Console dashboard | ConfigMap in `openshift-config-managed` labelled `console.openshift.io/dashboard=true` (upstream) [3] | Same, with pinned local JSON | Aligned |
| GPU console plugin | Install `console-plugin-nvidia-gpu` with Helm, enable it with `oc patch`, point `dcgmExporter.config` at the chart's metric ConfigMap [5] (upstream) | Rendered manifests from chart 0.3.0, enabled in the Git console plugin list, metric list is the 4.9 defaults plus the chart's names | Deviation (justified: GitOps ownership of the plugin list; the chart's list alone would drop the dcgm-exporter 4.9 defaults) |
| Metrics API access | Bind `cluster-monitoring-metrics-api` in `openshift-monitoring` for Prometheus/Thanos API access [4] | RoleBinding for `rhods-admins` | Aligned |

## References

1. Enable NVIDIA GPUs, Working with accelerators, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_accelerators/enabling-nvidia-gpus_accelerators
2. Installing the NVIDIA GPU Operator on OpenShift, NVIDIA GPU Operator on Red Hat OpenShift (latest) (upstream). https://docs.nvidia.com/datacenter/cloud-native/openshift/latest/install-gpu-ocp.html
3. Enabling the GPU Monitoring Dashboard, NVIDIA GPU Operator on Red Hat OpenShift (latest) (upstream). https://docs.nvidia.com/datacenter/cloud-native/openshift/latest/enable-gpu-monitoring-dashboard.html
4. Accessing monitoring APIs by using the CLI, Accessing metrics, Monitoring stack for Red Hat OpenShift 4.22. https://docs.redhat.com/en/documentation/monitoring_stack_for_red_hat_openshift/4.22/html/accessing_metrics/accessing-monitoring-apis-by-using-the-cli
5. OpenShift Console NVIDIA GPU plugin, release-0.3.0 (upstream; the OpenShift Monitoring book documented its install as "The NVIDIA GPU administration dashboard" up to 4.12 and has no later edition). https://github.com/rh-ecosystem-edge/console-plugin-nvidia-gpu/tree/release-0.3.0
6. Dynamic plugins, Web console, OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/web_console/dynamic-plugins
7. DCGM Exporter 4.9.0 release notes (upstream). https://github.com/NVIDIA/dcgm-exporter/releases/tag/4.9.0
