---
name: rhdh-monitoring
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when configuring monitoring, logging, and performance tracking for Red
  Hat Developer Hub 1.10. Covers LOG_LEVEL configuration via Operator and Helm,
  enabling ServiceMonitor metrics on OpenShift, Amazon Prometheus and
  CloudWatch integration, Azure AKS monitoring and live logs, and Red Hat
  Build of Keycloak OpenTelemetry metrics. Do NOT use for audit log
  configuration or RBAC audit events; use rhdh-audit-logs. Do NOT use for
  Segment web analytics or telemetry data collection; use rhdh-telemetry.
---

# RHDH Monitoring

Use this skill to configure monitoring, logging, and performance tracking
for Red Hat Developer Hub 1.10.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is the product authority. This skill adapts
the official Monitoring and Logging guide for this repo's demo posture.

## Scope

This skill covers:

- Application log level configuration (`LOG_LEVEL` environment variable)
- Enabling metrics via `ServiceMonitor` on OpenShift Container Platform
- Amazon Prometheus and CloudWatch integration
- Azure AKS monitoring and live logs
- Red Hat Build of Keycloak (RHBK) OpenTelemetry metrics

## Demo Policy

For this repo:

- Treat monitoring as optional platform infrastructure until a demo step
  explicitly introduces it.
- The OCP deployment path (ServiceMonitor) is the primary focus for this demo.
- AWS and AKS monitoring sections are documented for reference but are not
  part of the default demo flow.
- Do not commit cloud provider credentials or Prometheus endpoints.
- Use `ocp-observability` for the underlying OCP monitoring stack before
  applying RHDH-specific monitoring configuration.

## Workflow

### Log Level Configuration

1. Set `LOG_LEVEL` via the Backstage CR (Operator) or `values.yaml` (Helm).
2. Supported values in order of increasing severity: `debug`, `info` (default),
   `warn`, `error`, `critical`.

### OCP Metrics Enablement (Operator)

1. Confirm monitoring for user-defined projects is enabled on the cluster.
2. Edit the Backstage CR to set `spec.monitoring.enabled: true`.
3. The Operator creates a `ServiceMonitor` named `metrics-<cr_name>`
   automatically with correct labels.
4. Verify in the OpenShift web console under Observe > Dashboard.

### OCP Metrics Enablement (Helm)

1. Confirm monitoring for user-defined projects is enabled on the cluster.
2. Set `upstream.metrics.serviceMonitor.enabled: true` and
   `upstream.metrics.serviceMonitor.path: /metrics` in `values.yaml`.
3. Upgrade the Helm release.
4. Verify in the OpenShift web console under Observe > Dashboard.

### RHBK Metrics

The RHBK backend plugin exposes OpenTelemetry counters:

| Metric | Description |
|--------|-------------|
| `backend_keycloak_fetch_task_failure_count_total` | Fetch task failures with no data returned |
| `backend_keycloak_fetch_data_batch_failure_count_total` | Partial data batch failures |

All counters include the `taskInstanceId` label for tracing individual fetch
task executions. Query with PromQL in Prometheus UI or Grafana.

## Verification Commands

```bash
oc get servicemonitor -n <rhdh-namespace>
oc get pods -l app.kubernetes.io/name=developer-hub -n <rhdh-namespace>
oc logs deployment/<rhdh-deployment> -n <rhdh-namespace> | head -20
```

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
