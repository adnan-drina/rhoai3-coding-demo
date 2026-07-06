# Demo NVIDIA GPU Hardware Profile Contract

This file records the intended demo hardware profile behavior. It is not a
substitute for the active `HardwareProfile` CRD schema. Before creating GitOps
manifests, verify the schema with `oc explain hardwareprofile.spec` or export a
dashboard-created hardware profile and normalize it into GitOps.

## Current Demo GPU Shape

| Field | Value |
|-------|-------|
| AWS worker shape | `g6e.2xlarge` |
| Default GPU MachineSet replicas | `1` |
| Kubernetes accelerator identifier | `nvidia.com/gpu` |
| GPU allocation pattern | one L40S GPU per node, time-sliced to four schedulable `nvidia.com/gpu` units |
| Primary private model | `nemotron-3-nano-30b-a3b` |
| Primary model source | `oci://registry.redhat.io/rhai/modelcar-nvidia-nemotron-3-nano-30b-a3b-fp8:3.0` |
| Serving path | Stage 210 RHOAI model serving with vLLM; Stage 220 MaaS |
| Approved external model | OpenAI `gpt-5.4-mini` through MaaS using resource alias `gpt-5-4-mini`, after gateway/API compatibility is verified |

Use the active node labels and allocatable `nvidia.com/gpu` values as the
scheduling authority. The profile names below use NVIDIA L40S naming because
the active `g6e.2xlarge` worker exposes L40S hardware.

## Direct Profile: NVIDIA 1GPU

| Field | Value |
|-------|-------|
| Display name | NVIDIA 1GPU |
| Suggested resource name | `nvidia-l40s-1gpu` |
| Purpose | Direct single-GPU scheduling for inference, workbenches, and compatibility paths |
| Accelerator identifier | `nvidia.com/gpu` |
| Accelerator resource type | Accelerator |
| GPU default/min/max | `1` / `1` / `1` |
| Visibility | Visible everywhere unless a future step needs project-scoped profiles |
| Allocation strategy | Node selectors and tolerations |

Initial direct scheduling intent:

```text
node selector:
  node-role.kubernetes.io/gpu = ""
toleration:
  key = nvidia.com/gpu
  operator = Equal
  value = true
  effect = NoSchedule
```

## Queue Profile: NVIDIA 1GPU Queued

| Field | Value |
|-------|-------|
| Display name | NVIDIA 1GPU Queued |
| Suggested resource name | `nvidia-l40s-1gpu-queued` |
| Purpose | Preferred queue-managed single-GPU profile for private model serving |
| Accelerator identifier | `nvidia.com/gpu` |
| Accelerator resource type | Accelerator |
| GPU default/min/max | `1` / `1` / `1` |
| Visibility | Visible everywhere unless a future step needs project-scoped profiles |
| Allocation strategy | Kueue LocalQueue |
| LocalQueue | stage-specific LocalQueue such as `lq-gpu-shared` or `lq-gpu-reserved-demo` |

Use this profile when Kueue is configured for the target project and the
workload should consume GPU quota through the platform queue.

## Model Placement Contract

`nemotron-3-nano-30b-a3b` should be the default private GenAI workload:

```text
kind: LLMInferenceService
model.name: nemotron-3-nano-30b-a3b
model.uri: oci://registry.redhat.io/rhai/modelcar-nvidia-nemotron-3-nano-30b-a3b-fp8:3.0
resources.requests/limits:
  nvidia.com/gpu: "1"
toleration:
  key = nvidia.com/gpu
```

Review `LLMInferenceService`, Gateway, scheduler, autoscaling, auth, and
flow-control details with `rhoai-distributed-inference-llmd` before promoting
the serving manifest.

OpenAI `gpt-5.4-mini` belongs in the approved external MaaS path through the
DNS-safe `gpt-5-4-mini` resource alias. It should be governed by MaaS
subscriptions, auth policy, rate limits, token limits, and usage telemetry, but
it should not drive GPU MachineSet sizing.

## Manifest Promotion Rule

Do not promote a `HardwareProfile` YAML manifest from this contract alone.

Use one of these paths:

1. Create the profile in the OpenShift AI dashboard, export it with `oc get
   hardwareprofile`, and normalize the exported YAML for GitOps.
2. Verify the active CRD with `oc explain hardwareprofile.spec` and write the
   manifest from the verified schema.
3. Reuse this example pattern only after verifying the active CRD, node labels,
   taints, queue names, and observed GPU product.

After promotion, confirm the profile appears:

- on the OpenShift AI Hardware profiles page
- in the Create workbench hardware profile list
- on the `HardwareProfile` CRD instances page
