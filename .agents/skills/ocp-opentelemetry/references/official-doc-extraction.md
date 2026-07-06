# Official Doc Extraction

Use this extraction to keep Red Hat build of OpenTelemetry content grounded in
official Red Hat documentation. Before authoring manifests, verify the active
cluster CRDs and the installed Operator version.

## Product Definition

The official docs describe Red Hat build of OpenTelemetry as based on the
upstream OpenTelemetry project and as providing support for deploying and
managing the OpenTelemetry Collector and simplifying workload instrumentation.

The Collector can receive, process, and forward telemetry data in multiple
formats. It provides a unified solution for collecting and processing metrics,
traces, and logs, and can interoperate between telemetry systems.

The official docs also state that OpenTelemetry does not guarantee telemetry
data delivery and does not include built-in storage or query capabilities.

## Operator Installation

Installing Red Hat build of OpenTelemetry involves:

- installing the Red Hat build of OpenTelemetry Operator
- creating a namespace for an OpenTelemetry Collector instance
- creating an `OpenTelemetryCollector` custom resource

The captured CLI install example uses:

- Operator namespace: `openshift-opentelemetry-operator`
- Operator namespace label:
  `openshift.io/cluster-monitoring: "true"`
- `OperatorGroup` in `openshift-opentelemetry-operator`
- `Subscription` named `opentelemetry-product`
- channel: `stable`
- install plan approval: `Automatic`
- source: `redhat-operators`
- source namespace: `openshift-marketplace`

The captured web console install example states the default presets:

- update channel: `stable`
- installation mode: all namespaces on the cluster
- installed namespace: `openshift-opentelemetry-operator`
- update approval: `Automatic`

Collector instance project names beginning with the `openshift-` prefix are
not permitted.

## Collector Custom Resource

The captured install examples use:

- API version: `opentelemetry.io/v1beta1`
- kind: `OpenTelemetryCollector`
- `spec.mode`
- `spec.config`

Supported Collector deployment modes in the captured docs:

- `deployment`, the default
- `statefulset`, for stateful workloads such as the File Storage Extension or
  Tail Sampling Processor
- `daemonset`, for node-level scraping such as Filelog Receiver container logs
- `sidecar`

The Collector pipeline is configured with:

- receivers
- processors
- exporters
- connectors
- extensions

Use exact Red Hat documentation sections or active `oc explain` output for
component-specific fields. Do not mix upstream examples into product manifests
unless Red Hat docs or active CRDs confirm them.

## Instrumentation

Use `Instrumentation` custom resources and pod annotations for workload
auto-instrumentation.

Captured annotation patterns include:

- `instrumentation.opentelemetry.io/inject-go: "true"`
- `instrumentation.opentelemetry.io/otel-go-auto-target-exe: "/<path>/<to>/<container>/<executable>"`
- `instrumentation.opentelemetry.io/container-names: "<container_1>,<container_2>"`
- `instrumentation.opentelemetry.io/<application_language>-container-names: "<container_1>,<container_2>"`

For multi-container pods, the docs state that instrumentation is injected into
the first available container by default, and target containers can be
specified with annotations. Go auto-instrumentation does not support
multi-container auto-instrumentation injection.

When using the `Instrumentation` custom resource with Red Hat OpenShift
Service Mesh, use the `b3multi` propagator.

Go auto-instrumentation and Java auto-instrumentation are captured as
Technology Preview in the 3.9 docs. The Go section also states that the feature
injects unsupported upstream instrumentation libraries by default and requires
additional OpenShift permissions.

## Metrics And Monitoring Stack Integration

The metrics integration guide states that the `OpenTelemetryCollector` custom
resource can configure a Prometheus receiver to scrape metrics from the
in-cluster monitoring stack, or configure a Prometheus `ServiceMonitor` custom
resource to scrape Collector pipeline metrics and enabled Prometheus exporter
metrics.

The captured docs include:

- `spec.observability.metrics.enableMetrics: true`
- automatic creation of a `ServiceMonitor` or `PodMonitor` when
  `enableMetrics` is true
- two `ServiceMonitor` instances when enabled for deployment mode:
  - one for `<instance_name>-collector-monitoring`
  - one for `<instance_name>-collector`
- a manually created `PodMonitor` as an option for finer control
- a prerequisite that monitoring for user-defined projects is enabled for
  Collector metrics scraping

The Collector metrics guide states that the Operator automatically creates a
service named `<instance_name>-collector-monitoring` that exposes internal
Collector metrics on port `8888` by default.

## Forwarding And Receiving Telemetry

The sending guide states that Red Hat build of OpenTelemetry can send traces,
logs, and metrics to the OpenTelemetry Collector or a `TempoStack` instance.
Sending traces and metrics to the Collector can be configured with or without
sidecar injection.

The captured sidecar pattern uses `mode: sidecar` on the
`OpenTelemetryCollector` and adds the
`sidecar.opentelemetry.io/inject: "true"` annotation to the workload
`Deployment`. The non-sidecar pattern deploys a Collector instance and sets
application container environment variables such as `OTEL_SERVICE_NAME` and
`OTEL_EXPORTER_OTLP_ENDPOINT`.

The forwarding guide states that the Collector can forward telemetry data.
Captured forwarding targets include:

- traces to a `TempoStack`
- logs to a `LokiStack`
- third-party systems
- AWS
- Google Cloud
- Google-managed Prometheus

For TempoStack forwarding, the captured prerequisites include the Red Hat build
of OpenTelemetry Operator, Tempo Operator, and a deployed TempoStack instance.

The receiving guide states that, after setting up the Collector and
instrumenting an application, the application instrumentation must be connected
to the Collector so that the Collector can receive telemetry.

For multi-cluster receiving, the captured pattern is one Collector instance in
each remote cluster forwarding telemetry to a central Collector instance.

## Troubleshooting

The troubleshooting guide includes:

- `oc adm must-gather` for diagnostic data covering resources such as
  `OpenTelemetryCollector`, `Instrumentation`, `Deployment`, `Pod`, and
  `ConfigMap`
- the default Operator namespace for must-gather:
  `openshift-opentelemetry-operator`
- Collector log level configuration under
  `config.service.telemetry.logs.level`
- supported Collector log levels: `info`, `warn`, `error`, and `debug`
- Collector processed-volume metrics such as receiver accepted/refused spans,
  exporter sent spans, and enqueue failure counts

## Demo-Specific Handoff

The following are project constraints, not claims extracted from the
OpenTelemetry docs:

- Use GitOps for active Operator, Collector, `Instrumentation`, RBAC, and
  monitoring resources.
- Use OpenTelemetry to connect demo telemetry to approved backends; do not
  treat it as the backend itself.
- Keep external sink credentials and sensitive telemetry out of Git.
- Use `rhoai-guardrails-safety` for guardrails telemetry semantics and
  `rhoai-maas-governance` for MaaS usage export semantics.
- Use `ocp-observability` for the broader OCP observability boundary.

Use `project-gitops-authoring` and `project-manifest-review` for repo-specific
implementation and review rules.
