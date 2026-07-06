# Model Deployment Patterns

These are review patterns derived from the official Deploying models guide.
Verify CRDs, runtime availability, storage credentials, hardware profiles,
routes, token Secrets, and quota before copying anything into GitOps or
runbooks.

## OCI Model Image Pattern

```Dockerfile
FROM registry.access.redhat.com/ubi9/ubi-micro:latest
COPY --chown=0:0 models /models
RUN chmod -R a=rX /models
USER 65534
```

Review points:

- The base image must provide a shell; the guide says not to use `scratch`.
- Files must be readable by the root group for OpenShift random user IDs.
- OpenVINO models that need version directories should use paths such as
  `models/1/<model-file>`.
- For durable demo artifacts, prefer a reviewed tag or digest instead of
  relying on mutable tags.

## OCI InferenceService Pattern

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata:
  name: sample-isvc-using-oci
spec:
  predictor:
    model:
      runtime: kserve-ovms
      modelFormat:
        name: onnx
      storageUri: oci://quay.io/<user_name>/<repository_name>:<tag_name>
      resources:
        requests:
          memory: 500Mi
          cpu: 100m
        limits:
          memory: 4Gi
          cpu: 500m
```

Private registry addition:

```yaml
spec:
  predictor:
    imagePullSecrets:
      - name: <pull-secret-name>
```

Review points:

- `runtime` must match a `ServingRuntime` in the project.
- `modelFormat.name` must match the model artifact.
- Add GPU requests only when the runtime and model require them and GPU quota
  exists.
- Private OCI repositories need an image pull Secret.

## Deployment Decision Record

```text
Model: <model-name>
Model type: Generative AI | Predictive
Storage source: OCI | S3 | URI | PVC
Runtime selection: auto | manual
Serving runtime: <runtime-name>
Hardware profile: <profile-name>
Replicas: <count>
Strategy: Recreate | Rolling update
External route: enabled | disabled
Token authentication: required | not required
AI asset endpoint: enabled | disabled
Runtime endpoint path: <path>
Limitations: <quota, TP runtime, endpoint, or auth notes>
```

Review points:

- Use Recreate when GPU quota cannot support parallel old and new pods.
- Use Rolling update only when double-capacity headroom is documented.
- Add AI asset endpoint when Gen AI studio playground testing is required.
- Require token authentication for shared external demo endpoints unless a
  documented exception exists.

## vLLM Chat Request Pattern

```bash
curl -k "https://<inference-endpoint>:443/v1/chat/completions" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${TOKEN}" \
  -d '{
    "model": "<model-name>",
    "messages": [
      {
        "role": "user",
        "content": "Write a short readiness check response."
      }
    ]
  }'
```

Review points:

- Use `/v1/chat/completions` for chat-capable generative vLLM models.
- Do not use `/v1/embeddings` with generative models.
- Check chat-template requirements when the model does not include a predefined
  template.

## Deployment Evidence Record

```text
Project: <namespace>
Runtime: <serving-runtime>
API resource: <InferenceService or verified equivalent>
Ready state: <ready/not-ready>
Endpoint: <internal/external URL>
Token Secret: <secret name only>
Smoke test: passed | failed
Metrics handoff: rhoai-model-management-monitoring | deferred
```

Review points:

- Store only Secret names and evidence metadata, not token values.
- Link failures to troubleshooting evidence rather than overwriting results.
