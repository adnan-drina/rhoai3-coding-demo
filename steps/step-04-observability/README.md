# Step 04: Observability and Governance Dashboard
**"See what AI consumes"** — Deploy Grafana dashboards that give platform administrators visibility into model usage, tier consumption, rate limiting, and inference performance.

## Overview

Deploying models and governing access is only valuable if you can see what is happening. This step deploys a Grafana-based observability stack that surfaces MaaS usage metrics from the cluster's Prometheus monitoring. Administrators can track requests per tier, token consumption, rate limit rejections, and inference latency — supporting capacity planning, cost allocation, and operational awareness.

### What Gets Deployed

```text
Observability Stack
├── Grafana Operator          → Manages Grafana instances and dashboards
├── Grafana Instance          → Web UI for dashboards (grafana namespace)
├── GrafanaDatasource         → Connected to User Workload Monitoring (Thanos)
├── GrafanaDashboard          → MaaS Usage Dashboard (tier/model/latency panels)
└── ServiceMonitor            → Scrapes vLLM inference metrics from maas namespace
```

Manifests: [`gitops/step-04-observability/base/`](../../gitops/step-04-observability/base/)

<details>
<summary>Deploy</summary>

```bash
./steps/step-04-observability/deploy.sh
./steps/step-04-observability/validate.sh
```

</details>

## The Demo

> In this demo, the platform administrator reviews MaaS usage patterns through a Grafana dashboard connected to the cluster's monitoring stack.

### MaaS Usage Dashboard

> After models have been serving requests across tiers, the administrator opens Grafana to review consumption.

1. Open the Grafana URL printed by `deploy.sh`
2. Log in as `admin` / `redhat123`
3. Navigate to **Dashboards** -> **MaaS Usage Dashboard**

**Expect:** Six panels showing: Total Requests by Tier, Token Usage by Tier, Rate Limit Rejections, Active Models, Requests by Model, and Inference Latency (p95).

> Platform teams can see exactly who is consuming what. This supports internal chargeback, capacity forecasting, and early detection of tier exhaustion. No custom instrumentation needed — MaaS telemetry flows to Prometheus automatically.

## Key Takeaways

**For business stakeholders:**

- Track AI consumption across teams for cost allocation and budgeting
- Detect and address capacity bottlenecks before they impact developers
- Align AI infrastructure spending with actual usage patterns

**For technical teams:**

- Zero-config metrics via TelemetryPolicy and ServiceMonitor
- Grafana connected to User Workload Monitoring — no separate Prometheus needed
- Dashboards are GitOps-managed and reproducible

## References

- [Managing observability in RHOAI](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-observability_managing-rhoai)
- [Grafana Operator](https://grafana.github.io/grafana-operator/)
- [OCP 4.20 Monitoring](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/monitoring/)

## Next Steps

- **Step 05**: [Dev Spaces & AI Code Assistant](../step-05-devspaces/README.md) — OpenShift Dev Spaces with Continue extension for AI-assisted coding
