# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 guide captured in
`source-capture.md`.

## Concept Model

Model serving makes a trained model available as a service that can be queried
through an API. OpenShift AI supports model storage from S3-compatible object
storage, PVCs, and OCI images before deployment.

The guide describes two model serving platform choices:

| Platform | Official use case |
|----------|-------------------|
| Model serving platform | Dedicated runtime server per model; recommended for production use and suitable for large models, LLMs, and generative AI |
| NVIDIA NIM model serving platform | NVIDIA Inference Microservices for NVIDIA-optimized model deployment; requires the model serving platform first |

## Core CRDs

The model serving platform uses model-serving runtimes. Runtime configuration
is represented through `ServingRuntime` and `InferenceService` CRDs.

### ServingRuntime

`ServingRuntime` defines the runtime environment used to deploy and manage a
model. It creates pod templates that load model formats and exposes an
inferencing endpoint.

Officially documented field areas include:

- `apiVersion: serving.kserve.io/v1alpha1`
- `kind: ServingRuntime`
- `metadata.annotations.opendatahub.io/recommended-accelerators`
- `metadata.annotations.openshift.io/display-name`
- `metadata.labels.opendatahub.io/dashboard`
- container command, args, env, image, name, and ports
- Prometheus scrape annotations
- `multiModel`
- `supportedModelFormats`

### InferenceService

`InferenceService` creates the inference service that receives queries,
invokes the model, and returns inference output.

Officially documented responsibilities include:

- model location and format
- serving runtime selection
- passthrough route enablement for REST or gRPC
- HTTP or gRPC endpoint definition

Officially documented field areas include:

- `apiVersion: serving.kserve.io/v1beta1`
- `kind: InferenceService`
- `metadata.annotations.openshift.io/display-name`
- `metadata.annotations.serving.knative.openshift.io/enablePassthrough`
- `metadata.annotations.sidecar.istio.io/inject`
- `metadata.annotations.sidecar.istio.io/rewriteAppHTTPProbers`
- `metadata.labels.opendatahub.io/dashboard`
- `spec.predictor.minReplicas`
- `spec.predictor.maxReplicas`
- `spec.predictor.model.modelFormat.name`
- `spec.predictor.model.resources`
- `spec.predictor.model.runtime`
- `spec.predictor.model.storage.key`
- `spec.predictor.model.storage.path`
- `spec.predictor.tolerations`

## Accelerator Runtimes

OpenShift AI includes preinstalled model-serving runtimes that support
accelerators.

| Accelerator family | Runtime guidance |
|--------------------|------------------|
| NVIDIA GPUs | Use the vLLM NVIDIA GPU ServingRuntime for KServe; GPU support must be enabled first, including Node Feature Discovery and NVIDIA GPU enablement |
| Intel Gaudi | Use the vLLM Intel Gaudi Accelerator ServingRuntime for KServe; install Intel Gaudi support and configure a hardware profile |
| AMD GPUs | Use the vLLM AMD GPU ServingRuntime for KServe; install AMD GPU support and configure a hardware profile |
| IBM Spyre | Use the Spyre-specific vLLM runtime for the target architecture; x86_64 support is Technology Preview in RHOAI 3.4, while IBM Z and IBM Power support status depends on the referenced release context |

Supported runtimes are listed in the Red Hat supported configurations article.
Tested and verified runtimes are community runtimes tested against OpenShift AI
versions. Tested and verified runtimes are not directly supported by Red Hat;
customers are responsible for licensing, configuration, and maintenance.

## Enabling The Model Serving Platform

Prerequisites:

- The operator is logged in to OpenShift AI with administrator privileges.
- KServe is installed.

Dashboard path to enable the platform:

```text
OpenShift AI dashboard -> Settings -> Cluster settings -> General settings
```

Workflow:

1. Locate Model serving platforms.
2. Select Model serving platform.
3. Save changes.

Dashboard path to enable runtimes:

```text
OpenShift AI dashboard -> Settings -> Model resources and operations -> Serving runtimes
```

Workflow:

1. Open Serving runtimes.
2. Enable the preinstalled runtime that should be available for deployments.

Verification:

- The platform is available for model deployments.
- The selected runtime appears enabled on the Serving runtimes page.

## Speculative Decoding And Multi-Modal Inferencing

The vLLM NVIDIA GPU ServingRuntime for KServe can be configured for
speculative decoding and vision-language model inferencing.

Prerequisites:

- The operator has OpenShift AI administrator privileges.
- When using a draft model for speculative decoding, the original and draft
  models are stored in the same S3-compatible object storage folder.

Configuration is done when deploying a model, using the vLLM NVIDIA GPU
runtime and the Configuration parameters section.

Supported argument patterns from the official guide:

- n-gram speculative decoding:
  - `--speculative-model=[ngram]`
  - `--num-speculative-tokens=<NUM_SPECULATIVE_TOKENS>`
  - `--ngram-prompt-lookup-max=<NGRAM_PROMPT_LOOKUP_MAX>`
  - `--use-v2-block-manager`
- draft-model speculative decoding:
  - `--port=8080`
  - `--served-model-name={{.Name}}`
  - `--distributed-executor-backend=mp`
  - `--model=/mnt/models/<path_to_original_model>`
  - `--speculative-model=/mnt/models/<path_to_speculative_model>`
  - `--num-speculative-tokens=<NUM_SPECULATIVE_TOKENS>`
  - `--use-v2-block-manager`
- multi-modal inferencing:
  - `--trust-remote-code`

Only use `--trust-remote-code` with trusted models.

Verification:

