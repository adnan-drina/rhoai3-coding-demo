# Step 03: Governed Models-as-a-Service

## Why This Matters

Deploying a model is not the same as making AI usable across an enterprise. A single endpoint can support a proof of concept, but shared adoption quickly raises harder platform questions:

- Who is allowed to use the model?
- Which workloads are allowed to use external providers?
- How do we prevent one team from consuming all capacity?
- How do developers discover the right endpoint?
- How do we measure usage for capacity planning, showback, or chargeback?
- How do we switch model backends without rewriting every tool?

Models-as-a-Service is the platform pattern this demo uses to answer those questions. It exposes models as shared API services while centralizing access policy, rate limits, API keys, subscriptions, and usage telemetry.

This step is the center of the architecture. The later coding assistant, terminal agent, MTA Developer Lightspeed workflow, GenAI Playground experience, and portal story all depend on this governed model access layer.

## Architecture

![Step 03 layered capability map](../../docs/assets/architecture/step-03-capability-map.svg)

## What This Step Adds

Step 03 publishes four model choices through one MaaS access pattern:

| Model | Backend | Trust boundary | Why it is included |
|-------|---------|----------------|--------------------|
| `nemotron-3-nano-30b-a3b` | Local vLLM on OpenShift | Private platform boundary | Primary private coding and modernization model |
| `gpt-oss-20b` | Local vLLM on OpenShift | Private platform boundary | Open model alternative for private workloads |
| `gpt-4o` | External OpenAI provider through MaaS | Governed external processing | High-intelligence external model path |
| `gpt-4o-mini` | External OpenAI provider through MaaS | Governed external processing | Fast, lower-cost external model path |

The models are intentionally different. The capability is model choice with a consistent control point, not a claim that one model fits every workload.

- Local LLM serving through `LLMInferenceService` resources for `nemotron-3-nano-30b-a3b` and `gpt-oss-20b` in [`gitops/step-03-llm-serving-maas/base/models/`](../../gitops/step-03-llm-serving-maas/base/models/).
- External OpenAI model registration through `ExternalModel` and `MaaSModelRef` resources in [`gitops/step-03-llm-serving-maas/base/models-maas-crds/`](../../gitops/step-03-llm-serving-maas/base/models-maas-crds/).
- MaaS authorization and subscription resources that define which identities can consume the published models.
- Gateway, rate limit, token limit, authorization, and telemetry policy resources under [`gitops/step-03-llm-serving-maas/base/governance/`](../../gitops/step-03-llm-serving-maas/base/governance/) and [`gitops/step-03-llm-serving-maas/base/gateway/`](../../gitops/step-03-llm-serving-maas/base/gateway/).
- Grafana dashboard and Prometheus-facing metrics resources for usage and operational visibility.
- A read-only OpenShift MCP server and GenAI Playground MCP discovery ConfigMap, with optional Slack and BrightData MCP components kept credential-gated.

The external OpenAI model resources include a placeholder `openai-api-key` Secret. They prove the governed external path is wired, but external inference is only usable after an operator replaces that placeholder with an approved provider credential.

## What To Notice In The Demo

Focus on three platform takeaways.

First, model discovery is separated from backend deployment. The RHOAI dashboard and MaaS API expose consumable model choices without requiring every developer to understand vLLM pods, external provider configuration, gateway policy, or model registry seeding.

Second, local and external models use the same OpenAI-compatible API style and MaaS-issued `sk-oai-*` keys. That consistency is what allows Continue, OpenCode, GenAI Playground, and MTA Developer Lightspeed to consume models without bespoke integration work for each backend.

Third, the trust boundary is explicit. Local model requests stay on the OpenShift platform. External OpenAI requests are centrally governed, but prompt content is still processed by OpenAI. MCP integrations add their own data boundaries and should be enabled only when the connected service is approved.

The operational takeaway is simple access for consumers with centralized control for platform teams.

## How Red Hat And Open Source Make It Work

OpenShift AI provides the GenAI Studio and MaaS user experience, model-serving integration, and model registry context. OpenShift supplies the runtime platform, identity, networking, monitoring, and GitOps reconciliation. Red Hat Connectivity Link provides the gateway and policy layer used in the MaaS path.

The local models run on the GPU infrastructure from Step 02. vLLM serves the models with an OpenAI-compatible API surface. The upstream Open Data Hub models-as-a-service controller supplies the `ExternalModel`, `MaaSModelRef`, `MaaSAuthPolicy`, and `MaaSSubscription` resources used in this demo. Gateway API, Kuadrant, and Authorino enforce routing, authorization, rate limiting, and token limits at the API boundary.

