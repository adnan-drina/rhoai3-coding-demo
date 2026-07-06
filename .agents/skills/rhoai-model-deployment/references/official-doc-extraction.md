# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 Deploying models guide
captured in `source-capture.md`.

## Model Storage

Before deployment, a model must be stored in an accessible location. The guide
covers:

- S3-compatible object storage
- URI-based repositories
- OCI containers/modelcars
- Persistent Volume Claims

OCI containers for model storage are also known as modelcars in KServe.
Benefits described by the guide include reduced startup times, reduced local
disk use, and improved model performance through pre-fetched images.

## OCI Model Images

The guide's OCI model image example:

- uses an ONNX MobileNet model
- creates a `models/1` directory because OpenVINO uses numbered subdirectories
  for model versioning
- uses a shell-capable base image instead of `scratch`, because KServe needs a
  shell to ensure model files are accessible
- changes ownership of copied model files and grants root-group read
  permissions because OpenShift runs containers with random user IDs and the
  root group
- builds and pushes an OCI image with Podman

Do not treat the example model or registry as a demo default. Use it as a
field-placement and artifact-packaging pattern.

## PVC Model Storage

PVC deployment path:

- create a PVC with context type `Model storage`
- attach it to a running workbench
- upload files through JupyterLab or code-server under `/opt/app-root/src/`
- choose Existing cluster storage in the Deploy model dialog
- select the PVC and specify the model path

Use PVC model storage for small interactive workflows or when the demo
intentionally shows workbench-to-serving handoff. Prefer OCI or object storage
for durable GitOps-shaped artifacts.

## Model Serving Platform Deployment

The model serving platform is based on KServe and deploys each model from a
dedicated model server. The guide positions this architecture for large models
that require more resources, including LLMs.

General prerequisites:

- user is logged in to OpenShift AI
- KServe is installed and the model serving platform is enabled
- a preinstalled or custom model-serving runtime is enabled
- a project exists
- model storage and project connection exist for S3, URI, OCI registry, or PVC
- GPU support is enabled when the model server needs GPUs

Runtime-specific prerequisites include:

- Caikit-TGIS requires the model converted to Caikit format.
- vLLM NVIDIA GPU requires GPU support and Node Feature Discovery.
- vLLM CPU is used for IBM Z and IBM Power where GPU accelerators are not
  available.
- vLLM Intel Gaudi requires HPU support and hardware profiles.
- vLLM AMD GPU requires AMD GPU operator and hardware profiles.
- vLLM Spyre x86 is Technology Preview in the guide.
- vLLM Spyre ppc64le is General Availability in the guide.

## Runtime Selection

OpenShift AI can automatically select a serving runtime by analyzing:

- model type
- model format
- selected hardware profile

Hardware profile matching filters runtimes by accelerator. For NVIDIA GPU
profiles, compatible runtime examples include vLLM NVIDIA GPU ServingRuntime
for KServe.

Automatic selection limitations:

- automatic selection is available only when a hardware profile exists for the
  accelerator
- predictive models require model format before runtime selection
- the Auto-select option appears only when one distinct match exists
- if multiple templates match one accelerator, the user must manually select a
  runtime
- manual selection can choose global or project-scoped serving runtime
  templates
- administrator settings can override matching by enabling distributed
  inference with llm-d by default for generative models

## Deployment Strategy

The guide covers two deployment strategies:

- Rolling update: zero-downtime rollout, but requires about 200% of request
  resources during transition because old and new pods run briefly in
  parallel.
- Recreate: conserves resources by terminating old pods before new pods start,
  but introduces endpoint downtime.

Recreate applies to all runtimes except Distributed inference with llm-d. When
llm-d is selected, strategy options are not displayed and the system defaults
to Recreate.

Use Recreate when GPU quota is scarce or downtime is acceptable. Use Rolling
update only when enough CPU, memory, and accelerator headroom exists.

## Deploy A Model Wizard

The Deploy a model wizard captures:

- model location and connection details
- model type: Predictive or Generative AI model
- model deployment name and description
- hardware profile
- optional CPU and memory requests and limits
- serving runtime: auto-select or manual list
- predictive model framework
- number of model server replicas
- AI asset endpoint registration for generative AI models
- external route exposure
- token authentication and service account name
- advanced runtime-specific settings

