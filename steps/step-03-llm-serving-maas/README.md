# Step 03: LLM Serving with Models-as-a-Service
**"Governed model access at enterprise scale"** — Deploy NVIDIA models on vLLM and expose them through Models-as-a-Service with tier-based access control, rate limiting, and usage telemetry.

## Overview

Deploying a model is only the beginning. Teams need governed, measurable access to LLMs — not open endpoints that anyone can saturate. This step deploys two models on vLLM (OpenAI gpt-oss-20b and NVIDIA Nemotron 3 Nano 30B) and wraps them with **Models-as-a-Service (MaaS)**, a Technology Preview capability in RHOAI 3.4 that provides centralized model access governance.

MaaS lets platform administrators define who can access which models, how much they can consume, and track all usage for capacity planning and chargeback. Access is controlled through tier-based groups (free, premium, enterprise) with per-tier request and token rate limits enforced by Red Hat Connectivity Link.

### What Gets Deployed

```text
LLM Serving + MaaS
├── Models (namespace: maas)
│   ├── gpt-oss-20b              → All tiers (free, premium, enterprise)
│   └── nemotron-3-nano-30b-a3b  → Premium + Enterprise only
├── MaaS Governance
│   ├── Tier-to-Group Mapping    → free/premium/enterprise → OCP groups
│   ├── RateLimitPolicy          → Request rate limits per tier
│   ├── TokenRateLimitPolicy     → Token rate limits per tier
│   └── TelemetryPolicy          → Usage metrics to Prometheus
└── MaaS API (Developer Preview) → Centralized model access gateway
```

| Tier | Request Limit | Token Limit | Models Available | Users |
|------|--------------|-------------|-----------------|-------|
| Free | 5 / 2min | 100 / 1min | gpt-oss-20b | (unassigned) |
| Premium | 20 / 2min | 10,000 / 1min | gpt-oss-20b, Nemotron | user1-user5 |
| Enterprise | 50 / 2min | 20,000 / 1min | gpt-oss-20b, Nemotron | admin |

Manifests: [`gitops/step-03-llm-serving-maas/base/`](../../gitops/step-03-llm-serving-maas/base/)

<details>
<summary>Deploy</summary>

```bash
./steps/step-03-llm-serving-maas/deploy.sh
./steps/step-03-llm-serving-maas/validate.sh
```

</details>

## The Demo

> In this demo, we show how platform administrators govern model access and how developers discover and use models through the RHOAI dashboard and MaaS.

### Model Discovery in GenAI Studio

> Developers start in the OpenShift AI dashboard, browsing available AI assets. Models deployed through MaaS appear alongside their access tier and endpoint information.

1. Log in to the RHOAI Dashboard as `admin`
2. Navigate to **GenAI Studio** -> **AI Available Assets**
3. Locate the **NVIDIA Nemotron 3 Nano 30B** model

**Expect:** Both deployed models visible with their endpoint URLs and tier assignments.

> This is self-service model discovery. Developers find what they need without asking platform teams — models, endpoints, and access policies are all visible in one place.

### Testing in the Playground

> Before integrating a model into a coding workflow, the developer validates it in the built-in Playground.

1. Click on the Nemotron model and select **Open in Playground**
2. Enter a test prompt: "Write a Python function that reads a CSV file and returns a summary"
3. Observe the response quality, latency, and token usage

**Expect:** The model responds with functional Python code. Response metadata shows latency and token counts.

> The Playground lets developers validate model behavior before committing to an integration. No API keys, no external tools — just the dashboard.

### Tier-Based Access Control

> Platform administrators define who gets access to which models and how much they can consume.

1. Switch to the admin perspective
2. Navigate to **Settings** -> **Tiers**
3. Review the three tiers: Free (5 req/2min), Premium (20 req/2min), Enterprise (50 req/2min)

**Expect:** Three tiers with distinct rate limits and model access policies.

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

- [Governing LLM access with Models-as-a-Service](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/govern_llm_access_with_models-as-a-service/index)
- [MaaS Code Assistant Quickstart](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)
- [Deploying models on RHOAI](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/deploying_models/)
- [Red Hat Connectivity Link](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/)

## Next Steps

- **Step 04**: [Observability & Governance Dashboard](../step-04-observability/README.md) — Grafana dashboards for MaaS usage monitoring
