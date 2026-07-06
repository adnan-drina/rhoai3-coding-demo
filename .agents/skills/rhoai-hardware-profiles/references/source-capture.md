# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift AI Self-Managed |
| Product version | 3.4 |
| Documentation category | Administer |
| Documentation book | Working with accelerators |
| Official URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_accelerators/index |
| Source type | Versioned docs.redhat.com documentation |
| Retrieved | 2026-06-12 |
| Skill route | `rhoai-hardware-profiles` |

## Sections Used

- Overview of accelerators
- Enabling accelerators
- Enabling NVIDIA GPUs
- Working with hardware profiles
- Creating a hardware profile
- Updating a hardware profile
- Deleting a hardware profile
- Configuring a recommended accelerator for workbench images
- Configuring a recommended accelerator for serving runtimes

## Related Official Sources

- Active RHOAI baseline:
  https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/
- OCP NFD and GPU node prerequisites are routed through `ocp-*` skills.
- HardwareProfile API tier posture is routed through `rhoai-api-tiers`.
- Kueue-enabled hardware profile behavior is routed through
  `rhoai-kueue-workload-management`.

## Extraction Boundary

This skill extracts hardware profile lifecycle and compatibility behavior from
the official accelerator guide. It does not make this skill the owner of GPU
node provisioning, NFD, KMM, NVIDIA GPU Operator, ClusterPolicy, GPU time
slicing, or RDMA configuration.

The official guide describes dashboard workflows. It identifies
`HardwareProfile` as a CRD but does not provide a complete GitOps manifest
schema for every field. Before authoring a GitOps `HardwareProfile`, verify the
active CRD schema or export a dashboard-created profile.

## Demo-Specific Context

The rhoai3-demo default accelerator posture is NVIDIA-only:

- accelerator identifier: `nvidia.com/gpu`
- default GPU instance type: `g6e.2xlarge`
- GPU profile: NVIDIA L40S, one physical GPU per node, time-sliced to four
  schedulable `nvidia.com/gpu` units in Stage 120
- default node count: one GPU worker
- main private GenAI model: `nemotron-3-nano-30b-a3b`

These demo choices do not replace official product documentation and must be
validated against the active cluster before GitOps promotion.
