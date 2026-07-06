# Model Registry Workflow Patterns

## Dashboard Paths

The official chapter uses both of these paths:

```text
OpenShift AI dashboard -> AI hub -> Registry
OpenShift AI dashboard -> AI hub -> Models -> Registry
```

Use the label shown in the active dashboard when writing runbooks.

## Register Metadata Only

Use this shape when documenting model registration without copying artifacts:

```text
Registry: acme-model-registry
Model name: acme-risk-model
Model description: ACME governed risk-scoring model
Version name: v1
Source model format: ONNX
Source model format version: 1
Location type: URI
URI: oci://<public-oci-registry>/<org>/risk-model:v1
Decision: Register metadata only; artifact already exists in public OCI format.
```

## Register And Store As ModelCar

Use this shape when artifacts must be copied into an OCI ModelCar image:

```text
Transfer job name: Upload ACME model v1 to Quay
Project: acme-model-registry-jobs
Origin type: Object storage
Endpoint: https://s3.amazonaws.com
Bucket: acme-model-artifacts
Region: eu-central-1
Path: /models/acme-model/v1
Destination registry: quay.io
Destination image: acme/private-ai/acme-model:v1
Credentials: provided through the dashboard, not committed
Expected artifact URI: oci://quay.io/acme/private-ai/acme-model:v1
```

The path must point to a model or folder and must not point to the bucket root.

## Transfer Job Review

```text
Job status: Pending | Running | Complete | Failed
Review:
- job display name and resource name
- namespace
- author
- model and version links after success
- event log when failed
Retry behavior:
- creates a new job
- creates a new Kubernetes resource name
- can delete the failed job during retry
Delete behavior:
- deletes the Job and owned ConfigMap/Secrets
- does not delete successful OCI registry artifacts
```

## Metadata Review

Recommended demo metadata:

```text
Model labels:
- genai
- private-ai
- validated-demo
Model properties:
- license: <license URL>
- source: <artifact source URL>
- evaluation: <evaluation evidence URL>
- intended-use: <short use case>
Version properties:
- model-format: ONNX
- artifact-uri: oci://...
- benchmark: <benchmark result URL>
- deployment-target: KServe ModelCar
```

## Archive Safety

Before archiving:

```text
Model has deployments: no
Version has deployments: no
All deployments deleted from AI hub -> Deployments: yes
Archive target: model | model version
Restore path tested: yes
```
