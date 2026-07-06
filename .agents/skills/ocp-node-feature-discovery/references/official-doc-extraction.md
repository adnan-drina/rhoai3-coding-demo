# Official Doc Extraction

Use this extraction to keep NFD content grounded in the official OCP source.
When implementation needs exact CR fields, verify the active cluster schema
with `oc explain` or `oc get crd` before authoring GitOps manifests.

## NFD Operator And Instance

- The official chapter covers installing the Node Feature Discovery Operator
  and creating a `NodeFeatureDiscovery` custom resource.
- The `NodeFeatureDiscovery` resource configures the NFD operands and worker
  behavior for feature detection and node labeling.
- The official CLI flow applies a `NodeFeatureDiscovery` resource with
  `oc apply -f <filename>`.
- Verification includes inspecting the `NodeFeatureDiscovery` resource and
  checking NFD pods in the chosen NFD namespace.
- Starting with OCP 4.12, the `operand.image` field in the
  `NodeFeatureDiscovery` custom resource is mandatory. When the Operator is
  deployed by OLM, OLM sets the operand image automatically. When creating the
  custom resource manually by CLI or web console, set `operand.image`
  explicitly from the official source or verified cluster metadata.

## Worker Configuration

The official configuration model includes NFD worker options such as:

- `core.sleepInterval`: interval between feature detection, re-detection, and
  node relabeling. The documented default is 60 seconds.
- `core.sources`: list of enabled feature sources. The documented special
  value `all` enables all sources, and the documented default is `all`.
- `core.labelWhiteList`: regular-expression filter for feature labels based on
  the label basename, excluding prefix or namespace.
- `core.noPublish`: dry-run mode that prevents communication with
  `nfd-master`; the worker detects features but does not request node labels.
  Do not leave this enabled for a real deployment unless the dry-run behavior is
  intentional.

Feature-source configuration includes PCI, USB, kernel, CPU, and custom
discovery sources. For PCI, the official docs describe class whitelists and
label fields such as class, vendor, device, subsystem vendor, and subsystem
device. Do not invent PCI label names; inspect generated node labels before
using them for scheduling.

## Feature Labels

NFD publishes feature labels on nodes after discovery. Treat these labels as
observed cluster state:

- Read generated labels from nodes before writing selectors or affinity.
- Avoid assuming that a cloud instance type implies a specific NFD label.
- Do not confuse NFD feature labels with device-plugin resource capacity such
  as `nvidia.com/gpu`.
- Use `ocp-nodes` to reason about scheduling mechanics once labels exist.

## NodeFeatureRule

`NodeFeatureRule` objects support rule-based custom node labeling and optional
tainting based on discovered node features.

Officially documented use cases include:

- application-specific labels
- hardware-vendor-distributed labels
- custom labels or taints based on kernel modules, PCI devices, or other NFD
  feature sources

Rules create labels when all configured feature matches are satisfied. The
official example matches a loaded `veth` kernel module and a PCI device with
vendor ID `8086`. The official docs note that relabeling can be delayed by up
to one minute.

Use project-owned label names for demo-specific labels. Do not create
scheduling taints from a `NodeFeatureRule` unless the workload placement impact
is documented and validated.

## NFD Topology Updater

The NFD Topology Updater is a daemon that examines allocated resources on each
worker node and reports resource availability per zone, where a zone can be a
NUMA node.

Official behavior to preserve:

- One NFD Topology Updater instance runs on each cluster node when enabled.
- Enable topology updater workers by setting the documented
  `topologyupdater` variable to `true` in the `NodeFeatureDiscovery` custom
  resource.
- NFD creates `NodeResourceTopology` custom resources with API group
  `topology.node.k8s.io/v1alpha1` when the topology updater runs.
- Mutual TLS flags for the topology updater, such as `-ca-file`,
  `-cert-file`, and `-key-file`, must be specified together if used.

Enable Topology Updater only when topology-aware scheduling, NUMA-sensitive
workloads, or per-zone resource reporting is required by the implementation.

## Demo GPU Handoff

For the RHOAI demo, NFD is part of the GPU-readiness path but not the complete
GPU stack:

1. `ocp-machine-management` provisions or scales the GPU worker nodes.
2. `ocp-node-feature-discovery` detects hardware features and publishes labels.
3. `rhoai-nvidia-gpu-accelerators` handles NVIDIA GPU Operator, ClusterPolicy,
   device plugin, accelerator profiles, and RHOAI hardware-profile intent.
4. `ocp-nodes` and RHOAI serving skills handle scheduling and workload
   placement.
