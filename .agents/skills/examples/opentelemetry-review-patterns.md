# OpenTelemetry Review Patterns

These examples are review patterns and small schema reminders, not complete
deployment manifests. Verify Red Hat docs and active CRDs before committing
resources.

## Source Boundary Review

Use this decision flow:

| Task | Skill |
|------|-------|
| Explain the broad OCP observability model | `ocp-observability` |
| Install Red Hat build of OpenTelemetry Operator | `ocp-opentelemetry` |
| Configure an `OpenTelemetryCollector` pipeline | `ocp-opentelemetry` |
| Configure workload auto-instrumentation | `ocp-opentelemetry` |
| Scrape Collector metrics with OpenShift monitoring | `ocp-opentelemetry` plus `ocp-observability` |
| Send traces to Tempo or logs to LokiStack | `ocp-opentelemetry` plus the version-specific backend docs |
| Interpret RHOAI guardrails spans or detector metrics | `rhoai-guardrails-safety` |
| Review RHOAI observability dashboard behavior | `rhoai-observability` |
| Author GitOps manifests | `project-gitops-authoring` |
| Review manifest correctness and security posture | `project-manifest-review` |
| Deploy or troubleshoot against a live cluster | relevant `env-*` skill plus the OpenShift safety guard |

## Minimal Collector Shape

The captured docs use this resource shape:

```yaml
apiVersion: opentelemetry.io/v1beta1
kind: OpenTelemetryCollector
metadata:
  name: otel
  namespace: <permitted_project_of_opentelemetry_collector_instance>
spec:
  mode: deployment
  config:
    receivers: {}
    processors: {}
    exporters: {}
    service:
      pipelines: {}
```

Review points:

- The Collector namespace must not start with `openshift-`.
- Use a real pipeline before claiming telemetry is processed.
- Keep backend credentials in Secrets, not inline configuration.
- Verify every receiver, processor, exporter, connector, and extension against
  Red Hat docs or active CRDs.

## Metrics Integration Pattern

To expose Collector metrics to the monitoring stack, the captured docs use:

```yaml
apiVersion: opentelemetry.io/v1beta1
kind: OpenTelemetryCollector
metadata:
  name: <name>
spec:
  observability:
    metrics:
      enableMetrics: true
```

Review points:

- User-defined project monitoring must be enabled.
- The Operator-created monitoring service uses the
  `<instance_name>-collector-monitoring` naming pattern and port `8888` by
  default.
- Check OpenShift Observe > Targets or `ServiceMonitor`/`PodMonitor` resources
  before claiming scrape success.

## Instrumentation Pattern

Use `Instrumentation` resources plus workload annotations. For multi-container
pods, the captured docs include:

```yaml
instrumentation.opentelemetry.io/container-names: "<container_1>,<container_2>"
```

For Service Mesh integration, verify the `b3multi` propagator is configured.

Review points:

- Auto-instrumentation support posture varies by language and section.
- Go auto-instrumentation is Technology Preview in the captured docs and
  requires additional OpenShift permissions.
- Do not inject instrumentation into production-like workloads in the live
  demo without an explicit validation plan.

## Troubleshooting Pattern

Use read-only checks first:

```bash
oc get opentelemetrycollector -A
oc get instrumentation -A
oc get pods -A -l app.kubernetes.io/managed-by=opentelemetry-operator
oc get service -A -l app.kubernetes.io/managed-by=opentelemetry-operator
oc logs -n <collector_namespace> <collector_pod_name>
```

Increase Collector log level only when needed and document why:

```yaml
config:
  service:
    telemetry:
      logs:
        level: debug
```
