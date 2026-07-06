---
name: rhoai-hardware-profiles
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift AI hardware
  profiles from the official Working with accelerators guide: creating,
  updating, deleting, enabling, disabling, or GitOps-promoting
  HardwareProfile resources; setting accelerator identifiers, resource
  requests and limits, node selectors, tolerations, and Kueue local queues;
  reviewing recommended accelerator tags for workbench images and serving
  runtimes; validating dashboard visibility for workbenches and model serving;
  and aligning NVIDIA L40S demo profiles with active node capacity. Do NOT use
  for GPU node provisioning, NFD, NVIDIA GPU Operator, ClusterPolicy, or GPU
  time slicing setup; use rhoai-nvidia-gpu-accelerators and related ocp-*
  skills. Do NOT invent HardwareProfile spec fields; verify active schema or
  export a dashboard-created profile before authoring GitOps manifests.
---

# RHOAI Hardware Profiles

Use this skill to create, review, and promote OpenShift AI hardware profiles on
the active product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. The RHOAI 3.4 accelerator
guide defines the dashboard workflows and validation signals for hardware
profiles. Use `rhoai-api-tiers` for API support posture before treating
`hardwareprofiles.infrastructure.opendatahub.io/v1` as a durable contract.

## Scope

This skill covers:

- hardware profile creation, update, deletion, enablement, and disablement
- accelerator identifiers such as `nvidia.com/gpu`
- CPU, memory, and accelerator resource request and limit intent
- Kueue local queue association when distributed workload scheduling is used
- workload priority selection
- node selector and toleration intent
- recommended accelerator tags for workbench images
- recommended accelerator annotations on serving runtimes
- GitOps promotion of verified `HardwareProfile` resources

This skill does not cover:

- installing NFD, KMM, NVIDIA GPU Operator, or accelerator Operators
- AWS GPU MachineSets or GPU node lifecycle
- NVIDIA `ClusterPolicy`, GPU time slicing, or RDMA configuration
- full workbench image or serving runtime authoring
- queue design beyond the hardware profile handoff

## Demo Policy

For this repo:

- Default accelerator identifier: `nvidia.com/gpu`.
- Default demo hardware shape: one NVIDIA L40S GPU per `g6e.2xlarge` GPU worker,
  time-sliced to four schedulable `nvidia.com/gpu` units in Stage 120.
- Default profile intent: queue-backed GPU profiles for workbenches and later
  Nemotron model-serving workloads unless a stage `PLAN.md` documents a
  different resource class.
- Create hardware profiles only after GPU support is installed and nodes report
  accelerator capacity and allocatable resources.
- Use active node labels and taints as scheduling authority. Do not infer
  selectors or tolerations from AWS instance type alone.
- If Kueue is used, coordinate with `rhoai-kueue-workload-management`; do not
  combine Kueue local queue scheduling with conflicting node selectors or
  tolerations unless verified against the active docs and CRD schema.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Confirm accelerator prerequisites are complete with
   `rhoai-nvidia-gpu-accelerators`, `ocp-node-feature-discovery`,
   `ocp-machine-management`, and `ocp-nodes` as needed.
3. Read `references/official-doc-extraction.md`.
4. Decide whether the profile is global or project-scoped:
   - global profiles belong with the shared RHOAI platform owner
   - project-scoped profiles belong with the consuming project stage and must
     be coordinated with `rhoai-project-scoped-resources`
5. For dashboard-first creation, create the profile from
   Settings -> Hardware profiles, then export the resulting
   `HardwareProfile` before promoting to GitOps.
6. For GitOps-first authoring, verify schema first:

   ```bash
   oc explain hardwareprofile --api-version=infrastructure.opendatahub.io/v1
   oc explain hardwareprofile.spec --api-version=infrastructure.opendatahub.io/v1
   oc get crd hardwareprofiles.infrastructure.opendatahub.io -o yaml
   ```

7. Capture resource intent:
   accelerator identifier, CPU/memory defaults, accelerator defaults, limits,
   local queue, workload priority, node selectors, and tolerations.
8. Add recommended accelerator metadata to workbench images or serving runtimes
   only when it matches the active profile and runtime/image compatibility.
9. Validate with `references/validation-checklist.md`.

## Validation

- The hardware profile appears on the dashboard Hardware profiles page.
- The profile appears in the Create workbench hardware profile list when it is
  intended for workbenches.
- The profile appears on the `HardwareProfile` CRD instances page.
- GPU-backed profiles match observed node capacity and allocatable resources.
- Recommended accelerator tags appear only where the accelerator is actually
  compatible with the workbench image or serving runtime.
- GitOps manifests render and match the active CRD schema.

## Related Skills

- `rhoai-nvidia-gpu-accelerators`: accelerator installation, NVIDIA-only demo
  policy, GPU MachineSet handoff, and GPU Operator readiness.
- `rhoai-project-scoped-resources`: project-scoped hardware profile copies and
  dashboard `disableProjectScoped` behavior.
- `rhoai-kueue-workload-management`: local queue scheduling and Kueue-enabled
  hardware profile restrictions.
- `rhoai-model-deployment`: hardware profile selection during model deployment.
- `rhoai-workbench-image-import`: workbench image compatibility and accelerator
  metadata.
- `rhoai-model-serving-platform`: serving runtime compatibility and Dashboard
  behavior.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/nvidia-l40s-hardware-profile-pattern.md`
