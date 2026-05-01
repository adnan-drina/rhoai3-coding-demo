# Step 03: Governed Models-as-a-Service

## Why This Matters

Deploying a model is not the same thing as making AI usable in an enterprise. A single model endpoint might work for a proof of concept, but production teams quickly need answers to harder questions:

- Who is allowed to use the model?
- Which workloads are allowed to use external providers?
- How do we prevent one team from consuming all capacity?
- How do developers discover the right endpoint?
- How do we measure usage for capacity planning, showback, or chargeback?
- How do we switch model backends without rewriting every tool?

Models-as-a-Service is the platform answer. It makes models available as shared API services while keeping access, policy, rate limits, keys, and telemetry under central control.

This step is the heart of the workshop. Every later developer experience, from coding assistants to MTA modernization, depends on the governed model access layer created here.

## What This Step Adds

Step 03 publishes four models through one MaaS pattern:

| Model | Backend | Trust boundary | Why it is included |
|-------|---------|----------------|--------------------|
| `nemotron-3-nano-30b-a3b` | Local vLLM on OpenShift | Private platform boundary | Primary private coding and modernization model |
| `gpt-oss-20b` | Local vLLM on OpenShift | Private platform boundary | Open model alternative for private workloads |
| `gpt-4o` | External OpenAI provider through MaaS | Governed external processing | High-intelligence external model path |
| `gpt-4o-mini` | External OpenAI provider through MaaS | Governed external processing | Fast, lower-cost external model path |

The models are intentionally different. The lesson is not that one model is best. The lesson is that an enterprise platform should let teams choose the right model for the workload while enforcing policy at the access layer.

The external OpenAI model resources are included with a placeholder `openai-api-key` Secret. They show how the governed external model path is wired, but external inference requires an operator to replace the placeholder with an approved provider credential.

## What To Notice In The Demo

When presenting this step, focus on three things.

First, show **model discovery** in the RHOAI dashboard. Developers should be able to find model endpoints without understanding how the backend is deployed.

Second, show **one API style**. Local and external models use the same OpenAI-compatible `/v1/chat/completions` pattern and `sk-oai-*` MaaS keys. That is what makes the later Dev Spaces, OpenCode, Continue, and MTA integrations simple.

Third, show **governance resources**. `MaaSAuthPolicy` and `MaaSSubscription` demonstrate that model access is not unmanaged. The platform team controls who can use the models and how much they can consume.

The key message: developers get simple access; platform teams keep control.

## How Red Hat And Open Source Make It Work

```text
Governed MaaS layer
+-- Local model serving
|   +-- nemotron-3-nano-30b-a3b
|   +-- gpt-oss-20b
+-- External model registration
|   +-- gpt-4o
|   +-- gpt-4o-mini
+-- MaaS control plane
|   +-- maas-controller
|   +-- maas-api
|   +-- MaaSModelRef
|   +-- ExternalModel
|   +-- MaaSAuthPolicy
|   +-- MaaSSubscription
+-- API gateway and policy enforcement
|   +-- Red Hat Connectivity Link
|   +-- Gateway API
|   +-- Kuadrant
|   +-- Authorino
+-- Observability
    +-- telemetry policies
    +-- Prometheus metrics
    +-- Grafana dashboards
+-- MCP integration
    +-- read-only OpenShift MCP server
    +-- RHOAI GenAI Playground MCP discovery ConfigMap
    +-- optional Slack and BrightData MCP components
```

The local models run on the GPU infrastructure prepared in Step 02. vLLM provides efficient model inference. MaaS publishes the models as reusable endpoints. Red Hat Connectivity Link, Gateway API, Kuadrant, and Authorino provide the gateway and policy enforcement layer.

The workshop uses a hybrid MaaS implementation because external model support is evolving across the RHOAI 3.3 and 3.4 timeframe. The RHOAI dashboard MaaS experience remains active, while the upstream ODH MaaS controller provides the `ExternalModel`, `MaaSModelRef`, `MaaSAuthPolicy`, and `MaaSSubscription` capabilities required for this demo.

The base deployment also registers a read-only Kubernetes MCP server for OpenShift cluster context in the GenAI Playground. Slack and BrightData MCP components are present as optional Kustomize components and are not enabled unless their credential Secrets are created and the components are included.

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
