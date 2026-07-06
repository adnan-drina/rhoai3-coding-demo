# Validation Checklist

Use this checklist before approving NVIDIA GPU accelerator GitOps, docs, or
hardware profile changes.

## Source Review

- Skill and README references use the active baseline in
  `docs/PLATFORM_BASELINE.md`.
- NVIDIA is the only accelerator path described for the demo.
- AMD, Intel Gaudi, and IBM Spyre paths are not introduced unless explicitly
  marked out of scope.
- Hardware profile manifest fields are verified against the active CRD or
  exported from a dashboard-created profile before GitOps promotion.

## Operator And Runtime Review

- NFD Operator is installed.
- A `NodeFeatureDiscovery` instance exists after NFD Operator installation.
- NVIDIA GPU Operator is installed.
- NVIDIA `ClusterPolicy` exists after GPU Operator installation.
- KMM Operator appears in installed Operator verification.
- The `rhods-dashboard` deployment is restarted after NVIDIA enablement.
- `migration-gpu-status` cleanup is handled when applicable.

## AWS GPU MachineSet Review

- MachineSet shape is derived from an existing worker MachineSet in the active
  AWS cluster, not copied from another environment.
- Instance type is `g6e.2xlarge` unless an environment-specific plan says
  otherwise.
- Default desired GPU worker count is one node.
- GPU MachineSet and template labels include
  `cluster-api/accelerator=nvidia-gpu`.
- GPU node template includes `node-role.kubernetes.io/gpu`.
- GPU node template taint is `nvidia-gpu-only:NoSchedule`, or any replacement
  taint is updated consistently across ClusterPolicy, hardware profiles, and
  workload tolerations.
- MachineAutoscaler bounds match the environment plan and do not inherit a
  catalog example without cost and quota review.
- If an Argo CD sync-hook generator is used, generated MachineSets and
  MachineAutoscalers are captured back into Git or explicitly documented as a
  disposable bootstrap exception.
- Hook Job RBAC, if used, is reviewed with `ocp-security-rbac-scc`.

## GPU Detection Review

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get machinesets -n openshift-machine-api -l cluster-api/accelerator=nvidia-gpu
oc get machineautoscalers -n openshift-machine-api
oc get csv -A | rg -i "nvidia|node feature|nfd|kernel module|kmm|gpu"
oc get nodefeaturediscovery -A
oc get clusterpolicy
oc get nodes -o wide
oc describe node <gpu-node-name> | rg -A20 "Capacity|Allocatable|nvidia.com/gpu"
```

Expected signal:

- GPU worker nodes show `nvidia.com/gpu` in capacity and allocatable values.

## Hardware Profile Review

Before creating or changing hardware profile manifests:

```bash
oc api-resources | rg -i "hardwareprofile"
oc explain hardwareprofile.spec
oc get hardwareprofile -A
```

Review that each profile:

- uses the NVIDIA accelerator identifier `nvidia.com/gpu`
- matches an observed GPU node type and GPU count; current demo intent is
  `g6e.2xlarge` nodes with one allocatable `nvidia.com/gpu` each
- has visibility appropriate for the demo audience
- defines resource limits for GPU, CPU, and memory only after confirming the
  active CRD schema
- uses Local queue only when Kueue is configured for the target projects
- uses node selectors and tolerations only after confirming live node labels
  and taints

## Model Serving Intent Review

- `nemotron-3-nano-30b-a3b` is the default private GenAI model.
- The model source is the Red Hat modelcar image
  `oci://registry.redhat.io/rhai/modelcar-nvidia-nemotron-3-nano-30b-a3b-fp8:3.0`.
- The private model is served with RHOAI `LLMInferenceService` and vLLM.
- `LLMInferenceService`, Gateway, scheduler, autoscaling, auth, and
  flow-control details are reviewed with `rhoai-distributed-inference-llmd`.
- The private model requests one `nvidia.com/gpu` per replica.
- OpenAI `gpt-5.4-mini` is treated as an approved external MaaS model through
  the `gpt-5-4-mini` resource alias and does not influence GPU node sizing.
- Before implementing it in MaaS, verify the active MaaS gateway supports the
  OpenAI API surface required by the selected model.

## Serving Runtime Review

For custom serving runtimes that should show NVIDIA as recommended:

```yaml
metadata:
  annotations:
    opendatahub.io/recommended-accelerators: '["nvidia.com/gpu"]'
```

Do not edit the default OpenVINO Model Server runtime directly. Duplicate or use
a custom serving runtime when applying recommended accelerator annotations.

## Fail Conditions

- A README claims GPU support before nodes report `nvidia.com/gpu`.
- `NodeFeatureDiscovery` or NVIDIA `ClusterPolicy` is missing.
- Hardware profile YAML is committed without CRD/schema verification.
- Non-NVIDIA accelerator guidance is mixed into the demo path.
- Serving runtime recommended accelerator annotations are added to an
  uneditable default runtime.
