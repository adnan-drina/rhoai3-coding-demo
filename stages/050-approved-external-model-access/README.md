# Stage 050: Approved External Model Access

## Why This Matters

Some organizations approve external frontier models for selected workloads. The platform challenge is to make that access visible and controlled instead of giving every developer unmanaged provider credentials.

This stage shows that external model access can be exposed through the same governed Models-as-a-Service (MaaS) path used for private models, while still making the external provider boundary explicit.

## Architecture

![Stage 050 layered capability map](../../docs/assets/architecture/stage-050-capability-map.svg)

## What This Stage Adds

- OpenAI-backed `ExternalModel` resources for `gpt-4o` and `gpt-4o-mini`.
- External model `MaaSModelRef`, authorization, and subscription resources.
- `OPENAI_API_KEY` provisioning into the `openai-api-key` Secret when the value exists in `.env`.
- Optional GuideLLM smoke testing against `gpt-4o-mini` through MaaS when `GUIDELLM_EXTERNAL_SMOKE_TEST=true`.
- Validation that external model records are registered, while treating missing provider credentials as a warning rather than a deployment failure.

## What To Notice In The Demo

Show the distinction between governance and privacy:

1. External model records are declared through GitOps and registered with MaaS.
2. Provider credentials are centralized in the platform namespace instead of copied into workspaces.
3. MaaS presents approved external models through the same access pattern as private models.
4. If `OPENAI_API_KEY` is absent, the stage still validates registration but does not claim external inference works.

The proof point is control. External access can be approved, named, subscribed, and audited without pretending that external processing is private.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift AI and MaaS provide the model access pattern. Red Hat Connectivity Link, Gateway API, Kuadrant, and Authorino provide the governed API path already established in Stage 040.

The external registration mechanism in this demo comes from the upstream Open Data Hub models-as-a-service project and is intentionally documented as a demo deviation while the supported Red Hat OpenShift AI operator path evolves. The implementation uses placeholder credentials in GitOps and patches real credentials only from the operator-controlled environment.

## Why This Is Worth Knowing

Many enterprises need both private AI and selective access to frontier models. This stage shows a practical control pattern: private and external model choices can share a developer-facing access layer while preserving distinct data boundaries.

The operational lesson is also important. Local models from Stage 030 expose platform-owned runtime signals: GPU allocation, Kueue admission, vLLM metrics, model readiness, and pod health. External models do not expose those internals to the platform. MaaS can still provide shared governance signals such as subscription, API-key use, request success, latency from the gateway perspective, rate limits, token limits, and usage telemetry.

That distinction keeps the demo honest. External access can be approved, metered, and made convenient, but the provider remains a separate trust and observability boundary.

## Red Hat Products Used

- **Red Hat OpenShift AI** provides the MaaS context and model access experience.
- **Red Hat Connectivity Link** participates in the governed gateway path for model requests.
- **Red Hat OpenShift GitOps** manages the external model registration resources.
- **Red Hat OpenShift** provides the runtime, secret, RBAC, and namespace boundaries.

## Open Source Projects To Know

- [Open Data Hub models-as-a-service](https://github.com/opendatahub-io/models-as-a-service) provides the upstream external model registration APIs used in this demo.
- [Gateway API](https://gateway-api.sigs.k8s.io/) provides the model request routing layer.
- [Kuadrant](https://kuadrant.io/) and [Authorino](https://www.authorino.io/) provide gateway policy enforcement patterns.

## Trust Boundaries

Governed external access is not private model serving. Prompts are still processed by the external provider and must be allowed by policy. MaaS centralizes access, credentials, subscriptions, and telemetry, but it does not change where the external model processes data.

No real provider key should be committed. `OPENAI_API_KEY` is read from the operator environment and used to patch the `openai-api-key` Secret at deploy time.

## Where This Fits In The Full Platform

| Earlier capability | How this stage uses it |
|--------------------|------------------------|
| Stage 040 MaaS | Publishes external model records through the same governed model access path |
| Stage 010 platform identity | Keeps provider credentials and RBAC under platform control |

| Later capability | What this stage provides |
|------------------|--------------------------|
| Stage 070 Dev Spaces | Makes approved external models available to coding assistants when policy and credentials allow |
| Stage 090 Developer Hub | Provides external model entities that can later be documented in the portal catalog |

## Deploy And Validate

Operational commands are kept here for workshop operators.

```bash
./stages/050-approved-external-model-access/deploy.sh
./stages/050-approved-external-model-access/validate.sh
```

By default, validation confirms registration and governance resources without spending provider tokens. To run a small external inference smoke test through the same MaaS/GuideLLM pattern used in Stage 040:

```bash
GUIDELLM_EXTERNAL_SMOKE_TEST=true \
GUIDELLM_REQUESTS=1 \
GUIDELLM_OUTPUT_TOKENS=32 \
./stages/050-approved-external-model-access/validate.sh
```

Use this only when `OPENAI_API_KEY` is approved for the demo environment.

Manifests: [`gitops/stages/050-approved-external-model-access/base/`](../../gitops/stages/050-approved-external-model-access/base/)

## References

- [Red Hat OpenShift AI MaaS documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/govern_llm_access_with_models-as-a-service/use-models-as-a-service_maas)
- [Red Hat: What is Model-as-a-Service?](https://www.redhat.com/en/topics/ai/what-is-models-as-a-service)
- [Red Hat Developer: Run Model-as-a-Service for multiple LLMs on OpenShift](https://developers.redhat.com/articles/2026/03/24/run-model-service-multiple-llms-openshift)
- [MaaS code assistant quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- [Open Data Hub models-as-a-service](https://github.com/opendatahub-io/models-as-a-service)
- [OpenAI API documentation](https://platform.openai.com/docs)

## Next Stage

[Stage 060: MCP Context Integrations](../060-mcp-context-integrations/README.md) adds tool-context integrations with their own data boundaries.
