---
name: rhoai-nvidia-gpu-accelerators
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when installing, documenting, reviewing, or rebuilding NVIDIA GPU
  accelerator support for the rhoai3-demo OpenShift AI environment: accelerator
  prerequisites, Node Feature Discovery, Kernel Module Management, NVIDIA GPU
  Operator, NVIDIA ClusterPolicy, GPU detection through nvidia.com/gpu, NVIDIA
  RDMA support boundaries, AWS demo.redhat.com GPU MachineSet curation, and
  OpenShift AI dashboard restart requirements. Pair with
  rhoai-hardware-profiles for HardwareProfile lifecycle, profile schema,
  recommended accelerator tags, Kueue local queue handoff, and GitOps
  promotion. Do NOT use for AMD, Intel Gaudi, IBM Spyre, generic RHOAI
  installation, queue design, or live troubleshooting; use the relevant
  rhoai-* or env-* skill instead.
---

# RHOAI NVIDIA GPU Accelerators

Use this skill to enable and review NVIDIA GPU accelerator support for the
active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official accelerator and hardware profile guidance to this repo's GitOps
operating model and NVIDIA-only demo policy.

## Demo Policy

The rhoai3-demo environment uses NVIDIA GPUs only. Do not add AMD, Intel Gaudi,
or IBM Spyre accelerator paths unless the project baseline changes.

The demo hardware intent is:

- AWS GPU instance type: `g6e.2xlarge`.
- GPU capacity pattern: one NVIDIA L40S GPU per node, exposed to Kubernetes as
  `nvidia.com/gpu`; Stage 120 time-slices one physical GPU into four
  schedulable `nvidia.com/gpu` units for demo density.
- Default node count: one GPU worker node unless an environment-specific
  resource plan says otherwise.
- Default AWS environment source: demo.redhat.com OpenShift on AWS.
- Default GPU worker scheduling handoff:
  - MachineSet template label `node-role.kubernetes.io/gpu`
  - MachineSet and template label `cluster-api/accelerator=nvidia-gpu`
  - taint `nvidia-gpu-only:NoSchedule`
  - matching NVIDIA `ClusterPolicy` daemonset toleration
- Primary private GenAI model:
  `nemotron-3-nano-30b-a3b`.
- Primary model source:
  `oci://registry.redhat.io/rhai/modelcar-nvidia-nemotron-3-nano-30b-a3b-fp8:3.0`.
- Serving path: Stage 210 validates RHOAI model serving with vLLM; Stage 220
  publishes governed model access through the Model-as-a-Service layer.
- Use `rhoai-distributed-inference-llmd` when reviewing
  `LLMInferenceService`, Gateway, scheduler, autoscaling, auth, or
  flow-control details for the private model serving path.
- Use `rhoai-model-serving-platform` when reviewing KServe
  `ServingRuntime`, `InferenceService`, vLLM runtime parameters, or model
  serving platform dashboard behavior.
- Approved external model path: OpenAI `gpt-5.4-mini` registered in MaaS
  through the DNS-safe `gpt-5-4-mini` resource alias for governed external use
  cases where provider-side processing is allowed. External OpenAI models do
  not consume cluster GPU capacity.

Use active node labels and observed GPU resources as the scheduling authority.
Do not rely on AWS instance-family assumptions alone when naming hardware
profiles or ResourceFlavors.

## Installation Model

NVIDIA GPU enablement has four gates:

1. GPU-capable worker nodes exist and the accelerator is detected by the
   OpenShift environment.
2. Node Feature Discovery (NFD) Operator is installed and a
   `NodeFeatureDiscovery` instance exists.
3. NVIDIA GPU Operator is installed and an NVIDIA `ClusterPolicy` exists with
   defaults appropriate for the active cluster.
4. OpenShift AI hardware profiles expose the GPU resource to users and serving
   workflows.

The RHOAI docs also list Kernel Module Management (KMM) as part of accelerator
verification. Validate it with the installed Operators before declaring GPU
support complete.

## GitOps Policy

For this repo:

- Install prerequisite Operators and runtime instances through ArgoCD/GitOps.
- Keep GPU node provisioning and scale management in GitOps-aware environment
  workflows.
- Use the Red Hat CoP GPU Operator catalog as a local curation pattern only.
  Reuse its operator/channel layout, instance component composition, and AWS
  MachineSet transformation logic; do not commit remote Kustomize references.
- Prefer a reviewed, Git-tracked AWS GPU MachineSet and MachineAutoscaler in
  the environment overlay. Use an Argo CD hook generator only as a deliberate
  demo.redhat.com bootstrap exception, because generated MachineSets are not
  normal declarative GitOps state unless captured back into Git.
- Derive AWS GPU MachineSet provider details from an existing worker MachineSet
  in the target cluster, then change only reviewed fields such as instance
  type, replicas, labels, taints, and autoscaler bounds.
- Hand hardware profile design, schema verification, and GitOps promotion to
  `rhoai-hardware-profiles` after the GPU Operator and NFD have reconciled and
  nodes report `nvidia.com/gpu` capacity and allocatable values.
- Do not handwrite unverified `NodeFeatureDiscovery`, NVIDIA `ClusterPolicy`,
  or `HardwareProfile` fields from memory.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Confirm the active OpenShift cluster has the expected AWS GPU worker shape.
3. Read `references/official-doc-extraction.md`.
4. Read `references/gitops-catalog-gpu-pattern.md` when rebuilding the GPU
   Operator, AWS GPU MachineSet, or GPU instance overlay.
5. Install or review NFD, KMM, and NVIDIA GPU Operator prerequisites.
6. Confirm `NodeFeatureDiscovery` and NVIDIA `ClusterPolicy` exist.
7. Delete the OpenShift AI `migration-gpu-status` ConfigMap when required by
   the NVIDIA GPU enablement procedure.
8. Restart the OpenShift AI dashboard deployment after NVIDIA GPU enablement.
9. Validate GPU capacity and allocatable values on GPU worker nodes.
10. Create or review NVIDIA hardware profiles with
   `rhoai-hardware-profiles`.
11. Validate with `references/validation-checklist.md`.

## Related Skills

- Use `ocp-node-feature-discovery` for NFD Operator installation,
  `NodeFeatureDiscovery`, `NodeFeatureRule`, NFD feature labels, and topology
  updater behavior.
- Use `ocp-machine-management` for AWS GPU worker MachineSets and node count.
- Use `ocp-nodes` for scheduling mechanics after GPU and NFD labels exist.
- Use `rhoai-hardware-profiles` for RHOAI `HardwareProfile` lifecycle,
  profile schema verification, recommended accelerator tags, and GitOps
  promotion.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/gitops-catalog-gpu-pattern.md`
- `references/validation-checklist.md`
- `examples/demo-nvidia-l40s-hardware-profile-contract.md`
- `examples/aws-gpu-machineset-gitops-pattern.md`
