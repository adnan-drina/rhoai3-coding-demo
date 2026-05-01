# Stage 040: Governed Models-as-a-Service

## Why This Matters

Models-as-a-Service (MaaS) turns local model serving into a governed platform capability. Platform teams can publish model choices while centralizing identity, subscriptions, API keys, rate limits, token limits, telemetry, and gateway policy.

## What This Stage Adds

- The upstream MaaS controller and PostgreSQL backing services used by this OpenShift AI 3.3 demo posture.
- Red Hat Connectivity Link, Gateway API, Kuadrant, and Authorino policy resources.
- Local `MaaSModelRef`, `MaaSAuthPolicy`, and `MaaSSubscription` resources for the private models from Stage 030.
- Rate limit, token rate limit, and telemetry policy resources.
- Grafana and Prometheus-facing resources for model access visibility.
- Jobs that patch cluster-specific gateway and MaaS API behavior documented in `BACKLOG.md`.

## Red Hat Alignment And Demo Deviations

This stage follows the Red Hat OpenShift AI Models-as-a-Service (MaaS) pattern: models are published through a governed API path with Gateway API, Red Hat Connectivity Link, Kuadrant, Authorino, subscriptions, API keys, rate limits, token limits, and telemetry.

The implementation also includes deliberate demo deviations:

- Red Hat OpenShift AI 3.4 documents MaaS as a Technology Preview feature. This demo currently uses Red Hat OpenShift AI 3.3 plus upstream MaaS components where needed so the full external model registration story can be shown.
- The upstream MaaS controller, upstream `maas-api` image, PostgreSQL storage, and tokens bridge are included to demonstrate `ExternalModel` and `MaaSModelRef` registration before that path is available through the supported Red Hat OpenShift AI 3.3 operator flow.
- Community Grafana is included as a disposable demo add-on for visibility. A Red Hat-supported monitoring or observability path is preferred for long-lived environments.
- Cluster-specific Gateway hostname and TLS details are patched by PostSync jobs. The Argo CD ignore rules are intentionally narrow so GitOps still reports meaningful drift.

Keep `BACKLOG.md` and `docs/OPERATIONS.md` current whenever these deviations change.

## Deploy And Validate

```bash
./stages/040-governed-models-as-a-service/deploy.sh
./stages/040-governed-models-as-a-service/validate.sh
```

Manifests: [`gitops/stages/040-governed-models-as-a-service/base/`](../../gitops/stages/040-governed-models-as-a-service/base/)

## Next Stage

[Stage 050: Approved External Model Access](../050-approved-external-model-access/README.md) adds external OpenAI models behind the same governed MaaS path.
