# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Container Platform |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Observability |
| Official guide | Observability overview |
| Source URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/observability_overview/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/observability_overview/index |
| Capture date | 2026-06-10 |

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Container Platform |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Observability |
| Official guide | Monitoring |
| Source URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/monitoring/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/monitoring/index |
| Capture date | 2026-06-10 |

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Container Platform |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Observability |
| Official guide | Logging |
| Source URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/logging/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/logging/index |
| Capture date | 2026-06-10 |

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Container Platform |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Observability |
| Official guide | Cluster Observability Operator |
| Source URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html-single/cluster_observability_operator/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/cluster_observability_operator/index |
| Capture date | 2026-06-10 |

## Captured Sections

- Observability overview abstract and "About Observability"
- Observability component list:
  - Monitoring
  - Logging
  - Distributed tracing
  - Red Hat build of OpenTelemetry
  - Network Observability
  - Power monitoring
- Observability release-cadence boundary
- Monitoring abstract and "About OpenShift Container Platform monitoring"
- Default OCP monitoring stack posture
- User-defined project monitoring statement
- Monitoring documentation boundary
- Logging abstract and "About Logging"
- Log data collection, visualization, forwarding, and storage statement
- Node system audit, application container, and infrastructure log statement
- Logging documentation boundary
- Cluster Observability Operator abstract and overview
- Standalone COO documentation boundary

## Source Boundaries

The OCP observability sources are entry points. They do not provide enough
detail to author production-ready custom resources for every observability
component.

Do not infer detailed fields for the following from the overview pages alone:

- `ServiceMonitor`, `PodMonitor`, `PrometheusRule`, `AlertmanagerConfig`, or
  other monitoring resources
- user workload monitoring ConfigMap structure
- log collector, log store, log forwarder, or output schemas
- Cluster Observability Operator custom resources
- distributed tracing resources
- Red Hat build of OpenTelemetry resources
- Network Observability resources
- Power monitoring resources
- alert routing, retention, storage, tenancy, authentication, or RBAC details

Because logging, COO, and most other observability components can release on a
different cadence from core OCP, capture the separate product documentation or
verify the installed CRDs before creating detailed implementation guidance.

## Related Official Sources To Add Later

- Monitoring stack for Red Hat OpenShift documentation
- Red Hat OpenShift Logging documentation
- Red Hat OpenShift Cluster Observability Operator documentation
- Network Observability Operator documentation
- Power monitoring documentation
