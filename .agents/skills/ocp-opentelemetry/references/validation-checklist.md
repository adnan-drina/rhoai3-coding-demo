# Validation Checklist

Use this checklist when reviewing Red Hat build of OpenTelemetry documentation,
GitOps manifests, or live operations.

## Source And Baseline

- The task references `docs/PLATFORM_BASELINE.md`.
- Red Hat build of OpenTelemetry claims are tied to the pinned 3.9 official
  docs or active cluster schema.
- OCP default monitoring, logging, and broad observability claims are handled
  by `ocp-observability`.
- RHOAI-specific telemetry semantics are handled by the relevant `rhoai-*`
  skills.
- Upstream OpenTelemetry docs are not used as Red Hat product authority.

## Manifest Review

- Operator installation uses verified namespace, `OperatorGroup`,
  `Subscription`, channel, install approval, source, and source namespace.
- `OpenTelemetryCollector` resources use verified API versions and fields.
- Collector instance namespaces do not begin with the `openshift-` prefix.
- Collector mode is intentionally selected: `deployment`, `daemonset`,
  `statefulset`, or `sidecar`.
- Receiver, processor, exporter, connector, and extension fields are verified
  against Red Hat docs or active CRDs.
- Technology Preview components are explicitly labeled when used.
- `Instrumentation` CR fields and injection annotations are verified.
- Service Mesh instrumentation uses the required propagator.
- `ServiceMonitor`, `PodMonitor`, and
  `spec.observability.metrics.enableMetrics` behavior is verified before
  claiming OpenShift monitoring integration.
- User-defined project monitoring is enabled before expecting Collector
  metrics to appear in the user monitoring stack.
- RBAC, SCC, service account, ClusterRole, and ClusterRoleBinding changes are
  reviewed as platform-sensitive resources.
- External backends, bearer tokens, cloud credentials, TLS material, and API
  keys are not committed.

## Read-Only Cluster Checks

Run only after the repo environment guard confirms the target cluster:

```bash
oc get clusterversion
oc get subscription -A | grep -Ei 'opentelemetry|otel'
oc get csv -A | grep -Ei 'opentelemetry|otel'
oc get pods -n openshift-opentelemetry-operator
oc api-resources | grep -Ei 'opentelemetry|otel|instrumentation'
oc get crd | grep -Ei 'opentelemetry|otel|instrumentation'
oc get opentelemetrycollector -A
oc get instrumentation -A
oc get servicemonitor -A | grep -Ei 'otel|opentelemetry'
oc get podmonitor -A | grep -Ei 'otel|opentelemetry'
```

For schema verification:

```bash
oc explain opentelemetrycollector.spec
oc explain opentelemetrycollector.spec.observability
oc explain instrumentation.spec
```

For Collector health:

```bash
oc get pod -A -l app.kubernetes.io/managed-by=opentelemetry-operator
oc get service -A -l app.kubernetes.io/managed-by=opentelemetry-operator
oc logs -n <collector_namespace> <collector_pod_name>
```

For must-gather, use only after confirming the target cluster and output path:

```bash
oc adm must-gather --image=ghcr.io/open-telemetry/opentelemetry-operator/must-gather -- \
  /usr/bin/must-gather --operator-namespace openshift-opentelemetry-operator
```

## Live Operation Review

- The repo-local OpenShift safety guard is used before any `oc` or `kubectl`
  command that touches the cluster.
- Operator installation, Collector creation, instrumentation injection, RBAC,
  SCC, ServiceMonitor, PodMonitor, external sink, and credential changes have
  explicit user approval.
- Argo CD-managed resources are not also managed with direct `oc apply -k`
  unless the exception is documented.
- Telemetry routing does not send sensitive data to unapproved external
  systems.
- Log levels such as `debug` are used intentionally and are not left enabled
  without operational intent.

## Fail Conditions

Stop and ask for verification if:

- the OpenTelemetry documentation version does not match
  `docs/PLATFORM_BASELINE.md`
- a manifest includes unverified `opentelemetry.io` fields
- a Technology Preview feature is presented as production-ready
- storage, query, delivery, dashboard, or alerting capabilities are attributed
  to OpenTelemetry itself
- credentials, tokens, customer data, or sensitive telemetry samples would be
  committed
- the target cluster has no Red Hat build of OpenTelemetry CRDs installed and
  the task requires schema-accurate manifests
