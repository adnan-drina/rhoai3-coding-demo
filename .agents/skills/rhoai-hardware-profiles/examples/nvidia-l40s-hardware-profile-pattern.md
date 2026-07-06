# NVIDIA L40S Hardware Profile Pattern

This is the intended demo profile contract for review and planning. Do not copy
it as a complete `HardwareProfile` manifest. Export a dashboard-created profile
or verify the active CRD schema before writing GitOps YAML.

## Demo Intent

| Field | Intended value |
|-------|----------------|
| Profile purpose | Queue-backed NVIDIA L40S GPU profiles for workbenches and later model-serving workloads |
| Accelerator identifier | `nvidia.com/gpu` |
| Default GPU request | 1 schedulable `nvidia.com/gpu` unit |
| Default GPU limit | 1 unit unless the verified schema or workload policy uses another shape |
| Default node type | AWS `g6e.2xlarge` |
| Default node count | 1 GPU worker |
| Primary model path | `nemotron-3-nano-30b-a3b` through Stage 210 model serving and Stage 220 MaaS |
| Profile ownership | Shared RHOAI platform stage unless a project-specific stage needs a scoped copy |

## Scheduling Handoff

Verify these before encoding scheduling constraints:

```bash
oc get nodes -l node-role.kubernetes.io/gpu
oc describe node <gpu-node-name> | rg -n "Labels:|Taints:|nvidia.com/gpu"
```

Suggested demo intent, subject to live verification:

- node selector target: GPU worker label used by the active MachineSet
- toleration target: GPU-only taint used by the active MachineSet
- accelerator resource: `nvidia.com/gpu`

Do not use selectors or tolerations from this example if the active cluster
uses different labels or taints.

## Kueue Handoff

If the stage uses Kueue:

- select the intended local queue through the hardware profile workflow
- verify Kueue restrictions with `rhoai-kueue-workload-management`
- avoid conflicting node selectors or tolerations unless official docs and
  active schema validation support the combination

## Recommended Accelerator Tags

Workbench images:

- Add or select `nvidia.com/gpu` only for images that are compatible with
  NVIDIA GPU acceleration.
- If an image has no accelerator identifier, add the identifier before creating
  the associated hardware profile.

Serving runtimes:

```yaml
metadata:
  annotations:
    opendatahub.io/recommended-accelerators: '["nvidia.com/gpu"]'
```

Use this annotation only on custom serving runtimes that are compatible with
the NVIDIA GPU profile. Clone default runtimes before editing when the
dashboard requires it.

## GitOps Promotion Pattern

1. Create the hardware profile in the dashboard or verify the active CRD.
2. Export the profile:

   ```bash
   oc get hardwareprofiles.infrastructure.opendatahub.io <profile-name> -n <namespace> -o yaml
   ```

3. Remove live-only metadata before committing.
4. Place the manifest under the owning GitOps stage or shared RHOAI platform
   owner.
5. Validate with `references/validation-checklist.md`.
