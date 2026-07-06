---
name: ocp-observability
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding OpenShift Container Platform
  observability guidance from official OCP documentation: Observability
  overview, monitoring stack, user-defined project monitoring, metrics,
  customized alerts, Prometheus, Alertmanager, Thanos Querier, logging,
  infrastructure/application/audit logs, log collection, log visualization,
  log forwarding, log storage, Cluster Observability Operator, customizable
  monitoring stacks, and release-cadence handoffs to separate Red Hat
  observability documentation. Do NOT use for Red Hat OpenShift AI
  observability stack configuration, TrustyAI model monitoring, deployed model
  metrics, or RHOAI dashboard observability; use the relevant rhoai-* skill.
  Do NOT use for GitOps-managed Grafana Operator, Grafana instances,
  datasources, dashboards, OAuth routes, or Grafana RBAC; use
  ocp-grafana-operator. Do NOT invent monitoring, logging, or COO custom
  resource fields from OCP overview pages alone.
---

# OCP Observability

Use this skill to ground OpenShift Container Platform observability guidance in
the official OCP documentation for the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill captures the OCP
observability model, the default monitoring posture, the logging scope, and the
Cluster Observability Operator overview.

The OCP observability sources intentionally hand off detailed monitoring,
logging, and COO behavior to separate Red Hat documentation sets. Before
authoring manifests, verify the relevant separate product documentation or the
active cluster schema.

## Demo Observability Posture

For this AWS-hosted RHOAI demo:

- Use OCP platform observability as the base layer before adding RHOAI model,
  TrustyAI, or application-specific observability.
- Keep platform metrics, user workload monitoring, alerting rules, logging, and
  COO resources GitOps-managed once active implementation artifacts exist.
- Do not claim that a metric, alert, dashboard, log pipeline, trace, or
  observability stack exists unless the implementation and validation evidence
  exist.
- Keep OpenShift platform observability separate from Red Hat OpenShift AI
  observability. Use `rhoai-observability`,
  `rhoai-model-management-monitoring`, and `rhoai-monitoring-trustyai` for
  RHOAI-specific surfaces.
- Treat log output configuration, external log sinks, telemetry endpoints, and
  credentials as sensitive live-environment concerns.
- Let OLM and the Cluster Observability Operator own generated operand images,
  CSV `relatedImages`, copied CSVs, and generated observability resources.
  Diagnose image/version mismatches through Subscription and CSV inspection,
  then use operator lifecycle policy or product baseline alignment instead of
  generated image patches.

## OCP Observability Model

Use the official docs to frame:

- **Red Hat OpenShift Observability**: real-time visibility, monitoring, and
  analysis across metrics, logs, traces, and events.
- **Observability components**: Monitoring, Logging, Distributed tracing, Red
  Hat build of OpenTelemetry, Network Observability, and Power monitoring.
- **Unified solution**: observability components connect open-source tools and
  technologies to collect, store, deliver, analyze, and visualize data.
- **Release cadence boundary**: except for monitoring, Red Hat OpenShift
  Observability components have release cycles distinct from core OCP releases.
- **Monitoring**: OCP includes a preconfigured, preinstalled, and self-updating
  monitoring stack for core platform components. Cluster administrators can
  optionally enable monitoring for user-defined projects.
- **Logging**: logging collects, visualizes, forwards, and stores log data for
  troubleshooting, performance analysis, and security threat detection.
- **Cluster Observability Operator**: COO is optional and supports creating and
  managing highly customizable monitoring stacks with more tailored namespace
  views than the default OCP monitoring system.

## Workflow

1. Confirm the active OCP baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - OCP-level observability narrative or component mapping
   - default platform monitoring
   - user-defined project monitoring
   - logging collection, visualization, forwarding, or storage
   - Cluster Observability Operator positioning
   - detailed monitoring, logging, or COO CR fields that require separate docs
     or active schema verification
   - RHOAI-specific observability, which belongs in the relevant `rhoai-*`
     skill
4. For manifests, verify all API versions, CRDs, fields, namespaces,
   Operators, RBAC, credentials, and output endpoints before committing.
   Classify image fields as repo-owned or operator-generated before proposing
   any image pin.
5. For live operations, use the repo environment guard and pair this skill with
   `env-troubleshoot`, `env-manage-resources`, or `env-deploy-and-evaluate`.
6. Validate the output with `references/validation-checklist.md`.

## Related Skills

- Use `rhoai-observability` for the Red Hat OpenShift AI observability stack,
  dashboard visibility, `DSCInitialization.spec.monitoring`, and
  `redhat-ods-monitoring`.
- Use `rhoai-model-management-monitoring` for deployed model metrics, KServe,
  vLLM, NIM, and Grafana model dashboards.
- Use `rhoai-monitoring-trustyai` for TrustyAI fairness, bias, drift, and
  `TrustyAIService` workflows.
- Use `project-gitops-authoring` for repo-specific GitOps implementation.
- Use `project-manifest-review` for structural and security review of
  Kubernetes and OpenShift manifests.
- Use `ocp-opentelemetry` for Red Hat build of OpenTelemetry Operator,
  Collector, instrumentation, telemetry pipelines, and OpenTelemetry metrics
  integration.
- Use `ocp-distributed-tracing` for Red Hat OpenShift distributed tracing
  platform, Tempo Operator, `TempoStack`, `TempoMonolithic`, tenants, trace
  RBAC, Jaeger UI, and distributed tracing UI plugin behavior.
- Use `ocp-grafana-operator` for GitOps-managed Grafana Operator, Grafana
  instances, datasources, dashboards, OAuth routes, and Grafana RBAC.
- Create narrower `ocp-*` skills for Network Observability or Power monitoring
  when official sources are provided and implementation needs them.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/observability-review-patterns.md`
