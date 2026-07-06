# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat build of OpenTelemetry on OpenShift |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation version | 3.9 |
| Documentation landing page | https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9 |
| Capture date | 2026-06-10 |

| Guide | Source URL | Sections captured |
|-------|------------|-------------------|
| About Red Hat build of OpenTelemetry | https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9/html-single/about_red_hat_build_of_opentelemetry/index | product overview, Collector purpose, telemetry pipeline value, storage/query/delivery boundary |
| Installing Red Hat build of OpenTelemetry | https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9/html-single/installing_red_hat_build_of_opentelemetry/index | Operator install, namespace, subscription, `OpenTelemetryCollector`, deployment modes, verification, RBAC automation |
| Configuring the Collector | https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9/html-single/configuring_the_collector/index | Collector deployment modes, receivers, processors, exporters, connectors, extensions, Technology Preview notes |
| Configuring the instrumentation | https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9/html-single/configuring_the_instrumentation/index | `Instrumentation` resources, injection annotations, auto-instrumentation, multi-container behavior, Service Mesh propagator |
| Sending traces, logs, and metrics to the Collector | https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9/html-single/sending_traces_logs_and_metrics_to_the_collector/index | application-to-Collector telemetry sending patterns |
| Configuring metrics for the monitoring stack | https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9/html-single/configuring_metrics_for_the_monitoring_stack/index | Prometheus integration, `ServiceMonitor`, `PodMonitor`, in-cluster monitoring federation |
| Forwarding telemetry data | https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9/html-single/forwarding_telemetry_data/index | forwarding traces, logs, metrics, third-party systems, cloud providers |
| Configuring the Collector metrics | https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9/html-single/configuring_the_collector_metrics/index | Collector internal metrics, metrics service, user-defined monitoring prerequisite |
| Receiving telemetry data | https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9/html-single/receiving_telemetry_data/index | receiving telemetry from instrumented applications and multiple clusters |
| Troubleshooting the Red Hat build of OpenTelemetry | https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9/html-single/troubleshooting_the_red_hat_build_of_opentelemetry/index | must-gather, Collector logs, Collector metrics, diagnostics |

## Captured Product Objects

- Red Hat build of OpenTelemetry Operator
- `OpenTelemetryCollector` custom resources
- `Instrumentation` custom resources
- Operator namespace `openshift-opentelemetry-operator`
- Operator subscription name `opentelemetry-product`
- Operator channel `stable`
- Collector service accounts, RBAC, SCCs, Services, Pods, ConfigMaps, and
  monitoring resources
- OpenShift monitoring integration through `ServiceMonitor` and `PodMonitor`
- Collector deployment modes: `deployment`, `daemonset`, `statefulset`,
  `sidecar`
- Collector pipeline components:
  - receivers
  - processors
  - exporters
  - connectors
  - extensions

## Source Boundaries

Do not infer Red Hat support posture from upstream OpenTelemetry docs. Upstream
OpenTelemetry documentation can explain concepts, but Red Hat product
behavior, supported components, API versions, fields, Operator channels, and
Technology Preview posture must come from Red Hat documentation or active
cluster schema.

Do not treat OpenTelemetry as a storage, query, dashboard, or alerting backend.
The official docs state that OpenTelemetry does not guarantee telemetry
delivery and has no built-in storage or query capabilities.

Some Collector components, exporters, receivers, processors, connectors,
extensions, and auto-instrumentation modes are Technology Preview. Review the
specific component section before using it in a demo claim or GitOps manifest.

## Related Official Sources To Add Later

- Version-specific Red Hat OpenShift Logging documentation when LokiStack log
  forwarding becomes active
- Version-specific Monitoring stack for Red Hat OpenShift documentation when
  OpenTelemetry metrics scraping or federation becomes active
- Red Hat Customer Portal guidance for scheduling OpenTelemetry components on
  infra nodes when taints and tolerations are implemented
