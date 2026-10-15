---
name: rhoai-nvidia-gpu-accelerators
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when reviewing or changing Stage 020 NVIDIA GPU enablement for OpenShift
  AI: the gpu-operator-certified Subscription (channel v26.7) and
  gpu-cluster-policy ClusterPolicy, the NFD prerequisite, the GPU MachineSet
  pools (default g7e.2xlarge with one RTX PRO 6000, parked g6e.2xlarge L40S),
  the nvidia-gpu-only taint, one nvidia.com/gpu per card without time-slicing,
  the migration-gpu-status dashboard step, and GPU metrics for OpenShift AI.
  Do NOT use for HardwareProfile objects (use rhoai-hardware-profiles), Kueue
  queues (use rhoai-kueue-workload-management), MachineSet mechanics (use
  ocp-machine-management), or scaling GPUs for a session (use resume-gpu-demo).
---

# RHOAI NVIDIA GPU Accelerators

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/020-gpu-infrastructure-private-ai/nvidia-gpu-operator/README.md`
(also `.../gpu-machinesets/README.md` and `.../node-feature-discovery/README.md`).

## When to use

- A change touches `gitops/stages/020-gpu-infrastructure-private-ai/nvidia-gpu-operator/`,
  `.../gpu-machinesets/` or `.../node-feature-discovery/`.
- GPU nodes do not advertise `nvidia.com/gpu`, or OpenShift AI does not offer GPUs.
- Planning a new GPU type or pool.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| NVIDIA only; NFD Operator and `NodeFeatureDiscovery` instance first (deploy-order 1), then the GPU Operator (deploy-order 2) | `node-feature-discovery/`, `nvidia-gpu-operator/` | [Enable NVIDIA GPUs][nvidia] |
| `gpu-operator-certified` from `certified-operators`, channel `v26.7`, Automatic, no `startingCSV`; minimum 26.7.1 enforced | `nvidia-gpu-operator/subscription.yaml`, `scripts/platform/check-operator-policy.py` | [Enable NVIDIA GPUs][nvidia] (operator is a prerequisite) |
| `ClusterPolicy` `gpu-cluster-policy` from the operator's default example plus a `nvidia-gpu-only` toleration; Driver Toolkit build; DCGM ServiceMonitor on; sandbox workloads off | `nvidia-gpu-operator/cluster-policy.yaml` | [Enable NVIDIA GPUs][nvidia]; field detail is NVIDIA's (upstream, see component README) |
| No time-slicing or MIG partitioning: `mig.strategy: single`, no device-plugin config, one card = one `nvidia.com/gpu` (one model per card) | `nvidia-gpu-operator/cluster-policy.yaml` | [GPU time slicing][timeslice] (not used) |
| Default pool `g7e.2xlarge` (one RTX PRO 6000 Blackwell, 96 GB), one MachineSet per `us-east-2` zone; L40S pool `g6e.2xlarge` kept at zero; all 0 replicas in Git, 200 GB gp3 root disk | `gpu-machinesets/machineset-rtxpro6000.yaml`, `gpu-machinesets/machineset-gpu.yaml` | OCP: see `ocp-machine-management` |
| Pool shape: label `cluster-api/accelerator` (`nvidia-rtxpro6000` / `nvidia-gpu`), `node-role.kubernetes.io/gpu`, taint `nvidia-gpu-only:NoSchedule`; generated from the active CPU worker pool | `stages/020-gpu-infrastructure-private-ai/generate-gpu-machineset.sh` | OCP: see `ocp-machine-management` |
| `migration-gpu-status` delete + dashboard restart is not automated (ConfigMap absent on this cluster, checked 2026-10-14) | `docs/OPERATIONS.md#stage-020` | [Enable NVIDIA GPUs][nvidia] |
| GPU utilization for the OpenShift AI dashboards via ServiceMonitor `accelerator-gpu-utilization` (workaround for a 3.5.1 gap); `rhods-admins` bound to `cluster-monitoring-metrics-api` | `nvidia-gpu-operator/rhoai-monitoring/`, `nvidia-gpu-operator/rolebinding-gpu-metrics-admins.yaml` | see `rhoai-observability` |

## Procedure

1. On a new cluster regenerate the pools, review, publish:
   `./stages/020-gpu-infrastructure-private-ai/generate-gpu-machineset.sh --source <cpu-machineset> --write`.
2. Deploy: `./stages/020-gpu-infrastructure-private-ai/deploy.sh`.
3. Scale a pool for a session with `scripts/platform/resume-gpu-demo.sh up`
   (`GPU_POOL=l40s` for the L40S pool, `down` parks all pools); `scripts/platform/gpu-capacity-probe.sh`
   tries one zone at a time.
4. Validate: `./stages/020-gpu-infrastructure-private-ai/validate.sh --readiness`
   (operator CSV, `ClusterPolicy` ready, per-node driver DaemonSet, one GPU and
   the taint per Ready GPU node; node checks fail by design at zero replicas),
   then `--functional` (CUDA vectorAdd validator, DCGM scrape).
5. By hand, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get clusterpolicy gpu-cluster-policy -o jsonpath='{.status.state}{"\n"}'
   oc get machinesets -n openshift-machine-api -L cluster-api/accelerator
   oc get nodes -l node-role.kubernetes.io/gpu -o custom-columns=NAME:.metadata.name,GPU:.status.allocatable.nvidia\.com/gpu
   oc get configmap -A --field-selector metadata.name=migration-gpu-status   # after an upgrade from an older release
   ```

## Pitfalls

- Changing the taint key means changing the `ClusterPolicy` tolerations, both
  GPU ResourceFlavors and the generator together.
- KMM is not a prerequisite; it only appears in the verification list of
  [Enable accelerators][accel-install].
- A 100 GB root disk hit `DiskPressure` pulling a ~36 GB model image; keep 200 GB.
- AWS capacity: `docs/TROUBLESHOOTING.md#gpu-machine-stays-provisioning-or-fails-capacity-or-spot-policy`;
  no nodes: `docs/TROUBLESHOOTING.md#gpu-nodes-do-not-appear`.
- With pools at zero the `ClusterPolicy` still reports `ready`; check nodes.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Accelerator overview | [Enable accelerator devices][overview], [Enable accelerators][accel] |
| NVIDIA enablement | [Enable NVIDIA GPUs][nvidia] |
| Install-guide view | [Enable accelerators (install guide)][accel-install] |
| Time slicing (not used) | [Enable GPU time slicing][timeslice] |

Validated-models routing: the map's `red_hat_ai_validated_models` book returned
404 at 3.5 (2026-10-15), so model/hardware validation claims are not made here.

## Related skills

`rhoai-hardware-profiles`, `rhoai-kueue-workload-management`,
`ocp-node-feature-discovery`, `ocp-machine-management`, `ocp-nodes`,
`resume-gpu-demo`, `rhoai-observability`, `rhoai-platform-planning`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_accelerators/index#overview-of-accelerators_accelerators
[accel]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_accelerators/index#enabling-accelerators_accelerators
[nvidia]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_accelerators/index#enabling-nvidia-gpus_accelerators
[timeslice]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_accelerators/index#about-gpu-time-slicing_accelerators
[accel-install]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#enabling-accelerators_install
