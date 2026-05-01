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

## Deploy And Validate

```bash
./stages/040-governed-models-as-a-service/deploy.sh
./stages/040-governed-models-as-a-service/validate.sh
```

Manifests: [`gitops/stages/040-governed-models-as-a-service/base/`](../../gitops/stages/040-governed-models-as-a-service/base/)

## Next Stage

[Stage 050: Approved External Model Access](../050-approved-external-model-access/README.md) adds external OpenAI models behind the same governed MaaS path.
