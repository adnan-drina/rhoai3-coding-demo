# Step 03: LLM Serving with Models-as-a-Service
**"Governed model access at enterprise scale"** — Deploy NVIDIA models on vLLM and expose them through Models-as-a-Service with tier-based access control, rate limiting, and usage telemetry.

## Overview

Deploying a model is only the beginning. Teams need governed, measurable access to LLMs — not open endpoints that anyone can saturate. This step deploys two local models on vLLM (OpenAI gpt-oss-20b and NVIDIA Nemotron 3 Nano 30B) and an **external model** (OpenAI GPT-4o via the `ExternalModel` CRD), exposing all through **Models-as-a-Service (MaaS)**.

The MaaS layer uses a **hybrid architecture**: the RHOAI 3.3 operator's `modelsAsService: Managed` keeps the dashboard MaaS tab active, while the upstream [ODH maas-controller](https://github.com/opendatahub-io/models-as-a-service) (`quay.io/opendatahub/maas-controller:latest`) runs alongside to provide `ExternalModel`, `MaaSAuthPolicy`, `MaaSSubscription`, and `MaaSModelRef` CRDs. An `upstream-maas-api` deployment (`quay.io/opendatahub/maas-api:latest`) serves all API traffic through the `maas-api` Service, backed by PostgreSQL for API key storage.

Access is controlled through `MaaSAuthPolicy` (who can access which models) and `MaaSSubscription` (per-model token rate limits) CRDs, enforced by Red Hat Connectivity Link at the MaaS Gateway. API keys use the `sk-oai-*` hash-based format. See [BACKLOG.md](../../BACKLOG.md) for coexistence workarounds.

### What Gets Deployed

```text
LLM Serving + MaaS
├── MaaS Prerequisites
│   ├── LeaderWorkerSet Operator   → Distributed inference orchestration
│   ├── Red Hat Connectivity Link  → Gateway policies, rate limiting
│   ├── CloudNative PG Operator    → MaaS API database (operator-managed)
│   ├── GatewayClass + Gateway     → MaaS traffic routing (HTTP + HTTPS/TLS)
│   └── Kuadrant + Authorino       → Authentication, authorization, SSL trust
├── Upstream MaaS Controller (redhat-ods-applications)
│   ├── maas-controller            → Manages MaaSModelRef, MaaSAuthPolicy, MaaSSubscription, ExternalModel CRDs
│   ├── upstream-maas-api          → quay.io/opendatahub/maas-api:latest (serves /maas-api/* traffic)
│   ├── PostgreSQL                 → API key storage (hash-based sk-oai-* keys)
│   ├── payload-processing         → ExternalModel credential injection (IPP/BBR plugin)
│   └── 5 CRDs                    → ExternalModel, MaaSModelRef, MaaSAuthPolicy, MaaSSubscription, Tenant
├── Models (namespace: maas)
│   ├── gpt-oss-20b               → Local GPU model (LLMInferenceService + MaaSModelRef)
│   ├── nemotron-3-nano-30b-a3b   → Local GPU model (LLMInferenceService + MaaSModelRef)
│   └── openai-gpt-4o             → External model (ExternalModel + MaaSModelRef)
├── MaaS Governance (namespace: models-as-a-service)
│   ├── MaaSAuthPolicy            → Per-model access control (groups)
│   ├── MaaSSubscription          → Per-model token rate limits
│   └── Per-route policies        → Auto-created AuthPolicies + TokenRateLimitPolicies in maas namespace
├── MCP Servers (namespace: coding-assistant)
│   ├── OpenShift MCP              → Read-only cluster queries (pods, logs, events)
│   ├── Slack MCP                  → Post messages to Slack channels
│   └── BrightData Web MCP        → Browse and search the public web
├── Model Registration             → Seed Job registers models in Model Registry
├── In-Cluster Jobs
│   ├── configure-kuadrant        → Authorino SSL + AuthPolicy patches
│   ├── patch-gateway-hostname    → Cluster-specific Gateway hostname + TLS cert
│   └── configure-grafana-sa      → Grafana ServiceAccount token
└── Observability
    ├── Grafana Operator + Instance
    ├── ServiceMonitor             → Limitador metrics for rate limit monitoring
    └── MaaS Usage Dashboard
```

| Model | Type | Endpoint | Access |
|-------|------|----------|--------|
| gpt-oss-20b | Local (GPU, vLLM) | `/maas/gpt-oss-20b/v1/chat/completions` | `system:authenticated` |
| nemotron-3-nano-30b-a3b | Local (GPU, vLLM) | `/maas/nemotron-3-nano-30b-a3b/v1/chat/completions` | `system:authenticated` |
| openai-gpt-4o | External (OpenAI API) | `/maas/openai-gpt-4o/v1/chat/completions` | `system:authenticated` |

