---
name: ocp-node-feature-discovery
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing or changing the Stage 020 Node Feature Discovery component
  in gitops/stages/020-gpu-infrastructure-private-ai/node-feature-discovery/
  (nfd Subscription on stable, NodeFeatureDiscovery nfd-instance, PCI worker
  config, pinned operand image), the nfd minimum in
  scripts/platform/check-operator-policy.py, or diagnosing missing
  feature.node.kubernetes.io labels that the NVIDIA GPU Operator and
  validate.sh depend on. Do NOT use for the GPU Operator, ClusterPolicy and
  accelerator profiles (use rhoai-nvidia-gpu-accelerators) or node taints and
  placement (use ocp-nodes).
---

# OCP Node Feature Discovery

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift Container Platform 4.22 sections. Detailed record:
`gitops/stages/020-gpu-infrastructure-private-ai/node-feature-discovery/README.md`.

## When to use

- A change touches `node-feature-discovery/*.yaml` or the `020-node-feature-discovery`
  Application.
- The NFD release family moves (the `nfd` minimum in the operator policy is
  also the doc-map pin for the whole `ocp` product).
- GPU nodes lack `feature.node.kubernetes.io/pci-10de.present` or the RHCOS
  `system-os_release.OSTREE_VERSION` label.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| NFD installed before the NVIDIA GPU Operator, as its own Application (deploy-order 1) | `gitops/argocd/app-of-apps/020-gpu-infrastructure-private-ai/node-feature-discovery.yaml` | [Node Feature Discovery Operator][nfd] |
| Namespace `openshift-nfd`, OperatorGroup targeting it, Subscription `nfd` on `stable` from `redhat-operators`, Automatic approval, no `startingCSV` | `node-feature-discovery/namespace.yaml`, `operatorgroup.yaml`, `subscription.yaml` | [Node Feature Discovery Operator][nfd] |
| Release family bounded by policy: offered version must stay on 4.22 and be at least `4.22.0` | `scripts/platform/check-operator-policy.py` (`minimum['nfd']`) | [About specialized hardware and driver enablement][about] |
| One `NodeFeatureDiscovery` `nfd-instance`; Subscription and instance both sync-wave 1, carried by `SkipDryRunOnMissingResource` and retry until OLM installs the CRD | `node-feature-discovery/nodefeaturediscovery.yaml` | [Node Feature Discovery Operator][nfd] |
| `spec.operand.image` pinned by digest (`ose-node-feature-discovery-rhel9`); recorded deviation: Automatic operator updates no longer move the operand | `node-feature-discovery/nodefeaturediscovery.yaml` | [Node Feature Discovery Operator][nfd] |
| Worker config: `sleepInterval: 60s`, PCI `deviceClassWhitelist: ["0200", "03", "12"]`, `deviceLabelFields: [vendor]` (vendor-only labels such as `pci-10de.present`) | `node-feature-discovery/nodefeaturediscovery.yaml` | [Node Feature Discovery Operator][nfd] |
| Namespace has no `openshift.io/cluster-monitoring` label (recorded gap: NFD metrics not scraped) | `node-feature-discovery/namespace.yaml` | [Node Feature Discovery Operator][nfd] |
| No `NodeFeatureRule`, topology updater, Kernel Module Management or Driver Toolkit use | (none declared) | [Kernel Module Management Operator][kmm], [Driver Toolkit][dtk] |

Paths are relative to `gitops/stages/020-gpu-infrastructure-private-ai/` unless they start with `gitops/` or `scripts/`.

## Procedure

1. Edit the manifests in Git; `stages/020-gpu-infrastructure-private-ai/deploy.sh`
   runs the operator policy check before it applies the Applications.
2. When a new NFD minor ships with a new OpenShift minor, update
   `minimum['nfd']` in `scripts/platform/check-operator-policy.py` together
   with the `ocp` docs_version in `.agents/references/red-hat-doc-map.yaml`
   (the checker reports `PIN-MISMATCH` until both agree), and re-pin the
   operand digest from the installed CSV.
3. Validate: `./stages/020-gpu-infrastructure-private-ai/validate.sh`
   (Subscription Automatic, current CSV `Succeeded`, `nfd-instance`
   `Available` with ready `nfd-worker` and `nfd-master`). By hand, after the
   OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get subscription nfd -n openshift-nfd -o jsonpath='{.status.installedCSV}{"\n"}'
   oc get nodefeaturediscovery nfd-instance -n openshift-nfd -o jsonpath='{.status.conditions[?(@.type=="Available")].status}{"\n"}'
   oc get nodes -L feature.node.kubernetes.io/pci-10de.present
   ```

## Pitfalls

- The pinned operand digest can differ from the image in the installed CSV;
  after an operator update compare them before blaming NFD.
- The default PCI whitelist differs from the repo's; keep class `03`
  (display controllers) or GPU detection breaks.
- The `nfd-worker` DaemonSet runs on every node including control plane; a
  node without the worker has no labels.
- With GPU pools at zero there are no GPU labels to check; resume a pool
  first (`resume-gpu-demo`).

## Official documentation (OpenShift Container Platform 4.22)

| Topic | Section |
|---|---|
| Overview | [About specialized hardware and driver enablement][about] |
| NFD | [Node Feature Discovery Operator][nfd] |
| Not used here | [Driver Toolkit][dtk], [Kernel Module Management Operator][kmm] |
| GPUs on OpenShift | [About hardware accelerators][accel], [NVIDIA GPU architecture][nvidia] |

## Related skills

`rhoai-nvidia-gpu-accelerators`, `ocp-nodes`, `ocp-machine-management`,
`resume-gpu-demo`.

[about]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/specialized_hardware_and_driver_enablement/index#about-hardware-enablement
[nfd]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/specialized_hardware_and_driver_enablement/index#psap-node-feature-discovery-operator
[dtk]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/specialized_hardware_and_driver_enablement/index#driver-toolkit
[kmm]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/specialized_hardware_and_driver_enablement/index#kernel-module-management-operator
[accel]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/hardware_accelerators/index#about-hardware-accelerators
[nvidia]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/hardware_accelerators/index#nvidia-gpu-architecture