The workshop uses this hybrid MaaS implementation because external model support is evolving across the OpenShift AI 3.3 and 3.4 timeframe. The RHOAI dashboard MaaS experience remains active, while the upstream MaaS controller provides the external model and subscription capabilities required here.

The MCP layer follows the same pattern: the base deployment registers a read-only Kubernetes MCP server for OpenShift context in GenAI Playground, while Slack and BrightData remain optional Kustomize components that require separate credentials and approval.

## Red Hat Products Used

- **Red Hat OpenShift AI** provides the GenAI Studio dashboard experience, model serving integration, and MaaS user experience.
- **Models-as-a-Service in OpenShift AI** is the model access pattern demonstrated by this step.
- **Red Hat Connectivity Link** provides the gateway and policy layer used to enforce model access and token rate limits.
- **Red Hat OpenShift GitOps** reconciles the MaaS resources, gateway configuration, model definitions, and policy resources.
- **Red Hat OpenShift** provides the runtime platform, identity, networking, routes, and monitoring foundation.

## Open Source Projects To Know

- [Open Data Hub models-as-a-service](https://github.com/opendatahub-io/models-as-a-service) provides the upstream MaaS controller and CRDs used in this workshop.
- [vLLM](https://docs.vllm.ai/) serves local LLMs efficiently and exposes OpenAI-compatible APIs.
- [llm-d](https://llm-d.ai/) is an open source effort for distributed LLM serving on Kubernetes.
- [Gateway API](https://gateway-api.sigs.k8s.io/) provides Kubernetes-native gateway resources.
- [Kuadrant](https://kuadrant.io/) and [Authorino](https://www.authorino.io/) provide policy and authorization patterns for APIs.

## Trust Boundaries

This step should be explained carefully:

- A **private local model** keeps inference on the OpenShift platform. This is the preferred path for sensitive source code, regulated workloads, and network-restricted environments.
- A **governed external model** still sends prompts to the external provider. MaaS controls access and visibility, but it does not make that processing private.
- **External provider credentials** are a separate trust boundary. The committed OpenAI Secret is a placeholder and must be replaced with an approved key before external inference is usable.
- **MCP servers** can introduce additional data movement. The included OpenShift MCP server is deployed read-only; optional Slack and BrightData MCP servers require separate credentials and should be enabled only when those services are approved.
- A **single access layer** lets platform teams publish both options with clear policy boundaries.

That distinction is especially important for regulated industries. The platform gives teams a way to separate workloads by data sensitivity instead of forcing every use case into the same model path.

## Why This Is Worth Knowing

MaaS turns model serving into a platform capability. Without it, every team would need to manage model endpoints, provider credentials, quotas, and integrations on its own. With it, the platform team can become the internal AI provider.

This pattern supports:

- Private AI for sensitive software development.
- Approved external AI where policy allows.
- Consistent API consumption across tools.
- Centralized key management and rate limiting.
- Usage visibility for cost and capacity management.
- Model backend changes without rewriting every consuming workflow.

## Where This Fits In The Full Platform

| Consumer | How it uses Step 03 |
|----------|---------------------|
| RHOAI Playground | Tests available models before integration |
| Dev Spaces | Continue and OpenCode call MaaS endpoints |
| MTA Developer Lightspeed | The LLM proxy calls the MaaS-backed Nemotron endpoint |
| Developer Hub | Future catalog entities can expose model and API choices |

## Deploy And Validate

Operational commands are kept here for workshop operators.

```bash
./steps/step-03-llm-serving-maas/deploy.sh
./steps/step-03-llm-serving-maas/validate.sh
```

Manifests: [`gitops/step-03-llm-serving-maas/base/`](../../gitops/step-03-llm-serving-maas/base/)

## References

- [MaaS code assistant quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- [What is Model-as-a-Service?](https://www.redhat.com/en/topics/ai/what-is-models-as-a-service)
- [Red Hat OpenShift AI](https://www.redhat.com/en/products/ai/openshift-ai)
- [Red Hat Connectivity Link](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/)
- [opendatahub-io/models-as-a-service](https://github.com/opendatahub-io/models-as-a-service)
- [ExternalModel setup guide](https://github.com/opendatahub-io/models-as-a-service/blob/main/docs/content/install/external-model-setup.md)

## Next Step

[Step 04: Dev Spaces and AI Code Assistant](../step-04-devspaces/README.md) shows how developers consume the governed model endpoints from a controlled workspace.
