# Stage 040: Governed Models-as-a-Service

## Why This Matters

Models-as-a-Service (MaaS) turns model serving into a governed platform capability. Platform teams can publish model choices while centralizing identity, subscriptions, API keys, rate limits, token limits, telemetry, and gateway policy.

The important shift is that developers and tools do not need to know every backing model endpoint. They consume a governed model access layer that can apply the same controls across private and approved external model paths.

## Architecture

![Stage 040 layered capability map](../../docs/assets/architecture/step-03-capability-map.svg)

## What This Stage Adds

- The upstream MaaS controller and PostgreSQL backing services used by this Red Hat OpenShift AI 3.3 demo posture.
- Red Hat Connectivity Link, Gateway API, Kuadrant, and Authorino policy resources.
- Local `MaaSModelRef`, `MaaSAuthPolicy`, and `MaaSSubscription` resources for the private models from Stage 030.
- Rate limit, token rate limit, and telemetry policy resources.
- Grafana and Prometheus-facing resources for model access visibility.
- Jobs that patch cluster-specific gateway and MaaS API behavior documented in [`BACKLOG.md`](../../BACKLOG.md).

## What To Notice In The Demo

Show MaaS as the control point, not as another model endpoint:

1. Local models from Stage 030 are published as subscribed MaaS models.
2. API keys are issued centrally instead of being managed in each developer tool.
3. Gateway policy enforces authentication, rate limits, token limits, and telemetry.
4. The same model access pattern is prepared for developer workspaces and MTA.

The proof point is governance. Model access becomes a platform service with identity, policy, and observability attached.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift AI provides the MaaS direction and the dashboard experience for model access. Red Hat Connectivity Link, Gateway API, Kuadrant, and Authorino provide the API governance path used to authenticate requests and enforce model access policy.

This demo also includes deliberate implementation choices. Red Hat OpenShift AI 3.4 documents MaaS as a Technology Preview feature, while the demo currently runs Red Hat OpenShift AI 3.3 plus selected upstream MaaS components so the full external model registration story can be shown. The upstream MaaS controller, upstream `maas-api` image, PostgreSQL storage, and tokens bridge are demo deviations tracked in [`BACKLOG.md`](../../BACKLOG.md) and [`docs/OPERATIONS.md`](../../docs/OPERATIONS.md).

Community Grafana is included as a disposable demo add-on for visibility. A Red Hat-supported monitoring or observability path is preferred for long-lived environments.

## Red Hat Products Used

- **Red Hat OpenShift AI** provides the model-serving and MaaS platform context.
- **Red Hat Connectivity Link** provides the gateway and policy layer used in the MaaS governance path.
- **Red Hat OpenShift GitOps** reconciles the MaaS, gateway, policy, and observability resources.
- **Red Hat OpenShift** provides the runtime platform, identity, networking, routes, and storage foundation.

## Open Source Projects To Know

- [Open Data Hub models-as-a-service](https://github.com/opendatahub-io/models-as-a-service) provides the upstream MaaS controller and APIs used by this demo posture.
- [Gateway API](https://gateway-api.sigs.k8s.io/) provides Kubernetes-native API routing primitives.
- [Kuadrant](https://kuadrant.io/) provides gateway policy patterns for authentication, rate limiting, and protection.
- [Authorino](https://www.authorino.io/) provides external authorization for gateway-protected APIs.
- [CloudNativePG](https://cloudnative-pg.io/) provides the PostgreSQL database used by the MaaS API in this demo.

## Trust Boundaries

MaaS provides consistent access, authentication, rate limiting, and visibility across private and external model paths. It does not make an external model private. In this stage, MaaS is publishing private local models from Stage 030; Stage 050 adds governed external model records with a separate provider boundary.

Cluster-specific Gateway hostname and TLS details are patched by PostSync jobs. The Argo CD ignore rules are intentionally narrow so GitOps still reports meaningful drift while allowing those runtime values to come from the cluster.

## Why This Is Worth Knowing

The enterprise value of model serving appears when access can be managed centrally. MaaS gives platform teams a way to offer model choice without asking every development team to solve identity, keys, quotas, routing, and telemetry on its own.

## Where This Fits In The Full Platform

| Earlier capability | How MaaS uses it |
|--------------------|------------------|
| Stage 030 private model serving | Publishes local models as governed MaaS model choices |
| Stage 010 platform identity | Uses OpenShift identity and RBAC boundaries around model access |

| Later capability | What MaaS provides |
|------------------|--------------------|
| Stage 050 external access | Reuses the same governed path for approved external model records |
| Stage 070 Dev Spaces | Supplies OpenAI-compatible endpoints and API keys for coding assistants |
| Stage 080 MTA | Supplies the governed model endpoint for Developer Lightspeed for MTA |

## Deploy And Validate

Operational commands are kept here for workshop operators.

```bash
./stages/040-governed-models-as-a-service/deploy.sh
./stages/040-governed-models-as-a-service/validate.sh
```

Manifests: [`gitops/stages/040-governed-models-as-a-service/base/`](../../gitops/stages/040-governed-models-as-a-service/base/)

## References

- [Red Hat OpenShift AI documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/)
- [Red Hat OpenShift AI MaaS documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/govern_llm_access_with_models-as-a-service/use-models-as-a-service_maas)
- [Red Hat Connectivity Link gateway policies](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html-single/configuring_and_deploying_gateway_policies/configuring_and_deploying_gateway_policies)
- [Gateway API](https://gateway-api.sigs.k8s.io/)
- [Kuadrant](https://kuadrant.io/)
- [Authorino](https://www.authorino.io/)

## Next Stage

[Stage 050: Approved External Model Access](../050-approved-external-model-access/README.md) adds external OpenAI models behind the same governed MaaS path.
