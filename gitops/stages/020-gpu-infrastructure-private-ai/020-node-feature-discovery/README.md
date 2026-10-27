# Node Feature Discovery (`020-node-feature-discovery`)

This Application installs the Node Feature Discovery (NFD) Operator and one `NodeFeatureDiscovery` instance.
NFD labels every node with its hardware facts, including the PCI vendor of attached devices. The NVIDIA GPU
Operator (`020-nvidia-gpu-operator`) uses these labels to find GPU nodes, and the Stage 020 validator reads the
RHCOS version label to match each GPU node to its driver DaemonSet.

| | |
|---|---|
| Argo CD Application | `020-node-feature-discovery` ([manifest](../../../applications/020-node-feature-discovery.yaml)) |
| Deployed by | [`stages/020-gpu-infrastructure-private-ai/deploy.sh`](../../../../stages/020-gpu-infrastructure-private-ai/deploy.sh) (deploy-order 1) |
| Validated by | [`stages/020-gpu-infrastructure-private-ai/validate.sh`](../../../../stages/020-gpu-infrastructure-private-ai/validate.sh) (operator policy, `nfd current CSV Succeeded`, `NFD Available with fresh native worker/master`) |
| Sync | Automated, prune and self-heal; `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences`; Server-Side Diff by compare-options annotation; retry 10, 5s to 3m |
| Depends on | `redhat-operators` catalog; Stage 010 reconciled (checked by `deploy.sh`) |
| Used by | `020-nvidia-gpu-operator` (GPU node detection); `validate.sh` (`feature.node.kubernetes.io/system-os_release.OSTREE_VERSION` label) |

## Why

The NVIDIA GPU enablement procedure for OpenShift AI starts by installing the NFD Operator and creating a
`NodeFeatureDiscovery` instance, then installing the NVIDIA GPU Operator [1]. NFD is a Red Hat operator that
detects hardware features and publishes them as node labels [2]. It is installed by OLM so that Red Hat ships
the operand and its updates; this repository only declares the subscription and the instance.

The component is its own Application because it has its own operator lifecycle and no other component writes
to its namespace.

## What

Operator installation:

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `openshift-nfd` | cluster-scoped | Operator and operand namespace |
| OperatorGroup | `openshift-nfd` | `openshift-nfd` | Targets only `openshift-nfd` |
| Subscription | `nfd` | `openshift-nfd` | `stable` channel, `redhat-operators`, Automatic approval (sync-wave 1) |

Instance:

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| NodeFeatureDiscovery | `nfd-instance` | `openshift-nfd` | NFD master, worker and garbage collector, with a PCI worker configuration (sync-wave 1) |

Objects not in Git (operator-owned): the CSV, the `nfd-controller-manager`, `nfd-master` and `nfd-gc`
Deployments, the `nfd-worker` DaemonSet (one pod per node, including control-plane nodes), and the node labels
they write.

## How

- **Installation.** `stable` channel with Automatic approval, no `startingCSV`. The repository policy is to follow
  the channel and check the release family at deploy time: `check_operator_policy` in `scripts/lib.sh` requires
  the offered version to stay on 4.22 and at least `4.22.0`. Installed on this cluster:
  `nfd.4.22.0-202610231407` (updated by the channel on 2026-10-27; first install `nfd.4.22.0-202610140833`).
- **Ordering.** The Subscription and the instance are both sync-wave 1. The instance CRD does not exist on the
  first sync, so `SkipDryRunOnMissingResource` and the Application retry/backoff carry the sync until OLM
  installs the CRD.
- **Operand image.** `spec.operand.image` is pinned by digest to `ose-node-feature-discovery-rhel9`. OpenShift
  documents this field as mandatory and notes that OLM sets it automatically when it deploys the operator [2].
  Because Git now writes it, Automatic operator updates do not move the operand image.
- **Worker configuration.** `sleepInterval: 60s` is the documented default re-labeling interval [2].
  `deviceClassWhitelist: ["0200", "03", "12"]` publishes network controllers, display controllers (GPUs) and
  processing accelerators; the documented default is `["03", "0b40", "12"]` [2]. `deviceLabelFields: [vendor]`
  produces vendor-only labels such as `feature.node.kubernetes.io/pci-10de.present` for NVIDIA.
- **ignoreDifferences / delegated fields.** None.
- **Secrets.** None.
- **Cluster-specific values.** None.

## Validation

`validate.sh` checks that the Subscription is Automatic, its installed CSV equals the current CSV and is
`Succeeded`, and that `nfd-instance` is `Available` with a current, fully ready `nfd-worker` DaemonSet and
`nfd-master` Deployment owned by the instance.

```bash
oc get nodefeaturediscovery nfd-instance -n openshift-nfd -o jsonpath='{.status.conditions[?(@.type=="Available")].status}{"\n"}'
oc get nodes -L feature.node.kubernetes.io/pci-10de.present
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| NFD before the GPU Operator | Install NFD and create an instance before the NVIDIA GPU Operator [1] | Separate Application, deploy-order 1 | Aligned |
| Namespace and OperatorGroup | `openshift-nfd`, OperatorGroup targeting `openshift-nfd` [2] | Same | Aligned |
| Subscription | `nfd`, channel `stable`, `redhat-operators` [2] | Same, Automatic approval | Aligned |
| Namespace monitoring label | Example Namespace sets `openshift.io/cluster-monitoring: "true"` [2] | Set | Aligned |
| Operand image | The CLI install example sets `operand.image` [2] | Pinned digest in Git, equal to the installed CSV's operand image; Stage 020 validate fails when they differ, so an Automatic operator update means updating the pin | Aligned |
| PCI whitelist | The CLI install example uses `["0200", "03", "12"]` [2] | Same | Aligned |
| Re-detection interval | Default `60s` [2] | `60s` | Aligned |

## References

1. Enable NVIDIA GPUs, Working with accelerators, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_accelerators/enabling-nvidia-gpus_accelerators
2. Node Feature Discovery Operator, Specialized hardware and driver enablement, OpenShift Container Platform 4.22. https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/specialized_hardware_and_driver_enablement/psap-node-feature-discovery-operator
