# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product | Red Hat Developer Hub |
| Product version | 1.10 |
| Book title | Monitoring and logging |
| Book URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/monitoring_and_logging/index |
| Documentation category | Observability |
| Retrieved date | 2026-07-06 |
| Sections used | Chapter 1. Log levels; Chapter 2. Enable observability for RHDH on OCP; Chapter 3. Monitoring and logging RHDH on AWS; Chapter 4. Monitor and log with AKS; Chapter 5. Red Hat Build of Keycloak metrics |

## Supporting Red Hat Sources

| Source | Role |
|--------|------|
| Red Hat OpenShift Container Platform — Monitoring for user-defined projects | Prerequisite for ServiceMonitor scraping |
| Amazon Prometheus documentation (linked from official chapter) | AWS metrics integration context |
| Azure Monitor documentation (linked from official chapter) | AKS monitoring integration context |
| Backstage OpenTelemetry setup guide (linked from official chapter) | RHBK metrics export context |

## Source Boundaries

- Product configuration truth: official Red Hat Developer Hub 1.10 Monitoring
  and Logging book above.
- LOG_LEVEL values: `debug`, `info`, `warn`, `error`, `critical` are the
  documented severity levels.
- ServiceMonitor: the Operator creates `metrics-<cr_name>` automatically when
  `spec.monitoring.enabled: true` is set.
- Prometheus annotations: `prometheus.io/scrape`, `prometheus.io/path`,
  `prometheus.io/port`, `prometheus.io/scheme` are the documented pod
  annotations for AWS and AKS monitoring.
- RHBK metrics: `backend_keycloak_fetch_task_failure_count_total` and
  `backend_keycloak_fetch_data_batch_failure_count_total` are documented
  counters with `taskInstanceId` label.
- Not authoritative: upstream Backstage metrics internals, cloud provider
  monitoring configuration beyond what the RHDH docs describe, or OpenShift
  monitoring operator internals.

## Unresolved Or Environment-Specific Items

- AWS Prometheus workspace ARN and ingestion endpoint are environment-specific.
  Verification: obtain approved Amazon Prometheus workspace before configuring.
- Azure Monitor workspace and AKS cluster resource group are
  environment-specific.
  Verification: confirm AKS cluster and Azure Monitor workspace exist before
  enabling metrics.
- CloudWatch log group naming follows
  `/aws/containerinsights/<cluster_name>/application` pattern. The cluster
  name is environment-specific.
