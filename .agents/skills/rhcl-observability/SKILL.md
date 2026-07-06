---
name: rhcl-observability
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when configuring observability, monitoring gateways, APIs, and
  applications on OpenShift with Connectivity Link: metrics and Prometheus
  monitoring, Grafana dashboards (platform engineer, application developer,
  business user), ServiceMonitor and PodMonitor configuration, control-plane
  and data-plane tracing with OpenTelemetry, Envoy access logs and request
  correlation, MCP gateway observability with OpenTelemetry spans and audit
  trails, and AuthPolicy identity injection for audit logging. Do NOT use for
  Connectivity Link installation, API management, or gateway deployment; use
  the relevant rhcl-* skill. Do NOT use for OCP-level monitoring, logging, or
  Cluster Observability Operator; use the relevant ocp-* skill. Do NOT invent
  CR fields, API versions, or telemetry configurations not documented in the
  official source.
---

# RHCL Observability

Use this skill to ground Connectivity Link observability guidance in the
official Red Hat Connectivity Link 1.4 documentation for the active baseline
in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill captures the Connectivity
Link observability model including metrics, tracing, access logs, dashboards,
MCP gateway observability, and audit trails.

## Key Concepts

### Observability Features

- **Metrics**: Prometheus metrics for gateway and policy performance via
  Connectivity Link components, Gateway API state metrics, and Envoy metrics.
- **Tracing**: control-plane traces (operator reconciliation) and data-plane
  traces (request flows through Istio, Authorino, Limitador, wasm-shim).
- **Access Logs**: Envoy access logs with request correlation via
  `x-request-id` headers.
- **Dashboards**: pre-built Grafana dashboards for platform engineers,
  application developers, and business users.

### Enabling Observability

Set `spec.observability.enable: true` in the `Kuadrant` CR
(`kuadrant.io/v1beta1`) to create `ServiceMonitor` and `PodMonitor` CRDs
automatically.

### MCP Gateway Observability

Uses Red Hat build of OpenTelemetry with `OpenTelemetryCollector` CR for
traces and logs. Router spans follow OpenTelemetry MCP Semantic Conventions.
Audit trails capture caller identity, tool names, and session context through
`AuthPolicy` identity injection and Istio Telemetry access logs.

## Workflow

1. Confirm the active RHCL baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - enabling Connectivity Link observability monitoring
   - configuring Grafana dashboards and alerts
   - setting up control-plane or data-plane tracing
   - configuring Envoy access logs and filtering
   - request correlation across components
   - MCP gateway OpenTelemetry setup
   - MCP gateway audit trail configuration
   - AuthPolicy identity injection for audit logs
4. For manifests, verify all API versions, CRDs, fields, namespaces, and
   credentials before committing.
5. Validate the output with the official source and cluster schema.

## Related Skills

- Use `rhcl-develop` for API management, console plugin, RBAC, and API product
  workflows.
- Use `rhcl-troubleshoot` for diagnosing gateway, routing, policy, and MCP
  gateway issues.
- Use `ocp-observability` for OCP-level monitoring, logging, and COO.
- Use `ocp-opentelemetry` for Red Hat build of OpenTelemetry Operator and
  Collector configuration.
- Use `ocp-distributed-tracing` for Tempo Operator, TempoStack, and tracing
  platform configuration.
- Use `ocp-grafana-operator` for GitOps-managed Grafana Operator instances and
  dashboards.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
