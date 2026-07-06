# Official Doc Extraction

This extraction is derived from the official RHOAI documentation chapters
captured in `source-capture.md`.

## Accelerator Enablement

Before using an accelerator in OpenShift AI:

- User is logged in to OpenShift.
- User has the `cluster-admin` role.
- The accelerator is installed and detected in the environment.
- The accelerator-specific documentation is followed.
- After accelerator installation, a hardware profile is created.

For this demo, the accelerator-specific path is NVIDIA GPUs only.

Verification checks include installed Operators for:

- the selected accelerator
- Node Feature Discovery (NFD)
- Kernel Module Management (KMM)

For NVIDIA GPUs, the node should report `nvidia.com/gpu` in both capacity and
allocatable values.

## NVIDIA GPU Enablement

Before using NVIDIA GPUs in OpenShift AI, install the NVIDIA GPU Operator.

NVIDIA prerequisites:

- User is logged in to OpenShift.
- User has `cluster-admin`.
- NVIDIA GPU hardware is installed and detected.

Required behavior:

- After installing NFD Operator, create a `NodeFeatureDiscovery` instance.
- After installing NVIDIA GPU Operator, create an NVIDIA `ClusterPolicy` and
  populate it with default values.
- Delete the `migration-gpu-status` ConfigMap as described by the official
  NVIDIA GPU enablement chapter.
- Restart the `rhods-dashboard` deployment and wait for rollout completion.

NVIDIA verification:

- `migration-gpu-status` is no longer present on the `HardwareProfile` CRD
  instances tab.
- NVIDIA GPU, NFD, and KMM Operators are installed.
- GPU worker nodes report `nvidia.com/gpu` capacity and allocatable values.

Support boundaries:

- Red Hat supports accelerators within the same cluster only.
- Starting with RHOAI 2.19, Red Hat supports RDMA for NVIDIA GPUs only, using
  NVIDIA GPUDirect RDMA over Ethernet or InfiniBand.

## Hardware Profiles

Hardware profiles manage and allocate specific hardware resources for data
science, machine learning, and generative AI workloads.

Hardware profiles are custom resources for targeted scheduling and can include:

- hardware identifiers
- explicit resource limits for CPU, memory, and accelerators
- tolerations
- node selectors

Creation prerequisites:

- User has OpenShift AI administrator privileges.
- Relevant hardware is installed and detected.
- Desired GPU type and vRAM size are verified.

Creation fields and decisions:

- profile name
- optional Kubernetes resource name
- optional description
- visibility: visible everywhere or limited visibility
- optional resource requests and limits with label, identifier, resource type,
  default, minimum, and maximum values
- workload allocation strategy:
  - Local queue, when the cluster is configured for Kueue
  - Node selectors and tolerations for direct node targeting

Creation verification:

- Profile appears on the Hardware profiles page.
- Profile appears in the Create workbench hardware profile list.
- Profile appears on the `HardwareProfile` CRD details page.

## Recommended Accelerator Tags

For workbench images, the dashboard can show a recommended accelerator tag after
an accelerator identifier is associated with a workbench image.

For serving runtimes, the official docs show the annotation:

```yaml
metadata:
  annotations:
    opendatahub.io/recommended-accelerators: '["nvidia.com/gpu"]'
```

Use this only after NVIDIA GPU support is enabled and the serving runtime is a
custom runtime that can be edited or duplicated.

## Unresolved Items

The captured RHOAI chapters do not fully define:

- exact OLM Subscription channels for NFD, KMM, or NVIDIA GPU Operator
- complete `NodeFeatureDiscovery` YAML fields
- complete NVIDIA `ClusterPolicy` YAML fields
- complete `HardwareProfile` YAML schema
- exact AWS MachineSet provider shape for GPU worker nodes

Resolve these with official OpenShift/NVIDIA/Red Hat docs, active Operator CSVs,
active CRDs, and `references/gitops-catalog-gpu-pattern.md` before committing
GitOps manifests.
