# Stage 030: Private Model Serving

## Why This Matters

Private model serving is the point where the platform starts to provide an on-cluster AI capability for sensitive development and modernization workflows. The value is not only that a model runs on OpenShift, but that it runs through platform-managed namespaces, RBAC, model metadata, hardware profiles, and GitOps reconciliation.

## What This Stage Adds

- Local `LLMInferenceService` resources for `gpt-oss-20b` and `nemotron-3-nano-30b-a3b`.
- The `maas` data science project and administrative RBAC for model management.
- LeaderWorkerSet prerequisites used by the local model-serving path.
- Model Registry seed data for the two local models.
- The MaaS tier mapping workaround required by the current OpenShift AI webhook before tier-annotated model resources can be accepted.

The local models are the private model path used later by Models-as-a-Service, Red Hat OpenShift Dev Spaces, and Migration Toolkit for Applications.

## Deploy And Validate

```bash
./stages/030-private-model-serving/deploy.sh
./stages/030-private-model-serving/validate.sh
```

Manifests: [`gitops/stages/030-private-model-serving/base/`](../../gitops/stages/030-private-model-serving/base/)

## Next Stage

[Stage 040: Governed Models-as-a-Service](../040-governed-models-as-a-service/README.md) adds the MaaS control point, gateway policy, quotas, telemetry, and subscriptions.
