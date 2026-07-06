# Official Doc Extraction

Use this reference when authoring or reviewing observability stack content.

## Component Purpose

OpenShift AI observability provides centralized monitoring for OpenShift AI
components and user workloads. The stack includes:

- OpenTelemetry Collector for telemetry ingestion and export
- Prometheus for metrics
- Alertmanager for alerts
- Red Hat build of Tempo for distributed tracing

The chapter describes enabling the stack, exposing the dashboard menu,
collecting user workload metrics, exporting metrics, viewing traces, and
accessing built-in alerts.

## Support Posture

For the active baseline, this capability is Technology Preview. Technology
Preview features are not supported with Red Hat production SLAs and may be
functionally incomplete. Use this feature for demo and evaluation unless the
baseline changes.

## Prerequisites

Before enabling the observability stack, confirm:

- cluster administrator privileges
- OpenShift AI installed
- Cluster Observability Operator installed
- Tempo Operator installed
- Red Hat build of OpenTelemetry installed

For dashboard visibility, confirm:

- OpenShift AI administrator privileges
- observability stack enabled in `DSCInitialization`
- access to the default application namespace, `redhat-ods-applications`

## DSCI Monitoring Configuration

The official chapter enables observability in
`DSCInitialization.spec.monitoring`:

| Field | Purpose |
|-------|---------|
| `managementState: Managed` | Enables and manages the observability stack. |
| `namespace: redhat-ods-monitoring` | Namespace where monitoring components are deployed. |
| `alerting: {}` | Uses default Alertmanager settings when empty. |
| `metrics.replicas` | Number of Prometheus instances. |
| `metrics.resources` | CPU and memory requests and limits for Prometheus pods. |
| `metrics.storage.size` | Prometheus storage size. |
| `metrics.storage.retention` | Prometheus metrics retention period. |
| `metrics.exporters` | External metrics exporter configuration. |
| `traces.sampleRatio` | Portion of traces sampled. |
| `traces.storage.backend` | Tempo trace storage backend: `pv`, `s3`, or `gcs`. |
| `traces.storage.retention` | Trace retention period. |
| `traces.exporters` | External trace exporter configuration. |

For an operational dashboard, configure metrics and traces with their required
subfields. A DSCI that only sets `managementState: Managed` and
`namespace: redhat-ods-monitoring`, or leaves metrics and traces empty, can
reconcile as Ready while the RHOAI `Monitoring` service reports
`MetricsNotConfigured`, `TracesNotConfigured`, `PersesAvailable=False`, and
`MonitoringStackAvailable=False`.

Healthy stack pods in `redhat-ods-monitoring` include:

- `alertmanager-data-science-monitoringstack-*`
- `data-science-collector-collector-*`
- `prometheus-data-science-monitoringstack-*`
- `tempo-data-science-tempomonolithic-*`
- `thanos-querier-data-science-thanos-querier-*`

## Dashboard Enablement

The dashboard menu item is enabled through:

```yaml
spec:
  dashboardConfig:
    observabilityDashboard: true
```

The resource is `OdhDashboardConfig` in the OpenShift AI application namespace,
which defaults to `redhat-ods-applications`. After updating, reload the
dashboard and confirm the "Observe & monitor" dashboard menu item appears.

## User Workload Metrics

Metric collection is not automatically active for all deployed workloads. To
include a user workload, add this label to the pod template:

```yaml
monitoring.opendatahub.io/scrape: 'true'
```

Apply the label only to workloads that expose a metrics endpoint and that the
demo intends to monitor. Do not add it to operator-managed workloads because
the operator might overwrite or remove it.

## Metrics Export

External metrics export is configured through
`DSCInitialization.spec.monitoring.metrics.exporters`.

Captured exporter fields:

| Field | Purpose |
|-------|---------|
| `name` | Unique exporter name. Do not use reserved names such as `prometheus` or `otlp/tempo`. |
| `type` | Export protocol, such as `otlp` or `prometheusremotewrite`. |
| `endpoint` | External metrics receiver endpoint. |

Supported examples in the chapter include:

- OTLP gRPC endpoint on port `4317`
- OTLP HTTP endpoint on port `4318`
- Prometheus remote write endpoint ending in `/api/v1/write`

When exporters are removed from the DSCI, the OpenTelemetry Collector reverts
to collecting metrics only for the in-cluster Prometheus instance.

## Trace Access

When tracing is enabled in DSCI, OpenShift AI deploys Tempo and OpenTelemetry
Collector components. Instrumented applications send traces to the collector by
using OTLP:

- gRPC: `4317`
- HTTP: `4318`

The official example endpoint shape is:

```text
http://data-science-collector.redhat-ods-monitoring.svc.cluster.local:4318
```

External trace visualization tools, such as Grafana or Jaeger, connect to
Tempo Query through a route or temporary port forward. Prefer temporary
port-forward access unless the demo explicitly requires an external route.

## Built-In Alerts

The observability stack deploys Alertmanager with built-in alerts for OpenShift
AI platform conditions such as operator downtime, crashlooping pods, and
unresponsive services. Alertmanager is internal by default and can be accessed
locally by port-forwarding the Alertmanager service on port `9093`.

## Verification Commands

These commands are examples for documentation and review. Run live commands
only after applying the OpenShift safety guard in `AGENTS.md`.

```bash
oc get pods -n redhat-ods-monitoring
oc get pods -n redhat-ods-monitoring -l prometheus=data-science-monitoringstack
oc get pods -n redhat-ods-monitoring | grep collector
oc get svc -n redhat-ods-monitoring | grep alertmanager
oc get route -n redhat-ods-monitoring
oc get monitoring.services.platform.opendatahub.io default-monitoring -o yaml
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o yaml
oc explain dscinitialization.spec.monitoring
oc explain odhdashboardconfig.spec.dashboardConfig
```
