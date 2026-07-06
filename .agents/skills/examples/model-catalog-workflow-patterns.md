# Model Catalog Workflow Patterns

## Dashboard Path

```text
OpenShift AI dashboard -> AI hub -> Models -> Catalog
```

Use the label shown in the active dashboard when writing runbooks.

## Discovery Review

```text
Catalog category: Red Hat AI validated models
Search: <model name, description, or provider>
Filters:
- Task: Text-generation
- Provider: <provider>
- License: Apache 2.0
- Language: Japanese
- Tensor type: BF16
Review:
- model card intended use
- model card limitations
- training and evaluation notes
- provider labels
```

## Performance Evaluation

```text
Model performance view: enabled
Scenario: Chatbot
Latency metric: TTFT
Percentile: P90
Max latency: <milliseconds>
Max RPS: <minimum requests per second>
Hardware: <hardware type>
Decision:
- selected model variant
- selected tensor type
- selected hardware profile rationale
- remaining validation needed in this demo
```

Treat catalog performance data as selection evidence. Keep demo-specific
validation separate.

## Register From Catalog

```text
Source: AI hub -> Models -> Catalog
Registry: acme-model-registry
Model name: <catalog model name>
Version name: v1
Source model format: ONNX
Source model format version: 1
Model URI: read-only from catalog
Verification:
- model version appears on the Overview tab
- model appears on the Model registry page
```

Do not use this registration workflow on `s390x`.

## Deploy From Catalog

```text
Source: AI hub -> Models -> Catalog
Model type: Generative AI model
Project: acme-model-serving
Model deployment name: acme-catalog-model
Hardware profile: default-profile
Runtime selection: auto-select best runtime
Replicas: 1
Advanced:
- Add as AI asset endpoint: yes
- Use case: chat
- Token authentication: required
- Deployment strategy: Rolling update
Verification:
- AI hub -> Deployments
- Latest deployments on model details
- Deployments tab for the model version
```

Catalog deployments pull OCI-compliant ModelCar models through the global
cluster pull secret. Check the serving-platform skill for runtime and advanced
deployment details.