Access is controlled via `MaaSAuthPolicy` CRDs in the `models-as-a-service` namespace. Token rate limits (50,000 tokens/hour per model) are defined in `MaaSSubscription` CRDs. The per-route `AuthPolicy` and `TokenRateLimitPolicy` resources in the `maas` namespace are auto-created by the `maas-controller`.

Manifests: [`gitops/step-03-llm-serving-maas/base/`](../../gitops/step-03-llm-serving-maas/base/)

<details>
<summary>Deploy</summary>

```bash
./steps/step-03-llm-serving-maas/deploy.sh
./steps/step-03-llm-serving-maas/validate.sh
```

The `deploy.sh` applies the ArgoCD Application. All resources including operators, models, policies, and Jobs are managed by ArgoCD via sync waves.

</details>

## The Demo

> In this demo, we show how platform administrators govern model access and how developers discover and use models through the RHOAI dashboard and MaaS.

### Model Discovery in GenAI Studio

> Developers start in the OpenShift AI dashboard, browsing available AI assets.

1. Log in to the RHOAI Dashboard as `ai-admin` (via `demo-htpasswd`)
2. Navigate to **GenAI Studio > AI asset endpoints**
3. Select the **maas** project from the project dropdown
4. The **Models** tab shows available models with their status and playground access
5. The **Models as a service** tab shows models with MaaS badges, external endpoints, and tier information

**Expect:** Both models visible with **Active** status in both tabs.

### Viewing Endpoints and Generating API Keys

> The developer selects a MaaS model to get connection details.

1. Click **View** on any model in the Models as a service tab
2. The endpoint details show the external API endpoint URL (e.g., `https://maas.<cluster>/maas/openai-gpt-4o`)
3. Click **Generate API key** to create an `sk-oai-*` format API key
4. Copy the endpoint URL and key for use in applications (keys are stored in PostgreSQL, not as ServiceAccount tokens)

**Expect:** External API endpoint with a working API key generator. Keys work for both local GPU models and the external OpenAI model.

### Testing in the Playground

> Before integrating a model into a coding workflow, the developer validates it in the built-in Playground.

**Playground Prerequisites** (already satisfied by this demo):
- `genAiStudio: true` in OdhDashboardConfig (set in Step 01)
- Llama Stack Operator set to `Managed` in the DSC (set in Step 01)
- User is a member of a configured admin or user group (Auth resource in Step 01)
- A model is deployed and available as an AI asset endpoint in the project

1. Click **Add to playground** on the Nemotron model
2. Select the model in the **Configure playground** dialog and click **Create**
3. Enter a test prompt: "Write a Python function that reads a CSV file and returns a summary"
4. Observe the response quality, latency, and token usage

**Expect:** The model responds with functional Python code. Response metadata shows latency and token counts.

### Access Control via MaaS CRDs

> Platform administrators define who gets access to which models and how much they can consume.

1. `MaaSAuthPolicy` CRDs in `models-as-a-service` namespace define which groups can access which models
2. `MaaSSubscription` CRDs define per-model token rate limits per group
3. The `maas-controller` auto-creates per-route `AuthPolicy` and `TokenRateLimitPolicy` resources in the `maas` namespace
4. `TelemetryPolicy` sends usage metrics to Prometheus

```bash
# View access policies
oc get maasauthpolicy -n models-as-a-service
# View subscriptions
oc get maassubscription -n models-as-a-service
# View auto-created per-route policies
oc get authpolicy,tokenratelimitpolicy -n maas
```

**Expect:** `MaaSAuthPolicy` and `MaaSSubscription` in `Active` phase. Per-route policies auto-created for all 3 models.

## Key Takeaways

**For business stakeholders:**

- Govern AI model access with tier-based policies that align with organizational roles
- Track usage for capacity planning and internal cost allocation
- Control which teams access which models — not all models are for everyone

**For technical teams:**

- Deploy models once, expose through managed API endpoints with per-tier rate limits
- Red Hat Connectivity Link enforces rate limits at the gateway level — no application changes needed
- Usage telemetry flows to Prometheus automatically via TelemetryPolicy

## References

- [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant) — the public quickstart this step is based on
- [rh-ai-quickstart/maas-code-assistant](https://github.com/rh-ai-quickstart/maas-code-assistant) — upstream quickstart source
- [opendatahub-io/models-as-a-service](https://github.com/opendatahub-io/models-as-a-service) — upstream MaaS controller with ExternalModel CRD
- [ExternalModel setup guide](https://github.com/opendatahub-io/models-as-a-service/blob/main/docs/content/install/external-model-setup.md) — upstream docs for registering external providers
- [RHOAI 3.3 Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/)
- [Red Hat Connectivity Link](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/)

## Next Steps

- **Step 04**: [Dev Spaces & AI Code Assistant](../step-04-devspaces/README.md) — OpenShift Dev Spaces with Continue extension for AI-assisted coding
