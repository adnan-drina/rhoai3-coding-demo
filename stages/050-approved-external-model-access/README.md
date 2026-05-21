# Stage 050: Approved External Model Access

## Why This Matters

Most enterprises will not make one universal model choice. Some tasks need private inference because source code or regulated context must stay inside OpenShift. Other tasks may be approved for an external frontier model because the data classification and provider policy allow it.

Stage 050 keeps that distinction explicit. It registers approved external models as MaaS assets so consumers use the same governed access pattern, while making clear that prompts sent to those models are still processed by the external provider.

## Architecture

![Stage 050 layered capability map](../../docs/assets/architecture/stage-050-capability-map.svg)

## What This Stage Adds

This stage adds approved external model choices to the MaaS portfolio.

- OpenAI-backed `ExternalModel` resources for `gpt-4o` and `gpt-4o-mini`.
- `MaaSModelRef` resources so external models appear as MaaS-published choices.
- Platform-owned provider credential handling through `OPENAI_API_KEY`.
- MaaS authorization, subscription, gateway, and token-limit policy for external model access.
- Validation that separates model registration from opt-in external inference.
- An optional GuideLLM smoke test for environments where provider token spend is approved.

External inference is intentionally optional. If `OPENAI_API_KEY` is not set, the models can still be registered and governed, but inference calls are expected to fail.

## What To Notice And Why It Matters

Stage 050 extends the MaaS operating model without hiding the provider boundary.

- External models are registered as approved platform assets instead of being configured directly in developer tools.
- The committed Secret is a placeholder; `deploy.sh` provisions the live `openai-api-key` only from the operator's local environment.
- Consumers still use MaaS-issued API keys, subscriptions, token limits, and gateway policy.
- Validation checks governance resources by default and runs external inference only when explicitly requested.

This matters because unmanaged external access creates copied API keys, unknown consumers, inconsistent limits, and weak usage trails. MaaS centralizes access and telemetry, but data classification and provider approval still decide whether external processing is allowed.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift AI provides the MaaS access model, OpenAI-compatible consumption pattern, API key issuance, and subscription-aware limits. Red Hat OpenShift provides namespaces, RBAC, Secrets, routes, service networking, and identity. Red Hat OpenShift GitOps keeps approved model records and policies reproducible without storing real provider credentials in Git.

Red Hat Connectivity Link, Gateway API, Kuadrant, and Authorino keep external model access on the governed API path introduced in Stage 040.

## Trust Boundaries

Governed external access is not private model serving. MaaS centralizes provider credentials, consumer API keys, subscriptions, token limits, gateway policy, and telemetry, but prompts are processed by the external provider. Sensitive code or regulated data must not use this path unless organizational policy explicitly allows it.

## Red Hat Products Used

- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides the MaaS model access context.
- **[Red Hat Connectivity Link](https://www.redhat.com/en/technologies/cloud-computing/connectivity-link)** provides the governed gateway path.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides namespaces, RBAC, Secrets, routes, identity integration, and service networking.
- **[Red Hat OpenShift GitOps](https://www.redhat.com/en/technologies/cloud-computing/openshift/gitops)** reconciles external model resources, subscriptions, and policy.

## Open Source Projects To Know

- [Open Data Hub models-as-a-service](https://github.com/opendatahub-io/models-as-a-service) is the upstream project behind the MaaS APIs.
- [Gateway API](https://gateway-api.sigs.k8s.io/) provides routing primitives.
- [Kuadrant](https://kuadrant.io/) provides gateway policy patterns.
- [Authorino](https://www.authorino.io/) provides external authorization.
- [GuideLLM](https://github.com/vllm-project/guidellm) provides the opt-in smoke test.

## Deploy And Validate

```bash
./stages/050-approved-external-model-access/deploy.sh
./stages/050-approved-external-model-access/validate.sh
```

To run a small external inference smoke test through MaaS, set `OPENAI_API_KEY` and opt in:

```bash
GUIDELLM_EXTERNAL_SMOKE_TEST=true \
GUIDELLM_REQUESTS=1 \
GUIDELLM_OUTPUT_TOKENS=32 \
./stages/050-approved-external-model-access/validate.sh
```

Use the smoke test only when provider token spend is approved for the demo environment.

Manifests: [`gitops/stages/050-approved-external-model-access/base/`](../../gitops/stages/050-approved-external-model-access/base/)

## References

- [Red Hat OpenShift AI 3.4: Use Models-as-a-Service](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/govern_llm_access_with_models-as-a-service/use-models-as-a-service_maas)
- [Red Hat: What is Model-as-a-Service?](https://www.redhat.com/en/topics/ai/what-is-models-as-a-service)
- [MaaS code assistant quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- [Open Data Hub models-as-a-service](https://github.com/opendatahub-io/models-as-a-service)
- [Gateway API](https://gateway-api.sigs.k8s.io/)
- [Kuadrant](https://kuadrant.io/)
- [Authorino](https://www.authorino.io/)
- [GuideLLM](https://github.com/vllm-project/guidellm)
- [OpenAI API documentation](https://platform.openai.com/docs)

## Next Stage

[Stage 060: MCP Context Integrations](../060-mcp-context-integrations/README.md) adds tool-context integrations with their own data boundaries.
