---
name: ocp-machine-configuration
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when someone proposes a MachineConfig, KubeletConfig,
  ContainerRuntimeConfig, PinnedImageSet, custom MachineConfigPool or image
  mode change for this demo, when MachineConfigPools are Degraded or not
  Updated in the baseline health check, or when a node disk or image-GC
  problem tempts a host-level fix. The repo declares no Machine Config
  Operator resources. Do NOT use for MachineSet shape, disk size and scaling
  (use ocp-machine-management) or labels, taints and evictions (use
  ocp-nodes).
---

# OCP machine configuration

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift Container Platform 4.22 sections. The repo keeps the default host
configuration; the Machine Config Operator (MCO) and its pools are owned by
the cluster provisioner (`docs/OPERATIONS.md`, ownership table).

## When to use

- A change would add a `MachineConfig`, `KubeletConfig`,
  `ContainerRuntimeConfig`, `PinnedImageSet`, `MachineConfiguration` or a
  custom `MachineConfigPool` under `gitops/`.
- The baseline core-health check finds master or worker MachineConfigPools
  not `Updated` or `Degraded`.
- Node disk pressure or GPU driver issues invite a host OS change.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| No MCO resources in Git: no `MachineConfig`, `KubeletConfig`, `ContainerRuntimeConfig`, `PinnedImageSet`, custom pool or image mode | (none declared; checked by search on 2026-10-15) | [Machine configuration overview][overview] |
| Control plane, workers and machine lifecycle are provisioner-owned; stages must not adopt or remove them without evidence | `docs/OPERATIONS.md` (ownership and stage boundaries) | [Machine configuration overview][overview] |
| Baseline core health requires master and worker MachineConfigPools `Updated` and not `Degraded` | `docs/OPERATIONS.md` (core health) | [Machine configuration overview][overview] |
| Node disk sizing is solved in the MachineSet (200 GB `gp3` GPU root volume), not by kubelet image-GC tuning | `gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-machinesets/`, `stages/020-gpu-infrastructure-private-ai/deploy.sh --generate-machinesets` | [Pinning images to nodes][pin] |
| GPU drivers come from the NVIDIA GPU Operator `ClusterPolicy`, not from host extensions or layered images | `gitops/stages/020-gpu-infrastructure-private-ai/020-nvidia-gpu-operator/cluster-policy.yaml` | [Image mode for OpenShift][layering] |

## Procedure

1. Before adding any MCO resource, read the linked sections for the
   disruption it causes (drain, reboot or CRI-O reload) and record why the
   default does not work in the component README. Treat it as a high-risk,
   live-environment change (`.agents/rules/ocp.md`); pair control-plane pool
   changes with `ocp-etcd`.
2. Prefer a node disruption policy over a reboot when the change type allows
   it; target a dedicated pool rather than `worker` when only GPU nodes need it.
3. Read-only checks after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get machineconfigpool
   oc get machineconfig --sort-by=.metadata.creationTimestamp | tail -5
   oc get kubeletconfig,containerruntimeconfig
   oc describe machineconfigpool worker | grep -A8 Conditions:
   ```

## Pitfalls

- Any `worker` pool change rolls through every worker, GPU nodes included,
  and can drain model servers holding the whole GPU quota.
- GPU nodes are in the `worker` pool; a `MachineConfig` for them alone needs
  a custom pool, which also changes how upgrades roll.
- Kubelet image GC cannot reclaim an in-use modelcar; tuning thresholds does
  not fix the router-scheduler disk cost
  (`docs/TROUBLESHOOTING.md#worker-nodes-evict-pods-after-a-cluster-resume-kubenodeeviction`).
- A Degraded pool blocks cluster upgrades; read the Machine Config Daemon
  logs and metrics before deleting rendered configs.

## Official documentation (OpenShift Container Platform 4.22)

| Topic | Section |
|---|---|
| Overview | [Machine configuration overview][overview] |
| Configure | [Configuring MCO-related custom resources][configure], [Using node disruption policies][disruption], [Creating custom machine config pools][custom-mcp] |
| Images | [Pinning images to nodes][pin], [Image mode for OpenShift][layering] |
| Operate | [Using machine config objects to configure nodes][custom], [Machine Config Daemon metrics overview][metrics] |

## Related skills

`ocp-machine-management`, `ocp-nodes`, `ocp-etcd`,
`rhoai-nvidia-gpu-accelerators`.

[overview]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/machine_configuration/index#machine-config-index
[configure]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/machine_configuration/index#machine-configs-custom
[disruption]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/machine_configuration/index#machine-config-node-disruption_machine-configs-configure
[custom]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/machine_configuration/index#machine-configs-configure
[pin]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/machine_configuration/index#machine-config-pin-preload-images-about
[custom-mcp]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/machine_configuration/index#machine-config-creating-custom-mcp
[layering]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/machine_configuration/index#mco-coreos-layering
[metrics]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/machine_configuration/index#machine-config-daemon-metrics
