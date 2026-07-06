# Official Documentation Extraction

## Concept Model

The model catalog is a curated discovery surface where data scientists and AI
engineers find and evaluate available generative AI models. Users can evaluate
models before registering them in a model registry and deploying them to a model
serving runtime.

The model registry stores metadata and lifecycle records for models before
deployment and is the governance bridge between experimentation and serving.

## Catalog Discovery

Dashboard path:

```text
AI hub -> Models -> Catalog
```

The catalog page shows a high-level view of available models, including:

- model category
- model name
- description
- labels such as task, license, and provider
- performance benchmarks for validated third-party models

Catalog categories:

- All models
- Red Hat AI models
- Red Hat AI validated models
- Other models, shown when administrator-configured catalog sources have no
  labels
- custom categories named from administrator-configured catalog source labels

Search and filters:

- search by model name, description, or provider
- filter by task, provider, license, language, and tensor type

The model details page includes model description and model card information
provided by the model provider, such as intended use, limitations, training
parameters and datasets, and evaluation results.

`s390x` note:

- only `granite-3.3-8b-instruct` is supported on `s390x`
- its model card is available from All models

## Validated Model Performance

For validated models, users can open the Performance Insights tab to compare
performance metrics for specific hardware configurations.

Performance filters include:

- scenario or workload type, such as Chatbot
- latency metric and percentile, such as P90
- maximum acceptable latency value in milliseconds
- maximum requests per second threshold
- hardware type, such as H200

Metrics called out in the official guide:

- `E2E`: end-to-end request latency
- `TTFT`: time to first token
- `TPS`: tokens per second
- `ITL`: inter-token latency

## Model Performance View

The Model performance view displays only validated models and filters models
with workload and hardware constraints. It sorts models from lowest to highest
latency and displays performance data on cards instead of description and
labels.

Default filter settings:

- scenario: Chatbot
- latency: Time to first token for 90th percentile
- Max RPS: 1
- hardware: none

When a user opens a validated model card after enabling Model performance view,
the active performance constraints transfer to the model's Performance Insights
tab. Returning by using the Catalog breadcrumb transfers filter changes back to
the catalog. Returning by using the left navigation Models link deactivates the
Model performance view.

Performance Insights also supports Customize columns independently of the
performance filters.

## Tensor Types And Variants

Each tensor type is a compression variant of the same base model. Variants can
have different performance trade-offs and hardware requirements.

Example variants from the official guide:

- FP16: full precision, higher quality, heavier resource needs
- INT8: quantized to 8 bits, balance between quality and efficiency
- INT4: quantized to 4 bits, lighter and lower accuracy

The Tensor type filter is always available and works whether Model performance
view is enabled or not. The Performance Insights tab includes the Model
variants by tensor type comparison card only for validated models with variants.

## Registering From The Catalog

Prerequisites:

- user is logged in to OpenShift AI
- user has access to an available model registry

Workflow:

- open AI hub -> Models -> Catalog
- search or filter models
- open a model details page
- click Register model
- select a model registry
- optionally update model name and description
- enter version name and optional version description
- enter source model format, for example `ONNX`
- enter source model format version
- review the displayed model URI
- register the model

Registration from the model catalog is not supported on `s390x`.

Verification:

- new model details and version appear on the model details Overview tab
- new model and version appear on the Model registry page

## Deploying From The Catalog

The official guide states that model serving deployments use the global cluster
pull secret to pull models in OCI-compliant ModelCar format from the catalog.

Prerequisites:

- model-serving deployment prerequisites are complete
- `modelregistry` component is enabled

Workflow:

- open AI hub -> Models -> Catalog
- search or filter models
- open a model details page
- click Deploy model
- choose model type: Generative AI model or Predictive model
- select target project
- enter model deployment name
- optionally edit resource name
- enter description
- select hardware profile
- optionally customize CPU and memory requests and limits
- choose auto-selected or manually selected serving runtime
- for predictive AI models, optionally select model framework
- set number of model server replicas
- configure advanced settings
- review and deploy

Catalog deployment details:

- generative model is the default catalog model type
- model location and URI fields are read-only for catalog models
- model deployment name becomes the inference service name
- resource names cannot exceed 253 characters, must use lowercase
  alphanumeric characters or `-`, must start and end with an alphanumeric
  character, and cannot be edited after creation
- catalog models use `default-profile`
- auto-select runtime analyzes model framework and available hardware profiles
- manual runtime selection can use global and project-scoped serving runtime
  templates

Advanced settings:

- Add as AI asset endpoint, with use case such as chat, multimodal, or natural
  language processing
- model must be added as an AI asset endpoint to test it in Gen AI studio ->
  playground
- token authentication and service accounts
- custom runtime arguments
- custom runtime environment variables
- deployment strategy: Rolling update or Recreate

Rolling update is the default strategy and aims for zero downtime. Recreate
terminates existing pods before starting new pods and causes downtime.

Advanced settings are not supported on `s390x`.

Verification:

- deployment appears on AI hub -> Deployments
- deployment appears in Latest deployments on the model details page
- deployment appears on the Deployments tab for the model version
