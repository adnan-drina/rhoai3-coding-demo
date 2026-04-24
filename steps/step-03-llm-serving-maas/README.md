# Step 03: LLM Serving with Models-as-a-Service
**"Governed model access at enterprise scale"** — Deploy NVIDIA models on vLLM and expose them through Models-as-a-Service with tier-based access control, rate limiting, and usage telemetry.

## Overview

Deploying a model is only the beginning. Teams need governed, measurable access to LLMs — not open endpoints that anyone can saturate. This step deploys two models on vLLM (OpenAI gpt-oss-20b and NVIDIA Nemotron 3 Nano 30B) and wraps them with **Models-as-a-Service (MaaS)**, following the [public MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant) dev-preview approach for RHOAI 3.3.

MaaS lets platform administrators define who can access which models, how much they can consume, and track all usage for capacity planning and chargeback. Access is controlled through tier-based groups (free, premium, enterprise) with per-tier request and token rate limits enforced by Red Hat Connectivity Link.

> **Dev-preview note:** RHOAI 3.3 does not include MaaS natively. This step deploys a dev-preview `maas-api` from [opendatahub-io/models-as-a-service](https://github.com/opendatahub-io/models-as-a-service) using Kustomize. When RHOAI 3.4 GA ships with native MaaS support, these community workarounds can be reverted. See [BACKLOG.md](../../BACKLOG.md) for details.

### What Gets Deployed

```text
LLM Serving + MaaS
├── MaaS Prerequisites
│   ├── LeaderWorkerSet Operator  → Distributed inference orchestration
│   ├── Red Hat Connectivity Link → Gateway policies, rate limiting
│   ├── GatewayClass + Gateway    → MaaS traffic routing (HTTP + HTTPS/TLS)
│   └── Kuadrant + Authorino      → Authentication, authorization, SSL trust
├── Models (namespace: maas)
│   ├── gpt-oss-20b              → All tiers (free, premium, enterprise)
│   ├── nemotron-3-nano-30b-a3b  → Premium + Enterprise only
│   └── Per-model RBAC           → Tier ServiceAccounts → LLMInferenceService access
├── MaaS API (dev-preview)
│   ├── maas-api deployment      → quay.io/opendatahub/maas-api:latest-0681979
│   ├── PostgreSQL (CNPG)        → Included in remote kustomize base
│   └── HTTPRoute + AuthPolicy   → Routed through MaaS Gateway
├── MaaS Governance
│   ├── Tier Groups              → tier-free-users, tier-premium-users, tier-enterprise-users
│   ├── RateLimitPolicy          → Request rate limits per tier
│   ├── TokenRateLimitPolicy     → Token rate limits per tier
│   └── TelemetryPolicy          → Usage metrics to Prometheus
├── In-Cluster Jobs
│   ├── configure-kuadrant       → Authorino SSL env vars (SSL_CERT_FILE, REQUESTS_CA_BUNDLE)
│   ├── patch-gateway-hostname   → Cluster-specific Gateway hostname + TLS cert
│   └── configure-grafana-sa     → Grafana ServiceAccount token
└── Observability
    ├── Grafana Operator + Instance
    ├── ServiceMonitor            → Limitador metrics for rate limit monitoring
    └── MaaS Usage Dashboard
```

| Tier | Request Limit | Token Limit | Models Available | Groups | Users |
|------|--------------|-------------|-----------------|--------|-------|
| Free | 5 / 2min | 100 / 1min | gpt-oss-20b | `tier-free-users` | (none by default) |
| Premium | 20 / 2min | 10,000 / 1min | gpt-oss-20b, Nemotron | `tier-premium-users` | ai-developer |
| Enterprise | 50 / 2min | 20,000 / 1min | gpt-oss-20b, Nemotron | `tier-enterprise-users` | ai-admin |

Tier groups are defined in `gitops/step-03-llm-serving-maas/base/governance/maas-groups.yaml`. Models declare their tier membership via the `alpha.maas.opendatahub.io/tiers` annotation on `LLMInferenceService`.

Manifests: [`gitops/step-03-llm-serving-maas/base/`](../../gitops/step-03-llm-serving-maas/base/)

<details>
<summary>Deploy</summary>

```bash
./steps/step-03-llm-serving-maas/deploy.sh
./steps/step-03-llm-serving-maas/validate.sh
```

The `deploy.sh` script:
1. Applies the ArgoCD Application for all GitOps-managed resources
2. Separately applies the dev-preview `maas-api` via `oc apply -k gitops/step-03-llm-serving-maas/base/maas-api/` (not managed by ArgoCD because the remote kustomize base references an external repo)

</details>

## The Demo

> In this demo, we show how platform administrators govern model access and how developers discover and use models through the RHOAI dashboard and MaaS.

### Model Discovery in GenAI Studio

> Developers start in the OpenShift AI dashboard, browsing available AI assets. Models deployed through the MaaS dev-preview API appear with MaaS source badges.

1. Log in to the RHOAI Dashboard as `ai-admin` (via `demo-htpasswd`)
2. Navigate to **GenAI Studio > AI asset endpoints**
3. Select the **maas** project from the project dropdown
4. The **Models** tab shows available models with their source type (MaaS), status, and playground access

**Expect:** Models visible with **MaaS** source badge and **Active** status.

> This is self-service model discovery. Developers find what they need without asking platform teams — models, endpoints, and access policies are all visible in one place.

### Viewing Endpoints and Generating API Tokens

> The developer selects a MaaS model to get connection details for their application.

1. Click **View** on the **gpt-oss-20b** (MaaS source) model
2. The **Endpoints** modal shows the external API endpoint URL
3. Click **Generate API token** to create an authentication token
4. Copy the endpoint URL and token for use in applications

**Expect:** External API endpoint in the format `https://maas.<cluster-domain>/maas-api/` with a working token generator.

> Each model has a unique endpoint URL and supports OpenAI-compatible API calls. API tokens are managed through the dev-preview MaaS API.

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

> The Playground lets developers validate model behavior before committing to an integration. No API keys, no external tools — just the dashboard.

### Tier-Based Access Control

> Platform administrators define who gets access to which models and how much they can consume. Tiers are enforced at the Gateway level through Kuadrant policies.

1. Tier definitions are in `gitops/step-03-llm-serving-maas/base/governance/`
2. `RateLimitPolicy` controls request rate per tier
3. `TokenRateLimitPolicy` controls token consumption per tier
4. `TelemetryPolicy` sends usage metrics to Prometheus

**Expect:** Three tiers (free, premium, enterprise) with distinct rate limits enforced by Red Hat Connectivity Link at the MaaS Gateway.

> Models-as-a-Service gives platform teams centralized governance without building custom infrastructure. Rate limits, quotas, and access policies are defined once and enforced consistently across all consumers.

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
- [opendatahub-io/models-as-a-service](https://github.com/opendatahub-io/models-as-a-service) — MaaS API dev-preview source
- [RHOAI 3.3 Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/)
- [Deploying models on RHOAI](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.3/html/deploying_models/)
- [Red Hat Connectivity Link](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/)

## Next Steps

- **Step 04**: [Dev Spaces & AI Code Assistant](../step-04-devspaces/README.md) — OpenShift Dev Spaces with Continue extension for AI-assisted coding
