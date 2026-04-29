# Step 03: LLM Serving with Models-as-a-Service
**"Governed model access at enterprise scale"** — Deploy NVIDIA models on vLLM and expose them through Models-as-a-Service with tier-based access control, rate limiting, and usage telemetry.

## Overview

Deploying a model is only the beginning. Teams need governed, measurable access to LLMs — not open endpoints that anyone can saturate. This step deploys two local models on vLLM (OpenAI gpt-oss-20b and NVIDIA Nemotron 3 Nano 30B) and exposes them through **Models-as-a-Service (MaaS)** using the RHOAI 3.4 operator's native MaaS support.

The RHOAI 3.4 operator manages the entire MaaS stack: `maas-api`, tier ConfigMap, RBAC, and AuthPolicies. Models opt in to MaaS by referencing the `maas-default-gateway` and adding the `alpha.maas.opendatahub.io/tiers` annotation — the operator auto-creates the necessary RBAC resources per tier. Rate limits and tier assignments are managed through the RHOAI dashboard UI.

### What Gets Deployed

```text
LLM Serving + MaaS
├── MaaS Prerequisites
│   ├── LeaderWorkerSet Operator   → Distributed inference orchestration
│   ├── Red Hat Connectivity Link  → Gateway policies, rate limiting
│   ├── CloudNative PG Operator    → MaaS API database (operator-managed)
│   ├── GatewayClass + Gateway     → MaaS traffic routing (HTTP + HTTPS/TLS)
│   └── Kuadrant                   → Authentication, authorization enforcement
├── Operator-Managed MaaS (redhat-ods-applications)
│   ├── maas-api                   → Model discovery, API key generation, tier lookup
│   ├── tier-to-group-mapping      → Auto-created ConfigMap mapping tiers to groups
│   └── AuthPolicies               → Auto-created per Gateway and MaaS API routes
├── Models (namespace: maas)
│   ├── gpt-oss-20b               → Local GPU model (LLMInferenceService, all tiers)
│   └── nemotron-3-nano-30b-a3b   → Local GPU model (LLMInferenceService, premium+enterprise)
├── MCP Servers (namespace: coding-assistant)
│   ├── OpenShift MCP              → Read-only cluster queries (pods, logs, events)
│   ├── Slack MCP                  → Post messages to Slack channels
│   └── BrightData Web MCP        → Browse and search the public web
├── Model Registration             → Seed Job registers models in Model Registry
├── In-Cluster Jobs
│   ├── patch-gateway-hostname    → Cluster-specific Gateway hostname + TLS cert
│   └── configure-grafana-sa      → Grafana ServiceAccount token
└── Observability
    ├── Grafana Operator + Instance
    ├── ServiceMonitor             → Limitador metrics for rate limit monitoring
    └── MaaS Usage Dashboard
```

| Model | Type | MaaS Endpoint | Tier Access |
|-------|------|---------------|-------------|
| gpt-oss-20b | Local (GPU, vLLM) | `https://maas.<cluster>/llm/gpt-oss-20b/v1/chat/completions` | free, premium, enterprise |
| nemotron-3-nano-30b-a3b | Local (GPU, vLLM) | `https://maas.<cluster>/llm/nemotron-3-nano-30b-a3b/v1/chat/completions` | premium, enterprise |

Access is controlled via the `alpha.maas.opendatahub.io/tiers` annotation on each `LLMInferenceService`. The operator auto-creates Roles and RoleBindings per tier. Rate limits are configured through the dashboard's tier management UI.

Manifests: [`gitops/step-03-llm-serving-maas/base/`](../../gitops/step-03-llm-serving-maas/base/)

<details>
<summary>Deploy</summary>

```bash
./steps/step-03-llm-serving-maas/deploy.sh
./steps/step-03-llm-serving-maas/validate.sh
```

The `deploy.sh` applies the ArgoCD Application. All resources including operators, models, and Jobs are managed by ArgoCD via sync waves.

</details>

## The Demo

> In this demo, we show how platform administrators govern model access and how developers discover and use models through the RHOAI dashboard and MaaS.

### Model Discovery in GenAI Studio

> Developers start in the OpenShift AI dashboard, browsing available AI assets.

1. Log in to the RHOAI Dashboard as `ai-admin` (via `demo-htpasswd`)
2. Navigate to **GenAI Studio > AI asset endpoints**
3. Select the **maas** project from the project dropdown
4. The **Models as a service** tab shows models with MaaS badges, status, and tier information

**Expect:** Both models visible with **Ready** status.

### Viewing Endpoints and Generating API Keys

> The developer selects a MaaS model to get connection details.

1. Click **View** on any model in the Models as a service tab
2. The endpoint details show the MaaS route URL (e.g., `https://maas.<cluster>/llm/gpt-oss-20b/v1`)
3. Click **Generate API Key** to create an authentication token
4. Copy the endpoint URL and key for use in applications

**Expect:** External API endpoint with a working API key generator.

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

### Tier-Based Access Control

> Platform administrators define service tiers with different rate limits and model access.

1. In the RHOAI Dashboard, navigate to **Gen AI Studio > Tiers**
2. View the default tiers: Free, Premium, Enterprise — each with assigned groups and rate limits
3. Verify tier information: click **Tier information** on the MaaS tab to see your assigned tier

```bash
# Verify tier RBAC was auto-created by the tiers annotation
oc get rolebindings -n maas | grep gpt-oss-20b
oc get rolebindings -n maas | grep nemotron

# Test model access with generated API key
export MAAS_TOKEN="<your_generated_token>"
export CLUSTER_DOMAIN=$(oc get ingresses.config.openshift.io cluster -o jsonpath={.spec.domain})
curl -X GET "https://maas.${CLUSTER_DOMAIN}/v1/models" \
  -H "Authorization: Bearer ${MAAS_TOKEN}"
```

**Expect:** RoleBindings for each tier that has access. `/v1/models` returns both models with `ready: true`.

## Key Takeaways

**For business stakeholders:**

- Govern AI model access with tier-based policies that align with organizational roles
- Track usage for capacity planning and internal cost allocation
- Control which teams access which models — not all models are for everyone

**For technical teams:**

- Deploy models once, expose through managed API endpoints with per-tier rate limits
- Red Hat Connectivity Link enforces rate limits at the gateway level — no application changes needed
- Models opt in to MaaS with a single annotation — the operator handles RBAC and policy creation

## References

- [RHOAI 3.4 MaaS Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service_maas) — deploy and manage MaaS
- [MaaS User Guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/govern_llm_access_with_models-as-a-service/use-models-as-a-service_maas) — access models, generate tokens, playground
- [ODH MaaS Model Setup](https://opendatahub-io.github.io/models-as-a-service/0.0.1/configuration-and-management/model-setup/) — upstream LLMInferenceService configuration
- [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant) — the public quickstart this demo is based on
- [Red Hat Connectivity Link](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/)

## Next Steps

- **Step 04**: [Dev Spaces & AI Code Assistant](../step-04-devspaces/README.md) — OpenShift Dev Spaces with Continue extension for AI-assisted coding
