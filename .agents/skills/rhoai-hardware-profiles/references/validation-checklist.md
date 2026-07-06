# Validation Checklist

Use this checklist before accepting hardware profile documentation, GitOps, or
stage implementation work.

## Source And API Posture

- Active product version is checked in `docs/PLATFORM_BASELINE.md`.
- Official RHOAI 3.4 Working with accelerators documentation is cited.
- `rhoai-api-tiers` is consulted for `hardwareprofiles.infrastructure.opendatahub.io/v1`.
- No `HardwareProfile` fields are invented from memory.
- GitOps manifests are based on the active CRD schema or an exported,
  dashboard-created profile.

## Accelerator Readiness

- NFD, KMM, and the accelerator Operator are installed where relevant.
- GPU nodes report expected accelerator capacity and allocatable values:

  ```bash
  oc describe node <gpu-node-name> | rg -n "Capacity:|Allocatable:|nvidia.com/gpu"
  ```

- For the NVIDIA demo path, `nvidia.com/gpu` is present before profiles are
  shown as usable.
- The profile name and display name do not imply a physical GPU model unless
  that model is verified from node labels, node description, or provider data.

## Hardware Profile Resource Checks

Before authoring or reviewing a GitOps `HardwareProfile`:

```bash
oc explain hardwareprofile --api-version=infrastructure.opendatahub.io/v1
oc explain hardwareprofile.spec --api-version=infrastructure.opendatahub.io/v1
oc get crd hardwareprofiles.infrastructure.opendatahub.io -o yaml
```

For existing profiles:

```bash
oc get hardwareprofiles.infrastructure.opendatahub.io -A
oc get hardwareprofiles.infrastructure.opendatahub.io <name> -n <namespace> -o yaml
```

Check that:

- accelerator identifier matches the active accelerator resource
- CPU, memory, and accelerator request or limit intent matches the workload
- local queue is used only when Kueue scheduling is intentionally enabled
- node selectors match labels actually present on the intended nodes
- tolerations match taints actually present on the intended nodes
- profile enablement state matches the demo stage intent

## Dashboard Visibility

- Profile appears on Settings -> Hardware profiles.
- Profile appears in the Create workbench hardware profile list when intended.
- Profile appears on the `HardwareProfile` CRD instances page.
- Project-scoped profiles appear only in intended projects and are coordinated
  with `rhoai-project-scoped-resources`.

## Recommended Accelerator Tags

For workbench images:

- accelerator identifier exists on the workbench image
- recommended tag appears only for compatible accelerators
- custom workbench image guidance is reviewed with
  `rhoai-workbenches-custom-images` or `rhoai-workbench-image-import`

For serving runtimes:

- custom runtime is editable or cloned from a default runtime before mutation
- `opendatahub.io/recommended-accelerators` uses a JSON array string
- runtime compatibility is reviewed with `rhoai-model-serving-platform`

## GitOps Review

- The owning Argo CD Application is explicit.
- No other Application owns a competing full copy of the same hardware profile.
- Stage README, PLAN, GitOps, deploy, and validate scripts agree.
- If the profile is global, it is owned by the shared RHOAI platform layer.
- If the profile is project-scoped, it is owned by the consuming project stage.
- Kustomize renders locally before live deployment.
