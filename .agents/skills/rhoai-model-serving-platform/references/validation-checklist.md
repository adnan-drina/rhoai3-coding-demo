# Validation Checklist

Use this checklist before accepting model-serving platform documentation,
runbooks, or GitOps changes.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official guide URL uses the active `/3.4/` baseline path.
- The work is about model-serving platform configuration, serving runtimes,
  runtime customization, NIM enablement, or default deployment strategy.
- KServe and OpenShift AI installation are delegated to
  `rhoai-self-managed-installation`.
- GPU enablement and hardware profiles are delegated to
  `rhoai-nvidia-gpu-accelerators`.
- Project-scoped serving runtime templates are delegated to
  `rhoai-project-scoped-resources`.
- User model deployment flows, MaaS, and llm-d are not claimed as covered by
  this skill.

## Platform Enablement Review

- Operator has OpenShift AI administrator privileges.
- KServe is installed before enabling the model serving platform.
- Dashboard path is used:

  ```text
  Settings -> Cluster settings -> General settings
  ```

- Model serving platform is selected under Model serving platforms.
- Required preinstalled runtimes are enabled from:

  ```text
  Settings -> Model resources and operations -> Serving runtimes
  ```

- Dashboard flags that hide KServe or serving runtime controls are reviewed
  with `rhoai-dashboard-customization`.

## ServingRuntime Review

- `apiVersion` is `serving.kserve.io/v1alpha1` unless active schema and docs
  prove otherwise.
- `kind` is `ServingRuntime`.
- `metadata.name` is unique in the target namespace.
- Display name uses `metadata.annotations.openshift.io/display-name` when a
  user-friendly dashboard name is needed.
- Dashboard visibility uses `metadata.labels.opendatahub.io/dashboard: "true"`
  when the runtime should appear in OpenShift AI.
- Recommended accelerator annotations match installed accelerator support.
- Container image provenance is official, tested, verified, or explicitly
  documented as a custom runtime exception.
- `supportedModelFormats` match the model format actually being deployed.
- `multiModel` intent is explicit.
- Prometheus annotations, ports, command, args, env, and resources are sourced
  from official docs, installed templates, or active CRD/schema verification.

## InferenceService Review

- `apiVersion` is `serving.kserve.io/v1beta1` unless active schema and docs
  prove otherwise.
- `kind` is `InferenceService`.
- Runtime name matches an enabled `ServingRuntime`.
- Model format matches the runtime's supported formats.
- Model storage key and path match an existing connection and object path.
- Resource requests and limits fit the selected hardware profile and cluster
  capacity.
- GPU resource requests use the verified accelerator identifier, normally
  `nvidia.com/gpu` for this demo.
- Tolerations are paired with actual node taints.
- Passthrough, Istio sidecar, and HTTP prober annotations are verified before
  being committed to GitOps.

## Custom Runtime Review

- Custom runtime need is documented; preinstalled runtime was insufficient.
- Custom runtime support boundary is recorded: Red Hat does not support custom
  runtimes.
- Runtime image has a reviewed registry source and digest or immutable tag.
- Runtime was added by duplicating a trusted runtime or with YAML verified
  against official docs and active schema.
- REST or gRPC protocol choice is intentional.
- Custom `env` parameters are documented and do not contain secrets.
- Runtime appears enabled on the Serving runtimes page.

## Tested And Verified Runtime Review

- Tested-and-verified support boundary is recorded: the runtime is not
  directly supported by Red Hat.
- Licensing and maintenance ownership are documented.
- Any IBM or NVIDIA registry prerequisites are documented.
- Runtime name does not collide with an existing runtime.
- Optional display name is set when dashboard clarity matters.
- Runtime appears enabled after creation.

## NVIDIA NIM Review

- Model serving platform is enabled before NIM.
- `disableNIMModelServing` is `false`.
- NVIDIA GPU support is installed and verified.
- NGC account and NVIDIA AI Enterprise Viewer role are confirmed.
- Personal API key handling is documented and kept out of Git.
- If NIM was previously enabled before an upgrade, the API key is re-entered.
- NVIDIA NIM appears on Applications -> Enabled after enablement.

## Runtime Parameter Review

- Custom runtime arguments and environment variables apply only to the selected
  model deployment.
- Required port and runtime arguments are not overwritten unless official
  runtime docs prove the change is valid.
- `--trust-remote-code` is used only with trusted model sources.
- Speculative decoding paths are backed by the required model storage layout.
- Model-specific vLLM flags are not copied from Granite, Llama, or Mistral
  examples to unrelated models without a model-specific source.
- `VLLM_CPU_KVCACHE_SPACE` is sized to hardware capacity.
- First-deployment readiness waits account for large image and modelcar pulls.
  Fresh clusters can spend several minutes pulling modelcar, vLLM runtime,
  scheduler, router, and tokenizer images before readiness conditions become
  useful. Inspect pod events and image pull progress before changing manifest
  fields.

## Default Deployment Strategy Review

- Model serving is enabled.
- Default strategy is one of:
  - Rolling update
  - Recreate
- A new model deployment wizard shows the selected strategy in Advanced
  settings.
- Operations docs record the demo default when implemented.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get servingruntime -A
oc get inferenceservice -A
oc explain servingruntime.spec
oc explain inferenceservice.spec.predictor
oc get -o json inferenceservice <inferenceservicename/modelname> -n <projectname>
oc get events -n <projectname> --sort-by=.lastTimestamp
```

Additional dashboard-backed checks:

- Serving runtimes page shows expected runtime enabled state.
- Deployments page shows healthy deployment status.
- New deployment wizard shows the intended default deployment strategy.
- For llm-d or `LLMInferenceService` handoff, validate
  `status.conditions[?(@.type=="Ready")].status == "True"` before layering MaaS
  subscriptions or Playground validation on top.

## GitOps Review

- Long-lived `ServingRuntime` and `InferenceService` resources are managed
  through ArgoCD once active GitOps implementation exists.
- Dashboard-only settings are not automated until official docs or active
  schema verification identifies backing fields.
- Manifest labels follow `project-gitops-authoring` conventions.
- Runtime image and model artifact provenance are checked with
  `project-red-hat-doc-alignment-review`.
- README claims match implemented runtime, model, endpoint, and accelerator
  behavior.

## Fail Conditions

- KServe is not installed before the model serving platform is enabled.
- A custom or tested runtime is described as Red Hat-supported.
- A runtime image is introduced without provenance.
- A ServingRuntime or InferenceService field is added without official source
  or schema verification.
- Required port or runtime arguments are overwritten and deployment fails.
- Validation gives up during a progressing first image pull without checking
  events and configured readiness timeout.
- `--trust-remote-code` is used with an untrusted model source.
- NIM credentials are committed or logged.
- Demo docs claim model-serving behavior that is not implemented or validated.