- Use an OpenAI-compatible `/v1/chat/completions` request against the inference
  endpoint, with bearer-token authorization.
- For VLMs, include text and image URL content in the request body.

## Custom Model-Serving Runtimes

Administrators can add custom runtimes when preinstalled runtimes do not meet
requirements.

Support boundary:

- Red Hat does not support custom runtimes.
- The customer is responsible for licensing, configuration, and maintenance.

Prerequisites:

- The operator has OpenShift AI administrator privileges.
- The custom runtime image is built and pushed to a container registry.

Dashboard path:

```text
OpenShift AI dashboard -> Settings -> Model resources and operations -> Serving runtimes
```

Workflow:

1. Duplicate an existing runtime or select Add serving runtime.
2. Select Single-model serving platform.
3. Select REST or gRPC protocol.
4. Upload a YAML file or start from scratch in the embedded YAML editor.
5. Add the runtime.
6. Optionally edit the custom runtime later.

Important behavior:

- A newly added custom runtime is automatically enabled.
- Custom runtimes often require custom `env` parameters in the
  `ServingRuntime` spec.

Verification:

- The custom runtime appears on the Serving runtimes page in enabled state.
- The selected API protocol is visible.

## Tested And Verified Runtimes

Administrators can add tested and verified runtimes from the dashboard. The
guide includes examples for IBM Power, IBM Z, and NVIDIA Triton runtimes.

Support boundary:

- Tested and verified runtimes are not directly supported by Red Hat.
- The customer is responsible for licensing, configuration, and maintenance.

Key review points:

- The `metadata.name` for a runtime must not match an existing runtime.
- Optional display name is set with
  `metadata.annotations.openshift.io/display-name`.
- If no display name is configured, OpenShift AI displays `metadata.name`.
- Runtime is automatically enabled after creation.

## NVIDIA NIM Platform Enablement

The NVIDIA NIM platform is based on the model serving platform. The model
serving platform must be enabled first.

Prerequisites:

- The operator has OpenShift AI administrator privileges.
- Model serving platform is enabled.
- The `disableNIMModelServing` dashboard configuration option is `false`.
- GPU support is enabled, including NFD and NVIDIA GPU Operator.
- An NVIDIA Cloud Account can access NGC.
- The NCA account has the NVIDIA AI Enterprise Viewer role.
- A personal API key has been generated on the NGC portal.

Upgrade caveat:

- If NIM was enabled before an OpenShift AI upgrade, the personal API key must
  be re-entered to re-enable NIM.

Dashboard path:

```text
OpenShift AI dashboard -> Applications -> Explore -> NVIDIA NIM
```

Workflow:

1. Find the NVIDIA NIM tile.
2. Click Enable.
3. Enter the personal API key.
4. Submit.

Verification:

- NVIDIA NIM appears on the Enabled applications page.

## Customizing Model Deployments

Runtime configuration can be customized for one deployment without changing the
default runtime configuration. The customization can be made during deployment
or by editing an existing deployment.

Prerequisites:

- The operator has OpenShift AI administrator privileges.
- A model has been deployed.

Dashboard path:

```text
OpenShift AI dashboard -> AI hub -> Deployments
```

Workflow for an existing deployment:

1. Stop the target deployment.
2. Edit it.
3. In Configuration parameters, modify additional serving runtime arguments or
   additional environment variables.
4. Redeploy.
5. Start the deployment.

Do not modify port or model-serving runtime arguments that require specific
values. Overwriting required values can cause deployment failure.

vLLM KV cache environment variable:

- `VLLM_CPU_KVCACHE_SPACE` defines dedicated KV cache memory size in GiB.
- The official example uses `VLLM_CPU_KVCACHE_SPACE=40`.
- The default is `0`, meaning no dedicated KV cache is reserved and vLLM uses
  available system memory at runtime, which can lead to out-of-memory errors.

Verification:

- The deployment appears with a healthy status on the project Deployments tab
  and dashboard Deployments page.
- Runtime arguments appear in `spec.predictor.model.args`.
- Environment variables appear in `spec.predictor.model.env`.
- The official CLI verification shape is:

```bash
oc get -o json inferenceservice <inferenceservicename/modelname> -n <projectname>
```

## vLLM Runtime Model-Specific Arguments

The guide lists example additional arguments for Llama, Granite, and Mistral
models. Treat these as official examples for those named model families only.

Common field from the examples:

- `--distributed-executor-backend=mp`

Other documented examples include:

- `--max-model-len=<tokens>`
- `--tensor-parallel-size=4` for the Granite 20B example, distributing
  inference across four GPUs in one node

For this repo, do not reuse Granite, Llama, or Mistral values for Nemotron or
other models without a model-specific source.

## Default Cluster-Wide Deployment Strategy

Administrators can set the default deployment strategy for new model
deployments.

Prerequisites:

- The operator has OpenShift AI administrator privileges.
- Model serving is enabled.

Dashboard path:

```text
OpenShift AI dashboard -> Settings -> Cluster settings -> General settings
```

Workflow:

1. Open Model deployment options.
2. In Default deployment strategy, select one:
   - Rolling update
   - Recreate
3. Save changes.

Verification:

- In the deployment wizard for a new model, the Advanced settings deployment
  strategy is preselected with the configured default.

## Out Of Scope For This Guide

This guide does not define:

- installing OpenShift AI, KServe, Service Mesh, Serverless, or dependent
  Operators
- a full user-facing model deployment workflow
- model registry, model catalog, MaaS, or llm-d governance
- full runtime image provenance for every model family
- object storage bucket, connection, or credential lifecycle
- a complete GitOps representation for dashboard model-serving settings
