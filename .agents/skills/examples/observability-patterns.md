# Observability Patterns

These examples show the intended shape for future GitOps manifests and
runbooks. Replace placeholders with verified environment values before using
them in active manifests.

## DSCI Monitoring Fragment

Use this as a `DSCInitialization.spec` fragment, not a complete resource:
Do not replace `metrics` or `traces` with `{}` when enabling the dashboard;
the RHOAI `Monitoring` service treats empty sections as not configured.

```yaml
spec:
  monitoring:
    managementState: Managed
    namespace: redhat-ods-monitoring
    alerting: {}
    metrics:
      replicas: 1
      storage:
        size: 5Gi
        retention: 90d
    traces:
      sampleRatio: '0.1'
      storage:
        backend: pv
        retention: 2160h0m0s
```

Schema check:

```bash
oc explain dscinitialization.spec.monitoring --api-version=dscinitialization.opendatahub.io/v2
oc apply --dry-run=server -f <candidate-dsci.yaml>
```

## Dashboard Menu Fragment

```yaml
spec:
  dashboardConfig:
    observabilityDashboard: true
```

Review against:

```bash
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o yaml
```

## Sandbox Compatibility Checks

In current demo clusters, validate the product-generated monitoring stack and
Perses dashboard access in addition to the official DSCI and dashboard fields:

```bash
oc get secret prometheus-web-tls-ca -n redhat-ods-monitoring \
  -o jsonpath='{.data.service-ca\.crt}{"\n"}'

oc get networkpolicy perses-backend-operator-access -n redhat-ods-monitoring

oc auth can-i list persesdashboards.perses.dev \
  --as=ai-admin --as-group=rhods-admins --all-namespaces

oc auth can-i create prometheuses/k8s --subresource=api \
  --as=ai-admin --as-group=rhods-admins -n openshift-monitoring

CSV=$(oc get subscription cluster-observability-operator \
  -n openshift-cluster-observability-operator \
  -o jsonpath='{.status.installedCSV}')
oc get subscription cluster-observability-operator \
  -n openshift-cluster-observability-operator \
  -o jsonpath='{.spec.installPlanApproval}{" "}{.spec.startingCSV}{" "}{.status.installedCSV}{"\n"}'
oc get csv "$CSV" -n openshift-cluster-observability-operator \
  -o jsonpath='{.spec.relatedImages[?(@.name=="perses")].image}{"\n"}'
oc get perses data-science-perses -n redhat-ods-monitoring \
  -o jsonpath='{.spec.image}{"\n"}'
```

Use the CSV comparison only as diagnostic evidence. Do not patch
`Perses.spec.image`; Stage 110 should align the Cluster Observability Operator
lifecycle and let the operator manage operand images.
Do not copy generated CSVs, generated datasources, or generated observability
Deployments into GitOps as a workaround. If a controller pod failed because of
API timeout or leader-election loss, recreate that pod as live recovery and
then rerun the Stage 110 validation.

Use a GitOps hook to mirror `ConfigMap/prometheus-web-tls-ca` into
`Secret/prometheus-web-tls-ca` only when the generated `MonitoringStack`
expects the Secret and the service-ca bundle is present as a ConfigMap. Do not
commit the cluster-specific CA bundle.

## User Workload Scrape Label

Apply only to user workloads that expose metrics:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: <workload_name>
  namespace: <workload_namespace>
spec:
  template:
    metadata:
      labels:
        monitoring.opendatahub.io/scrape: 'true'
```

Do not add this label to operator-managed workloads.

## Metrics Exporter Fragment

```yaml
spec:
  monitoring:
    metrics:
      exporters:
        - name: <external_exporter_name>
          type: otlp
          endpoint: https://example-otlp-receiver.example.com:4317
```

Alternative exporter types documented by the chapter include
`prometheusremotewrite`. Do not use reserved names such as `prometheus` or
`otlp/tempo`.

## Trace Collection Endpoint

Instrumented applications can send OTLP traces to the collector service:

```text
OTEL_EXPORTER_OTLP_ENDPOINT=http://data-science-collector.redhat-ods-monitoring.svc.cluster.local:4318
```

The chapter documents OTLP gRPC on port `4317` and OTLP HTTP on port `4318`.

## Tempo And Alertmanager Access

Use temporary port-forwarding for operator access unless the demo explicitly
requires a route:

```bash
oc port-forward svc/tempo-query-frontend 3200:3200 -n redhat-ods-monitoring
oc port-forward svc/data-science-monitoringstack-alertmanager 9093:9093 -n redhat-ods-monitoring
```

Open local endpoints:

```text
http://localhost:3200
http://localhost:9093
```
