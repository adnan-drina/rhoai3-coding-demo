# Validation Checklist

Use this checklist before accepting model deployment README content, GitOps
manifests, examples, runbooks, notebooks, or scripts.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official Deploying models guide is recorded when storage, deployment,
  endpoint, or runtime inference behavior is introduced.
- Model-serving platform enablement and runtime configuration are checked with
  `rhoai-model-serving-platform`.
- Deployed-model metrics and day-2 operations are checked with
  `rhoai-model-management-monitoring`.
- TrustyAI bias/drift monitoring is checked with `rhoai-monitoring-trustyai`.
- AI asset endpoint testing is checked with `rhoai-gen-ai-playground`.
- Catalog and registry deployment handoffs are checked with
  `rhoai-model-catalog-workflows` and `rhoai-model-registry-workflows`.
- S3 and project connection behavior is checked with
  `rhoai-s3-object-storage-data` and `rhoai-project-workflows`.
- NVIDIA GPU prerequisites are checked with `rhoai-nvidia-gpu-accelerators`.
- API support posture is checked with `rhoai-api-tiers`.

## Deployment Review

- Project exists and access is explicit.
- Model storage source is intentional: S3, URI, OCI/modelcar, or PVC.
- Project connection or image pull Secret exists for private storage.
- Model type is correct: Predictive or Generative AI.
- Serving runtime choice is justified:
  - auto-select when one distinct runtime match exists
  - manual selection when multiple matches exist or a specific runtime is
    required
- Hardware profile matches the required accelerator.
- GPU deployment is not promised until GPU support and hardware profiles are
  present.
- Replicas, CPU, memory, and accelerator requests fit project quota.
- Deployment strategy is documented:
  - Rolling update only with about 200% resource headroom
  - Recreate when GPU scarcity or maintenance downtime is acceptable
- AI asset endpoint registration is set when playground testing is required.
- External route and token authentication settings match the client access
  model.
- Endpoint tokens are stored in Secrets and never committed.

## OCI And CLI Review

- OCI model image uses a shell-capable base image; do not use `scratch`.
- Model files are readable by the root group and compatible with OpenShift
  random user IDs.
- OpenVINO examples use numbered model version directories when required.
- `ServingRuntime` name matches `InferenceService.spec.predictor.model.runtime`.
- `modelFormat.name` matches the model artifact.
- `storageUri` uses the intended OCI repository and tag or digest.
- Private OCI repositories use `spec.predictor.imagePullSecrets`.
- `InferenceService` fields are verified against official docs or active CRD
  schema before GitOps use.
- Public KServe exposure and authentication posture are explicitly reviewed.

## Runtime Endpoint Review

- Endpoint URL is copied from the deployed model details or `InferenceService`
  status.
- Runtime-specific path is appended correctly.
- Token authentication header is included when enabled.
- vLLM chat requests use `/v1/chat/completions`.
- vLLM embeddings endpoint is used only with supported embedding models, not
  generative models.
- vLLM chat-template requirements are checked when a model lacks a predefined
  template.
- OpenVINO, Triton, and MLServer requests use Open Inference Protocol v2
  payload shape.
- MLServer requests include `Content-Type: application/json`.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get project <project>
oc get servingruntimes -n <project>
oc get inferenceservice -n <project>
oc describe inferenceservice <name> -n <project>
oc get secret -n <project>
oc get hardwareprofiles -A
```

Schema checks:

```bash
oc explain servingruntime.spec
oc explain inferenceservice.spec
oc explain inferenceservice.spec.predictor.model
```

Endpoint checks:

```bash
curl -k -H "Authorization: Bearer ${TOKEN}" \
  "https://<inference-endpoint>:443/v1/models"

curl -k -H "Authorization: Bearer ${TOKEN}" \
  -H "Content-Type: application/json" \
  "https://<inference-endpoint>:443/v1/chat/completions"
```

## Fail Conditions

Stop and correct the work if any of these are true:

- A model is deployed from storage without a documented storage source and
  credential model.
- A private registry, S3 bucket, URI source, or endpoint token value is
  committed.
- Runtime auto-selection is assumed when multiple runtime templates match.
- Rolling update is selected for scarce GPU resources without double-capacity
  headroom.
- An external endpoint is exposed without an intentional authentication
  decision.
- A generative model is tested through vLLM embeddings endpoint.
- GitOps manifests use unverified fields copied from dashboard behavior.
- A live cluster command bypasses the OpenShift safety guard.