AI asset endpoint registration is required when the model should be tested in
Gen AI studio playground.

## MLServer Deployment

MLServer deployment is covered for trained predictive models with frameworks
such as scikit-learn, XGBoost, LightGBM, ONNX, and TensorFlow.

Important guide details:

- choose Predictive model type
- select the MLServer runtime
- use the correct model framework and model format
- enable Add custom runtime environment variables when the model file is not
  under `/mnt/models` or does not use a well-known filename
- configure `MLSERVER_MODEL_URI` to point to the model file path, such as
  `/mnt/models/my-custom-model.pkl`

The guide labels MLServer ServingRuntime for KServe as Technology Preview in
the inference endpoint section.

## OCI Model Deployment By CLI

The CLI example deploys an OCI-stored ONNX model on OpenVINO Model Server.

Resources and fields:

- process the `kserve-ovms` template from `redhat-ods-applications`
- `ServingRuntime` named `kserve-ovms`
- `apiVersion: serving.kserve.io/v1beta1`
- `kind: InferenceService`
- `spec.predictor.model.runtime`
- `spec.predictor.model.modelFormat.name`
- `spec.predictor.model.storageUri`
- `spec.predictor.model.resources.requests`
- `spec.predictor.model.resources.limits`
- `spec.predictor.imagePullSecrets` for private OCI repositories

Important security note:

- by default in KServe, models are exposed outside the cluster and are not
  protected with authentication.

Verification:

- `oc get servingruntimes`
- `oc get inferenceservice`
- readiness state and URL are present in `InferenceService` output

## NVIDIA NIM Deployment

NIM deployment prerequisites:

- user is logged in to OpenShift AI
- NVIDIA NIM model serving platform is enabled
- project exists
- GPU support is enabled through Node Feature Discovery and NVIDIA GPU
  Operator

NIM deployment dialog captures:

- unique model deployment name
- selected NVIDIA NIM model
- NIM storage size
- model server replicas
- model server size
- hardware profile
- optional CPU/memory resource customization
- optional external route
- optional token authentication and service account names

The guide notes an Amazon EBS resize cooldown issue for PVC resizing:
`VolumeModificationRateExceeded` can occur if an EBS-backed PVC is resized
before the six-hour cooldown expires.

## Inference Requests

Token lookup:

- open the project Deployments tab
- expand the deployed model
- read the token Secret field in the Token authentication section
- copy token value when needed

Endpoint lookup:

- use AI hub -> Deployments
- read the Inference endpoints field
- append the runtime-specific path

When token authentication is enabled, requests must include the
`Authorization` header with the token value.

Runtime endpoint examples captured by the guide:

- Caikit TGIS:
  - `:443/api/v1/task/text-generation`
  - `:443/api/v1/task/server-streaming-text-generation`
- OpenVINO Model Server:
  - `/v2/models/<model-name>/infer`
- vLLM NVIDIA GPU ServingRuntime for KServe:
  - `:443/version`
  - `:443/docs`
  - `:443/v1/models`
  - `:443/v1/chat/completions`
  - `:443/v1/completions`
  - `:443/v1/embeddings`
  - `:443/tokenize`
  - `:443/detokenize`
- NVIDIA Triton:
  - `v2/models/[/versions/<model_version>]/infer`
  - readiness, liveness, metadata, and gRPC endpoints
- MLServer:
  - `/v2`
  - `/v2/health/live`
  - `/v2/health/ready`
  - `/v2/models/{model_name}`
  - `/v2/models/{model_name}/infer`
  - `/v2/models/{model_name}/ready`

vLLM notes:

- vLLM runtime is compatible with the OpenAI REST API.
- embeddings endpoint requires a vLLM-supported embeddings model and cannot be
  used with generative models.
- vLLM v0.5.5 and later requires a chat template for
  `/v1/chat/completions` if the model does not include a predefined template.
- external API requests use the HTTPS port of the OpenShift router, usually
  port 443.

## Monitoring Handoff

The Deploying models guide includes user-facing metrics views for deployed
models and NIM models. Use `rhoai-model-management-monitoring` for detailed
monitoring configuration, metric queries, Grafana, autoscaling, and NIM
metrics operations.
