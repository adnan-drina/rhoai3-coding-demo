---
name: rhoai-observability
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use for official RHOAI observability: support posture, DSCInitialization monitoring,
  monitoring namespace, COO/Tempo/OpenTelemetry, Prometheus/Alertmanager, observability
  dashboard, scrape labels, external exporters, trace access and alerts. Do NOT use for
  pod/audit logs (rhoai-logs-and-audit-records), deployed-model runtime dashboards (rhoai-
  model-management-monitoring), TrustyAI fairness/drift or guardrails-specific telemetry;
  use the matching rhoai skills. Pair live diagnostics with the environment
  troubleshooting skill and OpenShift safety guard.
---

# RHOAI Observability

Use this skill to manage the OpenShift AI observability stack and dashboard
visibility for the active product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official Administer chapter to this repo's GitOps and Technology Preview
governance model.

## Support Posture

For the current baseline, OpenShift AI observability is Technology Preview.
Document that status whenever enabling, presenting, or reviewing this
capability. Do not represent it as production-supported SLA functionality.

## Demo Policy

For this repo:

- Treat observability as optional platform infrastructure until a demo step
  explicitly introduces it.
- Use `ocp-observability` for the underlying OCP monitoring, logging, and COO
  product boundary before applying RHOAI-specific observability configuration.
- Use `ocp-opentelemetry` for Red Hat build of OpenTelemetry Operator,
  Collector, instrumentation, and telemetry-pipeline behavior before applying
  RHOAI-specific observability configuration.
- Use `ocp-distributed-tracing` for Tempo Operator, `TempoStack`, trace
  tenancy, trace RBAC, and distributed tracing back-end behavior before
  applying RHOAI-specific observability configuration.
- Use `redhat-ods-monitoring` as the monitoring namespace unless an active
  implementation decision changes it.
- Do not add `monitoring.opendatahub.io/scrape=true` to operator-managed
  workloads.
- Add scrape labels only to user workloads that expose metrics and are intended
  for monitoring.
- Keep external exporter credentials and endpoints out of Git unless they are
  harmless placeholders.
- Keep port-forward examples as operator runbook examples, not automated demo
  scripts.
- Treat RHOAI-generated observability operands as product-owned. Stage 110's
  Cluster Observability Operator `startingCSV` hold is an OLM lifecycle policy,
  not an image pin. Do not patch generated `Perses.spec.image`, generated
  `PersesDatasource` resources, or operator-created observability Deployments
  as durable fixes.
- Use `rhoai-guardrails-safety` for guardrails CR-level OpenTelemetry fields,
  spans, detector metrics, and Guardrails Gateway metrics. Use this skill for
  the shared observability stack receiving that data.
- Use `rhoai-monitoring-trustyai` for TrustyAI bias metrics, data drift
  metrics, `TrustyAIService`, model observations, and `trustyai_*` metric
  semantics. Use this skill for the shared observability stack surfacing those
  metrics.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Confirm the Technology Preview status is acceptable for the intended demo.
3. Confirm prerequisite Operators are installed:
   - Cluster Observability Operator
   - Tempo Operator
   - Red Hat build of OpenTelemetry
   Confirm the installed CSV through the owning Subscription, not copied CSVs
   or display names.
4. Configure `DSCInitialization.spec.monitoring` through GitOps.
5. Enable the dashboard menu with
   `OdhDashboardConfig.spec.dashboardConfig.observabilityDashboard: true`
   when UI access is required.
6. Add `monitoring.opendatahub.io/scrape=true` only to eligible user workload
   pod templates.
7. Configure metrics or trace exporters only when an external endpoint is
   approved and reachable.
8. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/observability-patterns.md`
