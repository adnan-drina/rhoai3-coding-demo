# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat Connectivity Link |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Observe |
| Official guide | Observability |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/observability/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/observability/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Connectivity Link observability
  - Observability features overview (metrics, tracing, access logs, dashboards)
  - Configure your observability monitoring stack (Prometheus, Grafana,
    user workload monitoring)
  - Enabling observability monitoring in Connectivity Link
    (`spec.observability.enable` in `Kuadrant` CR)
  - About configuring observability dashboards and alerts
    - Platform engineer Grafana dashboard
    - Application developer Grafana dashboard
    - Business user Grafana dashboard
    - Grafana dashboards available to import (IDs: 21538, 20982, 20981, 22695)
    - Importing dashboards in Grafana
    - About importing dashboards automatically in OCP
    - About configuring Prometheus alerts (PrometheusRule, SLO alerts via Sloth)
  - Tracing in Connectivity Link
    - Correlating control plane and data plane traces
    - Control-plane tracing environment variables (OTEL_EXPORTER_OTLP_ENDPOINT,
      OTEL_SERVICE_NAME, etc.)
    - Configuring data plane tracing (Telemetry CR, Istio CR extension
      providers, Authorino CR, Limitador CR, Kuadrant CR)
    - Troubleshooting by using traces and logs
    - Viewing rate-limit logging with trace IDs (Limitador verbosity 3+)
  - Configuring access logs
    - Telemetry API for mesh-wide and workload-scoped access logs
    - JSON-formatted access logs
    - Filtering access logs (CEL expressions)
    - Common access log format variables
  - About using access logs for request correlation
    - Setting up access log and tracing correlation
      (`httpHeaderIdentifier: x-request-id`)
- Chapter 2: Observing MCP gateway connections
  - Enabling Red Hat build of OpenTelemetry for MCP gateway
    (OpenTelemetryCollector CR, OTEL environment variables)
  - MCP gateway router spans (mcp-router.process, route-decision,
    broker-passthrough, tool-call, broker.get-server-info, session-cache.get,
    session-init, session-cache.store)
  - Root span attributes (http.method, mcp.method.name, gen_ai.tool.name,
    mcp.session.id, etc.)
  - Error attributes (error.type, error_source, http.status_code)
  - Understanding an MCP gateway audit trail
  - Configuring an AuthPolicy with identity injection (mcp and mcps listeners)
  - Verifying AuthPolicy identity injection
  - Adding a custom audit log provider (Istio MeshConfig extensionProviders)
  - Custom audit log provider fields reference
  - Create a Telemetry CR for audit logs
  - Verifying your audit trail
  - Using an audit trail without authentication

## Source Boundaries

This source covers:

- Connectivity Link observability features and configuration
- Prometheus metrics, Grafana dashboards, and alerts
- Control-plane and data-plane tracing with OpenTelemetry
- Envoy access logs, JSON formatting, CEL filtering
- Request correlation via x-request-id
- MCP gateway OpenTelemetry collector and router spans
- MCP gateway audit trail with AuthPolicy identity injection
- Istio Telemetry CR configuration for access logs

This source does NOT cover:

- Connectivity Link installation or operator lifecycle
- API management, console plugin, or RBAC configuration
- Gateway, HTTPRoute, or policy creation
- MCP gateway installation or MCP server registration
- General OCP monitoring, logging, or COO configuration
- Troubleshooting procedures (except tracing-based troubleshooting)

## Related Official Sources

- [Troubleshooting](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/troubleshooting/index)
- [Developing APIs with the web console](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/developing_apis_with_the_web_console/index)
- [Deploying Red Hat Connectivity Link](https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/deploying_red_hat_connectivity_link/index)
