# Model-Serving Platform Patterns

These examples are review patterns and minimal snippets. Verify active CRDs,
runtime templates, image provenance, model storage, and dashboard state before
copying any pattern into GitOps.

## Dashboard Enablement

Enable the platform:

```text
OpenShift AI dashboard
-> Settings
-> Cluster settings
-> General settings
-> Model serving platforms
-> Model serving platform
-> Save changes
```

Enable runtimes:

```text
OpenShift AI dashboard
-> Settings
-> Model resources and operations
-> Serving runtimes
-> enable the target runtime
```

Review points:

- KServe must be installed first.
- Dashboard visibility flags must not hide KServe or serving runtime controls.
- Enable only runtimes that have a clear model and hardware purpose.

## ServingRuntime Review Fragment

```yaml
apiVersion: serving.kserve.io/v1alpha1
kind: ServingRuntime
metadata:
  name: vllm-runtime
  annotations:
    openshift.io/display-name: vLLM ServingRuntime for KServe
    opendatahub.io/recommended-accelerators: '["nvidia.com/gpu"]'
  labels:
    opendatahub.io/dashboard: "true"
spec:
  multiModel: false
  supportedModelFormats:
  - name: vLLM
    autoSelect: true
  containers:
  - name: kserve-container
    image: <verified-runtime-image>
    args:
    - --port=8080
    - --model=/mnt/models
    - --served-model-name={{.Name}}
```

Review points:

- Verify image source and digest before use.
- Keep recommended accelerator annotations aligned with installed hardware.
- Do not assume this fragment is complete for every vLLM model.

## InferenceService Review Fragment

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: <model-name>
  annotations:
    openshift.io/display-name: <display-name>
    serving.knative.openshift.io/enablePassthrough: "true"
    sidecar.istio.io/inject: "true"
    sidecar.istio.io/rewriteAppHTTPProbers: "true"
  labels:
    opendatahub.io/dashboard: "true"
spec:
  predictor:
    minReplicas: 1
    maxReplicas: 1
    model:
      modelFormat:
        name: vLLM
      runtime: vllm-runtime
      storage:
        key: <connection-secret-or-storage-key>
        path: <model-path>
      resources:
        requests:
          cpu: "1"
          memory: 8Gi
          nvidia.com/gpu: "1"
        limits:
          cpu: "6"
          memory: 24Gi
          nvidia.com/gpu: "1"
```

Review points:

- Runtime must exist and be enabled.
- Storage key and path must match real model storage.
- Resource values must match the selected model and cluster capacity.
- GPU requests must use the verified accelerator identifier.

## vLLM Runtime Parameter Patterns

Speculative decoding with n-grams:

```text
--speculative-model=[ngram]
--num-speculative-tokens=<NUM_SPECULATIVE_TOKENS>
--ngram-prompt-lookup-max=<NGRAM_PROMPT_LOOKUP_MAX>
--use-v2-block-manager
```

Speculative decoding with a draft model:

```text
--port=8080
--served-model-name={{.Name}}
--distributed-executor-backend=mp
--model=/mnt/models/<path_to_original_model>
--speculative-model=/mnt/models/<path_to_speculative_model>
--num-speculative-tokens=<NUM_SPECULATIVE_TOKENS>
--use-v2-block-manager
```

Multi-modal inferencing:

```text
--trust-remote-code
```

Review points:

- Use `--trust-remote-code` only with trusted model sources.
- Keep model-specific values tied to source documentation for that model.
- Do not overwrite required port or runtime arguments.

## Demo Nemotron 3 Nano vLLM Profile

The rhoai3-demo Stage 210 direct-serving baseline adapts the Nemotron-specific
runtime configuration from the Red Hat-maintained
`rh-ai-quickstart/maas-code-assistant` implementation. Treat this as a
model-specific implementation reference, not as generic vLLM guidance.

```text
resources.requests.cpu: "2"
resources.requests.memory: 16Gi
resources.requests.nvidia.com/gpu: "1"
resources.limits.cpu: "4"
resources.limits.memory: 24Gi
resources.limits.nvidia.com/gpu: "1"

--enable-force-include-usage
--disable-uvicorn-access-log
--enable-prefix-caching
--max-model-len=8192
--max-num-batched-tokens=8192
--enable-auto-tool-choice
--tool-call-parser=qwen3_coder
--trust-remote-code
--reasoning-parser-plugin=/mnt/models/nano_v3_reasoning_parser.py
--reasoning-parser=nano_v3
```

Review points:

- The quickstart was tested on AWS `g6e.2xlarge` L40S GPU instances with at
  least 48GB GPU VRAM.
- The active demo uses the same modelcar source with prefix caching and an
  8192-token initial serving envelope. Larger context windows need separate
  benchmark evidence before they are exposed through MaaS.
- Stage 210 uses a direct `InferenceService`; Stage 220 should use the
  quickstart's `LLMInferenceService`, MaaS tier, Gateway, and RBAC patterns
  only after RHOAI 3.4 schema verification.
- Keep the Red Hat registry modelcar URI for this project unless a newer
  official Red Hat artifact is selected and documented.
- For full direct-serving and MaaS examples, use
  `examples/nemotron-vllm-configurations.md`.

## vLLM KV Cache Environment Variable

```text
VLLM_CPU_KVCACHE_SPACE=40
```

Review points:

- Value is in GiB.
- Match the value to actual node memory and expected parallelism.
- The default `0` does not reserve dedicated KV cache memory.

## NVIDIA NIM Enablement

```text
1. Enable the model serving platform.
2. Confirm disableNIMModelServing is false.
3. Verify NVIDIA GPU support.
4. Confirm NGC account, Viewer role, and personal API key.
5. Open Applications -> Explore.
6. Enable the NVIDIA NIM tile.
7. Enter the personal API key.
8. Confirm NVIDIA NIM appears under Enabled applications.
```

Review points:

- Keep the API key out of Git and logs.
- Re-enter the API key after upgrades when required.
- Do not enable NIM unless the demo explicitly needs it.

## Default Deployment Strategy

```text
OpenShift AI dashboard
-> Settings
-> Cluster settings
-> General settings
-> Model deployment options
-> Default deployment strategy
-> Rolling update or Recreate
-> Save changes
```

Review points:

- Verify the new deployment wizard preselects the chosen strategy.
- Record the demo default in operations notes when implemented.

## Read-Only Checks

Run only after following the repository OpenShift safety guard:

```bash
oc get servingruntime -A
oc get inferenceservice -A
oc explain servingruntime.spec
oc explain inferenceservice.spec.predictor
oc get -o json inferenceservice <inferenceservicename/modelname> -n <projectname>
```
