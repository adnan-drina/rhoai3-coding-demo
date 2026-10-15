---
name: rhcl-observability
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhcl
  docs-version: "1.4"
  skill-group: "Connectivity Link"
description: >
  Use when working on Connectivity Link observability in this demo: the
  Kuadrant observability switch and the ServiceMonitor/PodMonitor objects it
  creates, Limitador and Authorino metrics behind the MaaS usage dashboards,
  gateway access logs with request correlation, control- and data-plane
  tracing, the Connectivity Link Grafana dashboards, and MCP gateway audit
  trails. Do NOT use for OpenShift monitoring, COO or Perses in general (use
  ocp-observability), OpenTelemetry collector setup (use ocp-opentelemetry),
  Tempo (use ocp-distributed-tracing), or MaaS dashboards' RBAC and OAuth (use
  rhoai-maas-governance).
---

# Connectivity Link observability

Thin skill: repo decisions and pitfalls here, product procedures in the
linked Connectivity Link 1.4 observability book.

## When to use

- MaaS usage or token panels are empty or flapping.
- You need to trace or correlate one model request across the gateway,
  Authorino and Limitador.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `Kuadrant` sets `spec.observability.enable: true`, so the operator creates ServiceMonitors and PodMonitors for its components and gateways | `gitops/stages/040-governed-models-as-a-service/040-gateway-governance/governance/kuadrant.yaml` | [Enable observability monitoring][enable] |
| User workload monitoring is enabled (`enableUserWorkload: true`) and scrapes those monitors, including Limitador per-user/model series | `gitops/stages/010-openshift-ai-platform-foundation/010-observability-operators/cluster-monitoring/` | [Configure your monitoring stack][stack] |
| The gateway proxy keeps an Envoy stats matcher configured in Git | `gitops/stages/040-governed-models-as-a-service/040-gateway-governance/gateway/` (`maas-gateway-resources` ConfigMap) | — |
| The Connectivity Link Grafana dashboards are not imported; repo-owned MaaS cost and tokenomics dashboards read the Limitador series | `gitops/stages/040-governed-models-as-a-service/040-maas-platform/observability/` | [Dashboards and alerts][dash] |
| No data-plane tracing or access-log Telemetry CRs are configured | — | [Tracing][tracing], [Access logs][logs] |

## Procedure

After the OpenShift safety guard in `AGENTS.md`:

```bash
oc get servicemonitor,podmonitor -A -l kuadrant.io/observability=true
oc logs -n openshift-ingress -l gateway.networking.k8s.io/gateway-name=maas-default-gateway --since=10m | tail
```

To add tracing or access logs, follow [Tracing][tracing] or
[Access logs][logs] and record the decision in the 040 gateway-governance
README; correlation uses `x-request-id` ([Request correlation][corr]).

## Pitfalls

- Intermittent zero tokens on the usage view: Limitador PodMonitor churn,
  see `docs/TROUBLESHOOTING.md#usage-dashboard-shows-zeros-or-gaps-limitador-podmonitor-churn`.
- Setting `observability.enable: false` removes the operator-made monitors;
  the usage views then go empty.

## Official documentation (Connectivity Link 1.4)

| Topic | Section |
|---|---|
| Overview and stack | [Observability features][features], [Configure your monitoring stack][stack] |
| Enable monitors | [Enable observability monitoring][enable] |
| Dashboards and alerts | [Dashboards and alerts][dash] |
| Tracing | [Tracing][tracing] |
| Access logs and correlation | [Access logs][logs], [Request correlation][corr] |
| MCP gateway | [Observe MCP gateway connections][mcp] |

## Related skills

`rhoai-maas-governance`, `ocp-observability`, `ocp-opentelemetry`, `ocp-distributed-tracing`, `rhcl-troubleshoot`.

[features]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/observability/index#rhcl-observability-features_rhcl-observability
[stack]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/observability/index#configure-obs-monitoring_rhcl-observability
[enable]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/observability/index#rhcl-enable-observability-monitor_rhcl-observability
[dash]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/observability/index#rhcl-about-configuring-observability-dashboards_rhcl-observability
[tracing]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/observability/index#rhcl-obs-about-tracing_rhcl-observability
[logs]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/observability/index#ref-obs-configure-access-logs_rhcl-observability
[corr]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/observability/index#con-obs-access-logs-correlation_rhcl-observability
[mcp]: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/observability/index#mcp-gateway-observe
